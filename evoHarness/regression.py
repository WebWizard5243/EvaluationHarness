
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_jsonl(path):
    path = Path(path)
    rows = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}, line {line_no}: {exc}") from exc
    return rows


def by_id(rows, label):
    result = {}
    for row in rows:
        cid = str(row.get("id", "")).strip()
        if not cid:
            raise ValueError(f"{label} contains a row without an id.")
        if cid in result:
            raise ValueError(f"{label} contains duplicate id {cid}.")
        result[cid] = row
    return result


def score_status(row):
    if row is None:
        return "MISSING"
    return str(row.get("status") or "UNKNOWN").upper()


def response(result):
    return (result or {}).get("actual_response") or {}


def metric_summary(scores):
    statuses = Counter(score_status(s) for s in scores.values())
    total = len(scores)
    passes = statuses.get("PASS", 0)
    fails = statuses.get("FAIL", 0) + statuses.get("FAILED", 0)
    return {
        "total_scored": total,
        "pass": passes,
        "fail": fails,
        "review_or_other": total - passes - fails,
        "pass_rate": round(passes / total, 4) if total else None,
        "status_counts": dict(statuses),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-dir", default="baseline")
    p.add_argument("--baseline-results", default=None)
    p.add_argument("--baseline-scores", default=None)
    p.add_argument("--candidate-results", default="results.jsonl")
    p.add_argument("--candidate-scores", default="scores.jsonl")
    p.add_argument("--dataset", default="test_dataset.json")
    p.add_argument("--baseline-hallucinations", default=None)
    p.add_argument("--candidate-hallucinations", default=None)
    p.add_argument("--report", default="regression_report.md")
    p.add_argument("--json-out", default="regression_comparison.json")
    args = p.parse_args()

    base_dir = Path(args.baseline_dir)
    br_path = Path(args.baseline_results) if args.baseline_results else base_dir / "results.jsonl"
    bs_path = Path(args.baseline_scores) if args.baseline_scores else base_dir / "scores.jsonl"
    br_rows, bs_rows = load_jsonl(br_path), load_jsonl(bs_path)
    cr_rows, cs_rows = load_jsonl(args.candidate_results), load_jsonl(args.candidate_scores)
    base_r, base_s = by_id(br_rows, "baseline results"), by_id(bs_rows, "baseline scores")
    cand_r, cand_s = by_id(cr_rows, "candidate results"), by_id(cs_rows, "candidate scores")

    dataset_obj = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    if isinstance(dataset_obj, dict):
        cases = next((dataset_obj[k] for k in ("cases", "test_cases", "data") if isinstance(dataset_obj.get(k), list)), None)
        if cases is None:
            raise ValueError("Dataset object must contain a cases/test_cases/data list.")
    elif isinstance(dataset_obj, list):
        cases = dataset_obj
    else:
        raise ValueError("Dataset must be a JSON list or object containing a list.")
    category_by_id = {str(c["id"]): str(c.get("category") or "unknown") for c in cases if c.get("id") is not None}

    base_ids, cand_ids = set(base_s), set(cand_s)
    missing_candidate = sorted(base_ids - cand_ids)
    new_candidate = sorted(cand_ids - base_ids)
    common = sorted(base_ids & cand_ids)
    changed_status = []
    regressions = []
    improvements = []
    response_changes = []
    abstention_changes = []
    by_category = defaultdict(lambda: {"baseline_pass": 0, "baseline_fail": 0, "candidate_pass": 0, "candidate_fail": 0, "regressions": 0, "improvements": 0, "cases": 0})

    for cid in common:
        old_status, new_status = score_status(base_s[cid]), score_status(cand_s[cid])
        cat = category_by_id.get(cid, "unknown")
        agg = by_category[cat]
        agg["cases"] += 1
        if old_status == "PASS": agg["baseline_pass"] += 1
        elif old_status in ("FAIL", "FAILED"): agg["baseline_fail"] += 1
        if new_status == "PASS": agg["candidate_pass"] += 1
        elif new_status in ("FAIL", "FAILED"): agg["candidate_fail"] += 1
        item = {"id": cid, "category": cat, "baseline_status": old_status, "candidate_status": new_status}
        if old_status != new_status:
            changed_status.append(item)
        if old_status == "PASS" and new_status in ("FAIL", "FAILED"):
            regressions.append(item); agg["regressions"] += 1
        elif old_status in ("FAIL", "FAILED") and new_status == "PASS":
            improvements.append(item); agg["improvements"] += 1

        old_resp, new_resp = response(base_r.get(cid)), response(cand_r.get(cid))
        old_answer, new_answer = str(old_resp.get("answer") or ""), str(new_resp.get("answer") or "")
        if old_answer.strip() != new_answer.strip():
            response_changes.append({
                **item, "baseline_answer": old_answer, "candidate_answer": new_answer,
                "baseline_abstained": old_resp.get("abstained"), "candidate_abstained": new_resp.get("abstained")
            })
        if old_resp.get("abstained") != new_resp.get("abstained"):
            abstention_changes.append({
                "id": cid, "category": cat,
                "baseline_abstained": old_resp.get("abstained"),
                "candidate_abstained": new_resp.get("abstained")
            })

    base_metrics, cand_metrics = metric_summary(base_s), metric_summary(cand_s)
    comparison = {
        "baseline_files": {"results": str(br_path), "scores": str(bs_path)},
        "candidate_files": {"results": args.candidate_results, "scores": args.candidate_scores},
        "baseline_metrics": base_metrics, "candidate_metrics": cand_metrics,
        "matched_cases": len(common), "baseline_only_ids": missing_candidate,
        "candidate_only_ids": new_candidate, "changed_statuses": changed_status,
        "regressions_pass_to_fail": regressions, "improvements_fail_to_pass": improvements,
        "answer_changes": response_changes, "abstention_changes": abstention_changes,
        "by_category": dict(by_category),
        "interpretation": "Answer changes require review; they are not automatically regressions. PASS-to-FAIL is the primary regression signal."
    }

    if args.baseline_hallucinations and args.candidate_hallucinations:
        bh = by_id(load_jsonl(args.baseline_hallucinations), "baseline hallucinations")
        ch = by_id(load_jsonl(args.candidate_hallucinations), "candidate hallucinations")
        hchanges = []
        for cid in sorted(set(bh) & set(ch)):
            old, new = str(bh[cid].get("status") or "UNKNOWN"), str(ch[cid].get("status") or "UNKNOWN")
            if old != new:
                hchanges.append({"id": cid, "baseline_status": old, "candidate_status": new})
        comparison["hallucination_status_changes"] = hchanges

    Path(args.json_out).write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Regression Test Report", "",
        "## Summary", "",
        f"- Baseline: `{br_path}` and `{bs_path}`",
        f"- Candidate: `{args.candidate_results}` and `{args.candidate_scores}`",
        f"- Cases matched by ID: **{len(common)}**",
        f"- Baseline cases missing from candidate scores: **{len(missing_candidate)}**",
        f"- New candidate score IDs: **{len(new_candidate)}**",
        f"- Baseline pass rate: **{base_metrics['pass_rate'] if base_metrics['pass_rate'] is not None else 'n/a'}** ({base_metrics['pass']}/{base_metrics['total_scored']})",
        f"- Candidate pass rate: **{cand_metrics['pass_rate'] if cand_metrics['pass_rate'] is not None else 'n/a'}** ({cand_metrics['pass']}/{cand_metrics['total_scored']})",
        f"- Status changes: **{len(changed_status)}**",
        f"- Regressions (PASS → FAIL): **{len(regressions)}**",
        f"- Improvements (FAIL → PASS): **{len(improvements)}**",
        f"- Answer text changed: **{len(response_changes)}**",
        f"- Abstention behavior changed: **{len(abstention_changes)}**",
        "", "## Case-level score changes", "",
        "| Case | Category | Baseline | Candidate | Interpretation |",
        "|---|---|---|---|---|",
    ]
    if not changed_status:
        lines.append("| — | — | — | — | No score-status changes |")
    for x in changed_status:
        if x["id"] in {r["id"] for r in regressions}: interp = "Regression"
        elif x["id"] in {r["id"] for r in improvements}: interp = "Improvement"
        else: interp = "Other status change; review"
        lines.append(f"| {x['id']} | {x['category']} | {x['baseline_status']} | {x['candidate_status']} | {interp} |")

    lines += ["", "## Results by input category", "",
              "| Category | Cases | Baseline pass/fail | Candidate pass/fail | Regressions | Improvements |",
              "|---|---:|---:|---:|---:|---:|"]
    for cat, x in sorted(by_category.items()):
        lines.append(f"| {cat} | {x['cases']} | {x['baseline_pass']}/{x['baseline_fail']} | {x['candidate_pass']}/{x['candidate_fail']} | {x['regressions']} | {x['improvements']} |")

    lines += ["", "## Answer changes requiring review", ""]
    if not response_changes:
        lines.append("No answer-text changes.")
    else:
        for x in response_changes:
            lines += [f"### {x['id']} ({x['category']})",
                      f"- Score status: {x['baseline_status']} → {x['candidate_status']}",
                      f"- Baseline abstained: `{x['baseline_abstained']}`; candidate abstained: `{x['candidate_abstained']}`",
                      f"- Baseline answer: {x['baseline_answer'][:500]}",
                      f"- Candidate answer: {x['candidate_answer'][:500]}", ""]

    if comparison.get("hallucination_status_changes") is not None:
        lines += ["", "## Hallucination status changes", ""]
        hchanges = comparison["hallucination_status_changes"]
        lines.append(f"Changed hallucination verdicts: **{len(hchanges)}**")
        for x in hchanges:
            lines.append(f"- {x['id']}: {x['baseline_status']} → {x['candidate_status']}")

    lines += ["", "## Interpretation and limitations", "",
              "- A PASS → FAIL transition is a regression signal; inspect the case before attributing a cause.",
              "- A FAIL → PASS transition is an improvement signal.",
              "- Changed answer text is not automatically a regression: it may be a harmless wording change or a correctness change.",
              "- Compare only runs using the same dataset version, scoring rubric, model/configuration, and source document where possible.",
              "- If model outputs are nondeterministic, rerun ambiguous cases before making strong claims.",
              "- Baseline and candidate files are read-only inputs to this script; it writes only the report and JSON comparison.",
              ""]
    Path(args.report).write_text("\n".join(lines), encoding="utf-8")
    print(f"Matched cases: {len(common)}")
    print(f"Baseline pass rate: {base_metrics['pass_rate']} ({base_metrics['pass']}/{base_metrics['total_scored']})")
    print(f"Candidate pass rate: {cand_metrics['pass_rate']} ({cand_metrics['pass']}/{cand_metrics['total_scored']})")
    print(f"Status changes: {len(changed_status)} | regressions: {len(regressions)} | improvements: {len(improvements)}")
    print(f"Saved: {args.report}")
    print(f"Saved: {args.json_out}")


if __name__ == "__main__":
    main()
