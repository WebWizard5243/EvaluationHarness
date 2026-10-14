
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import failure_clustering as fc


def resolve_path(p_str: Optional[str]) -> Optional[Path]:
    if not p_str:
        return None
    p = Path(p_str)
    return p if p.is_absolute() else (HERE / p)


def run_clustering(
    results_path: Path,
    scores_path: Path,
    dataset_path: Path,
    document_path: Optional[Path] = None,
    top_k: int = 10,
    output_summary_path: Optional[Path] = None,
    output_report_path: Optional[Path] = None,
    output_jsonl_path: Optional[Path] = None,
) -> dict:
    results = fc.jsonl(results_path)
    scores = fc.jsonl(scores_path)
    cases = fc.read_cases(dataset_path)

    by_result = {str(x.get("id")): x for x in results if x.get("id") is not None}
    by_score = {str(x.get("id")): x for x in scores if x.get("id") is not None}
    by_case = {str(x.get("id")): x for x in cases if x.get("id") is not None}

    def is_fail(s):
        status = str(s.get("status", "")).lower()
        return status in {
            "fail", "failed", "false_abstention", "incorrect_answer",
            "failure_to_abstain", "failure_to_correct_false_premise"
        } or (s.get("passed") is False or s.get("is_correct") is False)

    failed_ids = sorted({cid for cid, score in by_score.items() if is_fail(score)})

    pdf = fc.get_doc(str(document_path) if document_path else None)
    processed = None
    if pdf:
        try:
            processed, _ = fc.build_index(pdf, top_k)
        except Exception as exc:
            print(f"[WARN] Live retrieval diagnostic unavailable: {exc}")
    else:
        print("[WARN] Source PDF not found; live retrieval diagnostics skipped.")

    diagnostics_rows = []
    for cid in failed_ids:
        result = by_result.get(cid, {})
        score = by_score[cid]
        case = by_case.get(cid, {})
        actual = result.get("actual_response") or {}

        question = str(case.get("question") or result.get("question") or "")
        expected = case.get("expected_answer") or result.get("expected_answer") or ""

        chunks, indexed_matches = [], []
        if processed is not None:
            chunks = processed.retrieve(query=question, top_k=top_k)
            for c in processed.chunks:
                found, clue = fc.clue_match(c.text, expected)
                if found:
                    indexed_matches.append({
                        "page": c.page_number,
                        "chunk_id": c.chunk_id,
                        "matched_clue": clue,
                        "text_excerpt": c.text[:1200],
                    })

        retrieved_text = "\n".join(c.text for c in chunks)
        top_match, top_clue = fc.clue_match(retrieved_text, expected) if processed is not None else (None, None)
        index_match = bool(indexed_matches) if processed is not None else None
        abstained = actual.get("abstained")
        error = result.get("error")
        failure_type = str(score.get("failure_type") or score.get("failure_mode") or
                           score.get("status") or "unknown").lower()

        abstention_for_diagnostics = abstained
        if abstention_for_diagnostics is None and "false_abstention" in failure_type:
            abstention_for_diagnostics = True

        expected_behavior = str(case.get("expected_behavior") or result.get("expected_behavior") or "").lower()

        if error:
            pattern = "execution_error"
            observation = "Evaluation recorded an execution error."
        elif processed is None:
            pattern = "trace_unavailable"
            observation = "No live retrieval trace was collected; cause cannot be localized."
        elif index_match and top_match is False:
            pattern = "indexed_answer_clue_missing_from_top_k"
            observation = (
                "An expected-answer clue occurs in the indexed corpus but not in top-k; "
                "consistent with a retrieval miss. The scorer labels this as a false abstention."
                if abstention_for_diagnostics else
                "An expected-answer clue occurs in the indexed corpus but not in top-k; "
                "this is a retrieval miss signal, though the raw abstention field does not confirm abstention."
            )
        elif top_match and abstention_for_diagnostics:
            pattern = "answer_clue_in_top_k_but_abstained"
            observation = "An expected-answer clue occurs in retrieved text although the QA response abstained."
        elif abstention_for_diagnostics is False and (
            failure_type == "failure_to_abstain" or expected_behavior == "abstain"
        ):
            pattern = "answered_when_abstention_expected"
            observation = "The system answered a case whose expected behavior was abstention."
        elif (
            "false_premise" in failure_type
            or "correct_false_premise" in failure_type
            or expected_behavior == "correct_false_premise"
        ):
            pattern = "false_premise_not_corrected"
            observation = "Scorer marked false-premise correction as failed; inspect whether corrective evidence was retrieved and used."
        elif index_match is False:
            pattern = "expected_answer_clue_not_found_in_index"
            observation = "No lexical/numeric clue for the expected answer was found in indexed chunks; extraction/annotation/semantic matching need review."
        else:
            pattern = "other_or_ambiguous"
            observation = "Current diagnostics do not isolate a more specific mechanism."

        diagnostics_rows.append({
            "id": cid,
            "category": case.get("category") or result.get("category"),
            "question": question,
            "expected_behavior": case.get("expected_behavior"),
            "expected_answer": expected,
            "actual_answer": actual.get("answer"),
            "abstained": abstained,
            "confidence": actual.get("confidence"),
            "abstention_reason": actual.get("abstention_reason"),
            "score_status": score.get("status"),
            "failure_type": failure_type,
            "score_reason": score.get("reason") or score.get("explanation") or score.get("details"),
            "retrieval_diagnostic_available": processed is not None,
            "expected_answer_clue_found_in_index": index_match,
            "indexed_match_pages": sorted({x["page"] for x in indexed_matches}),
            "indexed_matches": indexed_matches[:10],
            "expected_answer_clue_in_top_k": top_match,
            "top_k_match_clue": top_clue,
            "retrieved_pages": [c.page_number for c in chunks],
            "retrieved_chunks": [
                {"page": c.page_number, "chunk_id": c.chunk_id, "text_excerpt": c.text[:1800]}
                for c in chunks
            ],
            "diagnostic_pattern": pattern,
            "diagnostic_observation": observation,
            "root_cause_confirmed": False,
        })

    if output_jsonl_path:
        out_jsonl = Path(output_jsonl_path).resolve()
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with out_jsonl.open("w", encoding="utf-8") as f:
            for row in diagnostics_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    groups = defaultdict(list)
    for row in diagnostics_rows:
        key = (row["diagnostic_pattern"], str(row["expected_behavior"]))
        groups[key].append(row)

    clusters_list = []
    for (pattern, exp_beh), members in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        categories = sorted({str(m.get("category")) for m in members})
        case_ids = [m["id"] for m in members]
        case_details = []
        for m in members:
            case_details.append({
                "id": m["id"],
                "category": m["category"],
                "question": m["question"],
                "expected_behavior": m["expected_behavior"],
                "expected_answer": m["expected_answer"],
                "actual_answer": m["actual_answer"],
                "abstained": m["abstained"],
                "confidence": m["confidence"],
                "score_status": m["score_status"],
                "failure_type": m["failure_type"],
                "score_reason": m["score_reason"],
                "diagnostic_observation": m["diagnostic_observation"],
                "retrieved_pages": m["retrieved_pages"],
            })

        clusters_list.append({
            "name": pattern,
            "expected_behavior": exp_beh,
            "count": len(members),
            "case_ids": case_ids,
            "categories": categories,
            "cases": case_details,
        })

    summary_data = {
        "total_failed": len(diagnostics_rows),
        "num_clusters": len(clusters_list),
        "clusters": clusters_list,
    }

    if output_summary_path:
        summary_p = Path(output_summary_path).resolve()
        summary_p.parent.mkdir(parents=True, exist_ok=True)
        summary_p.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")

    if output_report_path:
        counts = Counter(row["diagnostic_pattern"] for row in diagnostics_rows)
        lines = [
            "# Evidence-Driven Failure Cluster Report", "",
            f"- Failed cases analyzed: **{len(diagnostics_rows)}**",
            f"- Live retrieval diagnostics: **{'available' if processed is not None else 'unavailable'}**",
            f"- Top-k: **{top_k}**",
            "- Candidate clusters are based on observed diagnostic signatures, not causal proof.",
            "- Lexical/numeric matching is heuristic: a miss does not prove semantic absence.",
            "", "## Diagnostic pattern counts", ""
        ]
        lines += [f"- `{k}`: **{v}** case(s)" for k, v in counts.most_common()]
        lines += ["", "## Candidate behavioral clusters", ""]
        for i, cluster in enumerate(clusters_list, 1):
            pattern = cluster["name"]
            exp_beh = cluster["expected_behavior"]
            cats = ", ".join(cluster["categories"])
            lines += [
                f"### Cluster {i}: `{pattern}`", "",
                f"- Cases: {', '.join(cluster['case_ids'])}",
                f"- Expected behavior: `{exp_beh}`",
                f"- Dataset categories represented: `{cats}`", ""
            ]
            for m in cluster["cases"]:
                lines += [
                    f"**{m['id']} — {m['question']}**",
                    f"- Scoring label: `{m['failure_type']}`; abstained: `{m['abstained']}`.",
                    f"- Observation: {m['diagnostic_observation']}",
                    f"- Retrieved pages: `{m['retrieved_pages']}`.",
                ]
                if m.get("score_reason"):
                    lines.append(f"- Scorer explanation: {str(m['score_reason'])[:400]}")
                lines.append("")

        lines += [
            "## Per-case summary", "",
            "| Case | Scoring label | Diagnostic pattern | Retrieved pages |",
            "|---|---|---|---|"
        ]
        for r in diagnostics_rows:
            lines.append(
                f"| {r['id']} | `{r['failure_type']}` | `{r['diagnostic_pattern']}` | `{r['retrieved_pages']}` |"
            )

        report_p = Path(output_report_path).resolve()
        report_p.parent.mkdir(parents=True, exist_ok=True)
        report_p.write_text("\n".join(lines), encoding="utf-8")

    return summary_data


