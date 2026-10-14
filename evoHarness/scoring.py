
import argparse
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = "gemini-3.5-flash-lite"


def load_jsonl(path: str) -> list[dict]:
    """Load evaluation results from JSONL."""
    records = []
    with open(path, "r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {exc}"
                ) from exc
    return records


def save_jsonl(path: str, records: list[dict]) -> None:
    """Write records to JSONL."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def make_score(
    case_id: str,
    status: str,
    failure_type: str | None,
    reason: str,
    correctness: str,
    scoring_method: str,
    **extra,
) -> dict:
    return {
        "id": case_id,
        "status": status,
        "failure_type": failure_type,
        "reason": reason,
        "correctness": correctness,
        "scoring_method": scoring_method,
        **extra,
    }


def judge_answer(client, result: dict) -> dict:
    """
    Evaluate semantic correctness against the ground truth.
    This judge evaluates correctness, not hallucination rate.
    """
    actual = result.get("actual_response") or {}

    question = result.get("question", "")
    expected_behavior = result.get("expected_behavior")
    expected_answer = result.get("expected_answer", "")
    actual_answer = actual.get("answer", "")
    evidence = actual.get("evidence", [])

    if isinstance(evidence, str):
        evidence_text = evidence
    else:
        evidence_text = json.dumps(
            evidence, ensure_ascii=False, default=str
        )

    prompt = f"""
You are evaluating a document-grounded question-answering system.

Evaluate whether the system's response satisfies the expected behavior
and matches the reference answer in meaning.

QUESTION:
{question}

EXPECTED BEHAVIOR:
{expected_behavior}

GROUND-TRUTH ANSWER:
{expected_answer}

ACTUAL ANSWER:
{actual_answer}

RETRIEVED EVIDENCE (context only):
{evidence_text}

Rules:
1. Judge meaning, not identical wording.
2. Accept reasonable paraphrases and equivalent numerical rounding
   when the reference supports that interpretation.
3. Do not accept a response merely because it repeats one correct fact
   if it materially contradicts the reference or fails the task.
4. For correct_false_premise, determine whether the response identifies
   and corrects the false premise rather than accepting it.
5. Use UNCERTAIN when the reference does not establish the answer
   or the response cannot be judged reliably.
6. Do not infer correctness merely because a claim appears in retrieved
   evidence. The response must answer the question appropriately.
7. Do not calculate a hallucination rate or judge whether every claim
   is grounded. A separate evaluator handles grounding.

Return only valid JSON:
{{
  "verdict": "CORRECT" | "INCORRECT" | "UNCERTAIN",
  "reason": "Brief explanation"
}}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )

    data = json.loads(response.text or "{}")
    verdict = data.get("verdict")

    if verdict not in {"CORRECT", "INCORRECT", "UNCERTAIN"}:
        raise ValueError(f"Invalid judge verdict: {verdict!r}")

    return {
        "verdict": verdict,
        "reason": str(data.get("reason", "No reason provided.")),
    }


