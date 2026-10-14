
import argparse
import json
from collections import Counter
from pathlib import Path


def load_jsonl(path):
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


def classify_failure(score, result):
    actual = result.get("actual_response") or {}
    evidence = actual.get("evidence") or []
    answer = str(actual.get("answer") or "").strip()
    abstained = actual.get("abstained")
    failure_type = score.get("failure_type")
    question = result.get("question", "")

    base = {
        "observed_failure": failure_type,
        "cluster": "needs_investigation",
        "root_cause_hypothesis": "Insufficient evidence to assign a root cause.",
        "evidence_available": bool(evidence),
        "root_cause_confirmed": False,
    }

    if failure_type == "false_abstention":
        base.update({
            "cluster": "false_abstention",
            "root_cause_hypothesis": (
                "The system abstained on an answerable question. "
                "The recorded response contains no evidence, so retrieval "
                "failure is a hypothesis, not a confirmed cause."
                if not evidence else
                "The system abstained despite evidence being recorded. "
                "Investigate the abstention decision and evidence relevance."
            ),
        })

    elif failure_type == "failure_to_correct_false_premise":
        base.update({
            "cluster": "false_premise_handling",
            "root_cause_hypothesis": (
                "The system abstained instead of correcting the false premise. "
                "Check whether the relevant corrective evidence was retrieved."
            ),
        })

    elif failure_type == "incorrect_answer":
        if "revenue" in question.lower():
            base.update({
                "cluster": "wrong_fact_or_metric_selection",
                "root_cause_hypothesis": (
                    "Possible confusion between total consolidated revenue "
                    "and Intel Products segment revenue. Inspect retrieved "
                    "chunks and answer-generation logic."
                ),
            })
        else:
            base.update({
                "cluster": "incorrect_answer",
                "root_cause_hypothesis": (
                    "The generated answer did not match the reference. "
                    "Inspect evidence relevance and answer generation."
                ),
            })

    elif failure_type == "failure_to_abstain":
        base.update({
            "cluster": "failure_to_abstain",
            "root_cause_hypothesis": (
                "The system answered a question labelled unanswerable. "
                "Check whether it made an unsupported inference or "
                "mistook partial evidence for sufficient evidence."
            ),
        })

    # Keep the observed behavior for auditing.
    base.update({
        "id": result.get("id"),
        "category": result.get("category"),
        "question": question,
        "expected_behavior": result.get("expected_behavior"),
        "expected_answer": result.get("expected_answer"),
        "actual_answer": answer,
        "abstained": abstained,
        "confidence": actual.get("confidence"),
        "abstention_reason": actual.get("abstention_reason"),
        "retrieved_evidence": evidence,
        "page_numbers": actual.get("page_numbers", []),
        "score_reason": score.get("reason"),
        "status": score.get("status"),
    })

    return base


def main():
    parser = argparse.ArgumentParser(
        description="Cluster QA evaluation failures using recorded evidence."
    )
    parser.add_argument("--results", default="results.jsonl")
    parser.add_argument("--scores", default="scores.jsonl")
    parser.add_argument("--output", default="failure_clusters.jsonl")
    parser.add_argument("--report", default="failure_cluster_report.md")
    args = parser.parse_args()

    results = load_jsonl(args.results)
    scores = load_jsonl(args.scores)

    result_by_id = {item["id"]: item for item in results}
    score_by_id = {item["id"]: item for item in scores}

    failures = []
    missing_results = []

    for case_id, score in score_by_id.items():
        if score.get("status") != "FAIL":
            continue

        result = result_by_id.get(case_id)
        if result is None:
            missing_results.append(case_id)
            continue

        failures.append(classify_failure(score, result))

    failures.sort(key=lambda item: item["id"])
    counts = Counter(item["cluster"] for item in failures)

    output_path = Path(args.output)
    with output_path.open("w", encoding="utf-8") as file:
        for item in failures:
            file.write(json.dumps(item, ensure_ascii=False) + "\n")

    lines = [
        "# Failure Clustering Report",
        "",
        f"- Scored failures: {len(failures)}",
        "- Method: deterministic, rule-based preliminary clustering",
        "- Root causes: hypotheses, not confirmed without retrieval traces",
        "",
        "## Cluster distribution",
        "",
        "| Cluster | Cases |",
        "|---|---:|",
    ]

    for cluster, count in sorted(counts.items()):
        lines.append(f"| `{cluster}` | {count} |")

    lines.extend(["", "## Case-level findings", ""])

    for item in failures:
        lines.extend([
            f"### {item['id']} — `{item['cluster']}`",
            "",
            f"- Category: {item.get('category')}",
            f"- Observed failure: `{item.get('observed_failure')}`",
            f"- Question: {item.get('question')}",
            f"- Abstained: {item.get('abstained')}",
            f"- Confidence: {item.get('confidence')}",
            f"- Evidence recorded: {item.get('evidence_available')}",
            f"- Root-cause hypothesis: {item.get('root_cause_hypothesis')}",
            "",
        ])

    if missing_results:
        lines.extend([
            "## Missing result records",
            "",
            ", ".join(missing_results),
            "",
        ])

    Path(args.report).write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print("===== FAILURE CLUSTERING SUMMARY =====")
    print(f"Failures clustered: {len(failures)}")
    for cluster, count in sorted(counts.items()):
        print(f"{cluster}: {count}")

    print(f"\nSaved detailed clusters: {output_path.resolve()}")
    print(f"Saved report: {Path(args.report).resolve()}")


if __name__ == "__main__":
    main()