def main():
    parser = argparse.ArgumentParser(description="Failure clustering and diagnostics.")
    parser.add_argument("--results", default="results.jsonl", help="Path to results.jsonl")
    parser.add_argument("--scores", default="scores.jsonl", help="Path to scores.jsonl")
    parser.add_argument("--dataset", default="test_dataset.json", help="Path to test_dataset.json")
    parser.add_argument("--document", default=None, help="Path to document PDF")
    parser.add_argument("--top-k", type=int, default=10, help="Top-K for retrieval check")
    parser.add_argument("--output-summary", default="cluster_summary.json", help="Output path for cluster_summary.json")
    parser.add_argument("--output-report", default="failure_cluster_report.md", help="Output path for report markdown")
    parser.add_argument("--output-jsonl", default="failure_diagnostics.jsonl", help="Output path for diagnostics JSONL")
    args = parser.parse_args()

    summary = run_clustering(
        results_path=resolve_path(args.results),
        scores_path=resolve_path(args.scores),
        dataset_path=resolve_path(args.dataset),
        document_path=resolve_path(args.document),
        top_k=args.top_k,
        output_summary_path=resolve_path(args.output_summary),
        output_report_path=resolve_path(args.output_report),
        output_jsonl_path=resolve_path(args.output_jsonl),
    )

    print(f"\n[INFO] Clustering completed: {summary['total_failed']} failed case(s) across {summary['num_clusters']} cluster(s).")
    for cl in summary["clusters"]:
        print(f"  - {cl['name']} ({cl['expected_behavior']}): {cl['count']} case(s) -> {', '.join(cl['case_ids'])}")
    if args.output_summary:
        print(f"Saved cluster summary to: {resolve_path(args.output_summary)}")


if __name__ == "__main__":
    main()