def score_result(result: dict, client=None) -> dict:
    """Score behavior deterministically and correctness semantically."""

    case_id = result.get("id", "UNKNOWN")
    expected_behavior = result.get("expected_behavior")
    actual = result.get("actual_response")
    error = result.get("error")

    # 1. Execution failures
    if error or not isinstance(actual, dict):
        return make_score(
            case_id,
            "FAIL",
            "execution_error",
            str(error or "No structured response was recorded."),
            "INCORRECT",
            "deterministic",
        )

    abstained = actual.get("abstained")
    answer = str(actual.get("answer") or "").strip()

    if not isinstance(abstained, bool):
        return make_score(
            case_id,
            "REVIEW",
            None,
            "The response is missing a valid boolean abstained field.",
            "UNCERTAIN",
            "deterministic",
        )

    # 2. Expected abstention: no semantic judge needed
    if expected_behavior == "abstain":
        if abstained:
            return make_score(
                case_id,
                "PASS",
                None,
                "The application abstained as expected.",
                "NOT_APPLICABLE",
                "deterministic",
            )

        return make_score(
            case_id,
            "FAIL",
            "failure_to_abstain",
            "The application answered when abstention was expected.",
            "INCORRECT",
            "deterministic",
        )

    # 3. Answerable question: abstention is a behavioral failure
    if expected_behavior == "answer" and abstained:
        return make_score(
            case_id,
            "FAIL",
            "false_abstention",
            "The application abstained when an answer was expected.",
            "INCORRECT",
            "deterministic",
        )

    # 4. False-premise correction: abstention fails the expected behavior
    if expected_behavior == "correct_false_premise" and abstained:
        return make_score(
            case_id,
            "FAIL",
            "failure_to_correct_false_premise",
            "The application abstained instead of correcting the false premise.",
            "INCORRECT",
            "deterministic",
        )

    if expected_behavior not in {"answer", "correct_false_premise"}:
        return make_score(
            case_id,
            "REVIEW",
            None,
            f"Unknown expected behavior: {expected_behavior}",
            "UNCERTAIN",
            "deterministic",
        )

    if not answer:
        return make_score(
            case_id,
            "FAIL",
            "empty_answer",
            "The application returned an empty answer without abstaining.",
            "INCORRECT",
            "deterministic",
        )

    # 5. Semantic correctness and false-premise evaluation
    if client is None:
        return make_score(
            case_id,
            "REVIEW",
            None,
            "Semantic evaluation was unavailable.",
            "UNCERTAIN",
            "deterministic",
        )

    try:
        judgment = judge_answer(client, result)
    except Exception as exc:
        return make_score(
            case_id,
            "REVIEW",
            None,
            f"Semantic judge error: {type(exc).__name__}: {exc}",
            "UNCERTAIN",
            "llm_judge_error",
        )

    verdict = judgment["verdict"]
    reason = judgment["reason"]

    if verdict == "CORRECT":
        return make_score(
            case_id,
            "PASS",
            None,
            reason,
            "CORRECT",
            "llm_judge",
            semantic_judgment=judgment,
        )

    if verdict == "INCORRECT":
        failure_type = (
            "false_premise_not_corrected"
            if expected_behavior == "correct_false_premise"
            else "incorrect_answer"
        )
        return make_score(
            case_id,
            "FAIL",
            failure_type,
            reason,
            "INCORRECT",
            "llm_judge",
            semantic_judgment=judgment,
        )

    return make_score(
        case_id,
        "REVIEW",
        None,
        reason,
        "UNCERTAIN",
        "llm_judge",
        semantic_judgment=judgment,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate GroundTruth QA behavior and correctness."
    )
    parser.add_argument(
        "--input",
        default="results.jsonl",
        help="Raw evaluation results JSONL.",
    )
    parser.add_argument(
        "--output",
        default="scores.jsonl",
        help="Output scores JSONL.",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip semantic evaluation; applicable answers remain REVIEW.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=4.5,
        help="Delay in seconds between API calls to respect rate limits (default: 4.5s).",
    )
    args = parser.parse_args()

    client = None
    if not args.no_judge:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise SystemExit(
                "GEMINI_API_KEY is missing. Check your .env file."
            )
        client = genai.Client(api_key=api_key)

    results = load_jsonl(args.input)
    scores = []

    for index, result in enumerate(results, start=1):
        score = score_result(result, client)
        scores.append(score)

        # Show progress and preserve partial results if interrupted.
        if index % 5 == 0 or index == len(results):
            save_jsonl(args.output, scores)
            print(f"Scored {index}/{len(results)} cases")
        
        if index < len(results):
            print(f"    [PAUSE] Waiting {args.delay:.1f}s to respect API rate limits...")
            time.sleep(args.delay)

    from collections import Counter

    statuses = Counter(score["status"] for score in scores)
    failures = Counter(
        score["failure_type"]
        for score in scores
        if score["failure_type"]
    )
    methods = Counter(score["scoring_method"] for score in scores)

    print("\n===== SCORING SUMMARY =====")
    print(f"Total cases: {len(scores)}")
    print(f"PASS:        {statuses['PASS']}")
    print(f"FAIL:        {statuses['FAIL']}")
    print(f"REVIEW:      {statuses['REVIEW']}")

    print("\n===== SCORING METHODS =====")
    for method, count in sorted(methods.items()):
        print(f"{method}: {count}")

    print("\n===== FAILURE DISTRIBUTION =====")
    for failure_type, count in sorted(failures.items()):
        print(f"{failure_type}: {count}")

    print(f"\nScores saved to: {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
