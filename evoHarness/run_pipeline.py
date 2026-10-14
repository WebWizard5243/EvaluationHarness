
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent


# ── Utility Helpers ──────────────────────────────────────────────────────────


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                records.append(json.loads(line_str))
            except json.JSONDecodeError as exc:
                print(f"[WARN] Bad JSON in {path}:{line_no}: {exc}", file=sys.stderr)
    return records


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[WARN] Failed to load JSON from {path}: {exc}", file=sys.stderr)
        return None


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp_{os.getpid()}")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


# ── Subprocess Execution & Logging ───────────────────────────────────────────


def run_stage(
    stage_name: str,
    cmd: List[Any],
    log_path: Path,
    cwd: Path = HERE,
) -> Tuple[int, float, str]:
    """Execute a subprocess command, streaming output to terminal and saving to log_path."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    str_cmd = [str(x) for x in cmd]
    print(f"\n{'='*70}\n[STAGE] Starting {stage_name}...\nCommand: {' '.join(str_cmd)}\n{'='*70}", flush=True)

    start_time = time.time()
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"=== {stage_name} ===\n")
        log_file.write(f"Start: {dt.datetime.now().isoformat()}\n")
        log_file.write(f"Command: {' '.join(str_cmd)}\n\n")
        log_file.flush()

        process = subprocess.Popen(
            str_cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log_file.write(line)
            log_file.flush()

        process.wait()
        duration = time.time() - start_time
        exit_code = process.returncode

        log_file.write(f"\nEnd: {dt.datetime.now().isoformat()}\n")
        log_file.write(f"Exit code: {exit_code}\n")
        log_file.write(f"Duration: {duration:.2f}s\n")

    return exit_code, duration, str(log_path.relative_to(HERE))


# ── Metric Calculators ───────────────────────────────────────────────────────


def compute_evaluation_metrics(
    scores_path: Path,
    dataset_path: Path,
) -> Dict[str, Any]:
    scores = load_jsonl(scores_path)
    if not scores:
        return {
            "total_scored": 0,
            "pass_count": 0,
            "fail_count": 0,
            "review_count": 0,
            "pass_rate": None,
            "categories": {},
            "failure_types": {},
        }

    dataset_cases = {}
    if dataset_path.is_file():
        try:
            raw_cases = json.loads(dataset_path.read_text(encoding="utf-8"))
            if isinstance(raw_cases, dict):
                for k in ("cases", "test_cases", "data"):
                    if isinstance(raw_cases.get(k), list):
                        raw_cases = raw_cases[k]
                        break
            if isinstance(raw_cases, list):
                for c in raw_cases:
                    if "id" in c:
                        dataset_cases[str(c["id"])] = c
        except Exception:
            pass

    statuses = Counter()
    by_category = defaultdict(lambda: Counter())
    failure_types = Counter()

    for s in scores:
        cid = str(s.get("id"))
        st = str(s.get("status", "UNKNOWN")).upper()
        if st not in ("PASS", "FAIL", "REVIEW"):
            st = "FAIL" if "FAIL" in st else ("PASS" if "PASS" in st else "REVIEW")
        statuses[st] += 1

        cat = (dataset_cases.get(cid) or {}).get("category") or s.get("category") or "unknown"
        by_category[cat][st] += 1
        by_category[cat]["TOTAL"] += 1

        ft = s.get("failure_type") or s.get("failure_mode")
        if ft:
            failure_types[str(ft)] += 1

    total = len(scores)
    pass_cnt = statuses.get("PASS", 0)
    fail_cnt = statuses.get("FAIL", 0)
    rev_cnt = statuses.get("REVIEW", 0)
    pass_rate = round(pass_cnt / total, 4) if total > 0 else 0.0

    cat_metrics = {}
    for cat, counts in sorted(by_category.items()):
        cat_total = counts["TOTAL"]
        cat_pass = counts["PASS"]
        cat_metrics[cat] = {
            "total": cat_total,
            "pass": cat_pass,
            "fail": counts["FAIL"],
            "review": counts["REVIEW"],
            "pass_rate": round(cat_pass / cat_total, 4) if cat_total > 0 else 0.0,
        }

    return {
        "total_scored": total,
        "pass_count": pass_cnt,
        "fail_count": fail_cnt,
        "review_count": rev_cnt,
        "pass_rate": pass_rate,
        "categories": cat_metrics,
        "failure_types": dict(sorted(failure_types.items())),
    }


def compute_hallucination_metrics(hallucination_path: Path) -> Dict[str, Any]:
    records = load_jsonl(hallucination_path)
    if not records:
        return {"total_checked": 0, "counts": {}}

    counts = Counter(r.get("status", "UNKNOWN") for r in records)
    return {
        "total_checked": len(records),
        "counts": dict(sorted(counts.items())),
    }


# ── Markdown Document Builders ──────────────────────────────────────────────


def build_pipeline_summary_markdown(run_summary: Dict[str, Any], include_marker: bool = False) -> str:
    """Build the markdown summary report for a single pipeline run."""
    run_id = run_summary["run_id"]
    lines = []

    if include_marker:
        lines.append(f"<!-- RUN_START: {run_id} -->")

    lines.append(f"# Pipeline Run Summary: `{run_id}`")
    lines.append("")
    lines.append(f"- **Timestamp:** {run_summary['timestamp']}")
    lines.append(f"- **Overall Pipeline Status:** **{run_summary['pipeline_status']}**")
    lines.append(f"- **Total Duration:** {format_duration(run_summary['total_duration_seconds'])}")
    lines.append(f"- **Dataset:** `{run_summary['dataset']}` ({run_summary['test_case_count']} cases)")
    lines.append(f"- **Run Directory:** `{run_summary['run_dir']}`")
    lines.append("")

    # Stage Execution Table
    lines.append("## Stage Execution")
    lines.append("")
    lines.append("| Stage | Status | Duration | Exit Code | Output Artifact |")
    lines.append("| :--- | :---: | :---: | :---: | :--- |")
    for stage in run_summary.get("stages", []):
        st = stage.get("status", "UNKNOWN")
        st_badge = f"**{st}**"
        dur = format_duration(stage.get("duration_seconds", 0.0))
        ec = stage.get("exit_code", "-")
        art = stage.get("output_path") or "-"
        lines.append(f"| `{stage.get('name')}` | {st_badge} | {dur} | `{ec}` | `{art}` |")
    lines.append("")

    # Evaluation & Category Metrics
    eval_m = run_summary.get("metrics", {}).get("evaluation", {})
    if eval_m.get("total_scored", 0) > 0:
        lines.append("## Accuracy & Category Breakdown")
        lines.append("")
        lines.append(f"- **Overall Pass Rate:** **{eval_m.get('pass_rate', 0.0):.1%}** ({eval_m.get('pass_count')}/{eval_m.get('total_scored')} cases)")
        lines.append(f"- **Fail:** {eval_m.get('fail_count')} | **Review:** {eval_m.get('review_count')}")
        lines.append("")
        lines.append("| Category | Total | Pass | Fail | Review | Pass Rate |")
        lines.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
        for cat, cm in eval_m.get("categories", {}).items():
            lines.append(
                f"| `{cat}` | {cm['total']} | {cm['pass']} | {cm['fail']} | {cm['review']} | {cm['pass_rate']:.1%} |"
            )
        lines.append("")

        if eval_m.get("failure_types"):
            lines.append("### Failure Distribution")
            lines.append("")
            for ft, count in eval_m.get("failure_types", {}).items():
                lines.append(f"- `{ft}`: **{count}** case(s)")
            lines.append("")

    # Hallucination Summary
    hal_m = run_summary.get("metrics", {}).get("hallucination", {})
    if hal_m.get("total_checked", 0) > 0:
        lines.append("## Hallucination Evaluation")
        lines.append("")
        lines.append(f"- **Total Cases Evaluated:** {hal_m['total_checked']}")
        counts_str = ", ".join(f"`{k}`: {v}" for k, v in hal_m.get("counts", {}).items())
        lines.append(f"- **Status Counts:** {counts_str}")
        lines.append("")

    # Calibration Summary
    cal_m = run_summary.get("metrics", {}).get("calibration", {})
    if cal_m.get("answered_and_scored_cases") is not None:
        lines.append("## Confidence Calibration")
        lines.append("")
        lines.append(f"- **Answered & Scored Cases:** {cal_m.get('answered_and_scored_cases')}")
        brier = f"{cal_m.get('brier_score'):.4f}" if cal_m.get("brier_score") is not None else "N/A"
        ece = f"{cal_m.get('expected_calibration_error'):.4f}" if cal_m.get("expected_calibration_error") is not None else "N/A"
        lines.append(f"- **Brier Score:** `{brier}`")
        lines.append(f"- **Expected Calibration Error (ECE):** `{ece}`")
        if cal_m.get("plot_path"):
            lines.append(f"- **Reliability Diagram:** `{cal_m.get('plot_path')}`")
        lines.append("")

    # Clustering Summary
    cl_m = run_summary.get("metrics", {}).get("clustering", {})
    if cl_m.get("status") is not None:
        lines.append("## Failure Clustering")
        lines.append("")
        lines.append(f"- **Status:** `{cl_m.get('status')}`")
        lines.append(f"- **Failed Cases Analyzed:** {cl_m.get('total_failed', 0)}")
        lines.append(f"- **Clusters Found:** {cl_m.get('num_clusters', 0)}")
        lines.append(f"- **Per-Run Cluster Summary:** `{cl_m.get('summary_path') or '-'}`")

        if cl_m.get("cluster_highlights"):
            lines.append("")
            lines.append("| Cluster Name | Expected Behavior | Failures | Case IDs |")
            lines.append("| :--- | :--- | :---: | :--- |")
            for ch in cl_m.get("cluster_highlights", []):
                lines.append(f"| `{ch['name']}` | `{ch['expected_behavior']}` | {ch['count']} | {', '.join(ch['case_ids'][:8])} |")
        lines.append("")

    # Errors & Warnings
    warnings = run_summary.get("warnings", [])
    errors = run_summary.get("errors", [])
    if warnings or errors:
        lines.append("## Warnings & Errors")
        lines.append("")
        for w in warnings:
            lines.append(f"- ⚠️ **Warning:** {w}")
        for e in errors:
            lines.append(f"- ❌ **Error:** {e}")
        lines.append("")

    if include_marker:
        lines.append(f"<!-- RUN_END: {run_id} -->")

    return "\n".join(lines)


def build_cluster_failure_markdown(run_id: str, timestamp: str, cluster_summary: Dict[str, Any], include_marker: bool = False) -> str:
    """Build the markdown failure cluster analysis report for a single run."""
    lines = []
    if include_marker:
        lines.append(f"<!-- CLUSTER_START: {run_id} -->")

    lines.append(f"# Failure Clustering Report: `{run_id}`")
    lines.append("")
    lines.append(f"- **Run ID:** `{run_id}`")
    lines.append(f"- **Timestamp:** {timestamp}")
    total_failed = cluster_summary.get("total_failed", 0)
    num_clusters = cluster_summary.get("num_clusters", 0)
    lines.append(f"- **Total Failed Cases:** **{total_failed}**")
    lines.append(f"- **Number of Clusters:** **{num_clusters}**")
    lines.append("")

    if total_failed == 0:
        lines.append("🎉 **No failures detected in this evaluation run.**")
        lines.append("")
    else:
        lines.append("## Cluster Overview")
        lines.append("")
        lines.append("| # | Cluster Name | Expected Behavior | Count | Represented Categories | Affected Cases |")
        lines.append("| :---: | :--- | :--- | :---: | :--- | :--- |")
        for i, cl in enumerate(cluster_summary.get("clusters", []), 1):
            cats = ", ".join(cl.get("categories", []))
            cids = ", ".join(cl.get("case_ids", []))
            lines.append(f"| {i} | `{cl.get('name')}` | `{cl.get('expected_behavior')}` | {cl.get('count')} | {cats} | {cids} |")
        lines.append("")

        lines.append("## Detailed Cluster Diagnoses")
        lines.append("")
        for i, cl in enumerate(cluster_summary.get("clusters", []), 1):
            lines.append(f"### Cluster {i}: `{cl.get('name')}`")
            lines.append(f"- **Expected Behavior:** `{cl.get('expected_behavior')}`")
            lines.append(f"- **Affected Cases ({cl.get('count')}):** {', '.join(cl.get('case_ids', []))}")
            lines.append("")
            for case in cl.get("cases", []):
                lines.append(f"**{case.get('id')} — {case.get('question')}**")
                lines.append(f"- **Scoring Label:** `{case.get('failure_type')}` | **Abstained:** `{case.get('abstained')}`")
                lines.append(f"- **Diagnostic Observation:** {case.get('diagnostic_observation')}")
                if case.get("retrieved_pages"):
                    lines.append(f"- **Retrieved Pages:** `{case.get('retrieved_pages')}`")
                if case.get("expected_answer"):
                    lines.append(f"- **Expected Answer:** `{case.get('expected_answer')}`")
                if case.get("actual_answer"):
                    lines.append(f"- **Actual Answer:** {case.get('actual_answer')[:300]}")
                if case.get("score_reason"):
                    lines.append(f"- **Scorer Reason:** {str(case.get('score_reason'))[:300]}")
                lines.append("")

    if include_marker:
        lines.append(f"<!-- CLUSTER_END: {run_id} -->")

    return "\n".join(lines)


# ── Consolidated Markdown Updaters ──────────────────────────────────────────


def update_consolidated_pipeline_summary(
    summary_path: Path,
    run_summary: Dict[str, Any],
) -> None:
    """Prepend or update the run's entry in runs/pipeline_summary.md (newest first)."""
    run_id = run_summary["run_id"]
    marker_start = f"<!-- RUN_START: {run_id} -->"
    marker_end = f"<!-- RUN_END: {run_id} -->"

    new_run_block = build_pipeline_summary_markdown(run_summary, include_marker=True)

    existing_content = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else ""
    header = "# Consolidated Evaluation Pipeline Summary\n\nThis document tracks the execution history and metrics of all evaluation pipeline runs.\n\n"

    if marker_start in existing_content and marker_end in existing_content:
        start_idx = existing_content.index(marker_start)
        end_idx = existing_content.index(marker_end) + len(marker_end)
        updated_content = existing_content[:start_idx] + new_run_block + existing_content[end_idx:]
    else:
        if existing_content.startswith("# Consolidated Evaluation Pipeline Summary"):
            parts = existing_content.split("\n\n", 2)
            if len(parts) >= 2:
                prefix = parts[0] + "\n\n" + parts[1] + "\n\n"
                rest = parts[2] if len(parts) > 2 else ""
                updated_content = prefix + new_run_block + "\n\n---\n\n" + rest
            else:
                updated_content = header + new_run_block + "\n\n---\n\n" + existing_content
        else:
            updated_content = header + new_run_block + ("\n\n---\n\n" + existing_content if existing_content else "\n")

    atomic_write_text(summary_path, updated_content.strip() + "\n")


def update_consolidated_cluster_failure(
    cluster_md_path: Path,
    run_id: str,
    timestamp: str,
    cluster_summary: Dict[str, Any],
) -> None:
    """Prepend or update run failure cluster analysis in runs/cluster_failure.md."""
    marker_start = f"<!-- CLUSTER_START: {run_id} -->"
    marker_end = f"<!-- CLUSTER_END: {run_id} -->"

    new_cluster_block = build_cluster_failure_markdown(run_id, timestamp, cluster_summary, include_marker=True)

    existing_content = cluster_md_path.read_text(encoding="utf-8") if cluster_md_path.is_file() else ""
    header = "# Consolidated Failure Clustering Report\n\nDetailed failure diagnostic analysis and behavioral clusters across evaluation pipeline runs.\n\n"

    if marker_start in existing_content and marker_end in existing_content:
        start_idx = existing_content.index(marker_start)
        end_idx = existing_content.index(marker_end) + len(marker_end)
        updated_content = existing_content[:start_idx] + new_cluster_block + existing_content[end_idx:]
    else:
        if existing_content.startswith("# Consolidated Failure Clustering Report"):
            parts = existing_content.split("\n\n", 2)
            if len(parts) >= 2:
                prefix = parts[0] + "\n\n" + parts[1] + "\n\n"
                rest = parts[2] if len(parts) > 2 else ""
                updated_content = prefix + new_cluster_block + "\n\n---\n\n" + rest
            else:
                updated_content = header + new_cluster_block + "\n\n---\n\n" + existing_content
        else:
            updated_content = header + new_cluster_block + ("\n\n---\n\n" + existing_content if existing_content else "\n")

    atomic_write_text(cluster_md_path, updated_content.strip() + "\n")


# ── Terminal Output Summary ──────────────────────────────────────────────────


def print_terminal_summary(run_summary: Dict[str, Any]) -> None:
    """Print a clean, prominent consolidated summary in the terminal covering all 4 evaluation areas."""
    run_id = run_summary["run_id"]
    eval_m = run_summary.get("metrics", {}).get("evaluation", {})
    hal_m = run_summary.get("metrics", {}).get("hallucination", {})
    cal_m = run_summary.get("metrics", {}).get("calibration", {})
    cl_m = run_summary.get("metrics", {}).get("clustering", {})

    print(f"\n{'='*75}")
    print(f"PIPELINE RUN COMPLETE — {run_id}")
    print(f"Status:   {run_summary['pipeline_status']}")
    print(f"Duration: {format_duration(run_summary['total_duration_seconds'])}")
    print(f"{'='*75}")

    # 1. SCORING SUMMARY
    print("\n[1] SCORING & ACCURACY SUMMARY")
    print("-" * 75)
    total_scored = eval_m.get("total_scored", 0)
    pass_cnt = eval_m.get("pass_count", 0)
    fail_cnt = eval_m.get("fail_count", 0)
    rev_cnt = eval_m.get("review_count", 0)
    pass_rate = eval_m.get("pass_rate", 0.0) or 0.0

    print(f"Total Cases Scored: {total_scored}")
    print(f"PASS:               {pass_cnt}")
    print(f"FAIL:               {fail_cnt}")
    print(f"REVIEW:             {rev_cnt}")
    print(f"Overall Pass Rate:  {pass_rate:.1%}")

    if eval_m.get("categories"):
        print("\nCategory Breakdown:")
        for cat, cm in eval_m["categories"].items():
            print(f"  - {cat:<20}: {cm['pass']}/{cm['total']} passed ({cm['pass_rate']:.1%}) [Fail: {cm['fail']}, Review: {cm['review']}]")

    if eval_m.get("failure_types"):
        print("\nFailure Distribution:")
        for ft, count in eval_m["failure_types"].items():
            print(f"  - {ft:<30}: {count}")

    # 2. HALLUCINATION SUMMARY
    print("\n[2] HALLUCINATION EVALUATION SUMMARY")
    print("-" * 75)
    total_hal = hal_m.get("total_checked", 0)
    print(f"Total Cases Evaluated: {total_hal}")
    if hal_m.get("counts"):
        for verdict, count in hal_m["counts"].items():
            print(f"  - {verdict:<22}: {count}")
    else:
        print("  (No hallucination checks recorded)")

    # 3. CONFIDENCE CALIBRATION SUMMARY
    print("\n[3] CONFIDENCE CALIBRATION SUMMARY")
    print("-" * 75)
    ans_scored = cal_m.get("answered_and_scored_cases")
    if ans_scored is not None:
        brier = f"{cal_m.get('brier_score'):.4f}" if cal_m.get("brier_score") is not None else "N/A"
        ece = f"{cal_m.get('expected_calibration_error'):.4f}" if cal_m.get("expected_calibration_error") is not None else "N/A"
        print(f"Answered & Scored Cases:    {ans_scored}")
        print(f"Brier Score:                {brier}")
        print(f"Expected Calibration Error: {ece}")
        if cal_m.get("plot_path"):
            print(f"Calibration Diagram:        {cal_m.get('plot_path')}")
    else:
        print("  (Confidence calibration metrics unavailable)")

    # 4. FAILURE CLUSTERING SUMMARY
    print("\n[4] FAILURE CLUSTERING SUMMARY")
    print("-" * 75)
    total_fail_analyzed = cl_m.get("total_failed", 0)
    num_cl = cl_m.get("num_clusters", 0)
    print(f"Failed Cases Analyzed:      {total_fail_analyzed}")
    print(f"Clusters Identified:        {num_cl}")
    if cl_m.get("cluster_highlights"):
        print("\nIdentified Behavioral Clusters:")
        for ch in cl_m["cluster_highlights"]:
            cids_str = ", ".join(ch["case_ids"][:10])
            if len(ch["case_ids"]) > 10:
                cids_str += f" (+{len(ch['case_ids']) - 10} more)"
            print(f"  - {ch['name']} (expected: {ch['expected_behavior']}):")
            print(f"      Count: {ch['count']} | Cases: {cids_str}")
    elif total_fail_analyzed == 0:
        print("  🎉 No failures to cluster.")

    print(f"\n{'='*75}")
    print("OUTPUT ARTIFACTS SAVED IN RUN DIRECTORY:")
    print(f"  Per-Run Summary:      {run_summary['run_dir']}/pipeline_summary.md")
    print(f"  Machine-Readable JSON:{run_summary['run_dir']}/pipeline_summary.json")
    print(f"  Cluster Summary JSON: {run_summary['run_dir']}/cluster_summary.json")
    print(f"  Evaluation Results:   {run_summary['run_dir']}/results.jsonl")
    print(f"  Scoring Results:      {run_summary['run_dir']}/scores.jsonl")
    print(f"  Hallucination Results:{run_summary['run_dir']}/hallucination_results.jsonl")
    print(f"  Calibration Results:  {run_summary['run_dir']}/calibration_results.json")
    print(f"{'='*75}\n")


# ── Post-processing Existing Run ─────────────────────────────────────────────


def summarize_existing_run(run_dir: Path, dataset_path: Path = HERE / "test_dataset.json") -> int:
    """Generate per-run and consolidated summaries for an existing run directory."""
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        print(f"[ERROR] Directory does not exist: {run_dir}", file=sys.stderr)
        return 1

    run_id = run_dir.name
    summary_json_path = run_dir / "pipeline_summary.json"
    scores_file = run_dir / "scores.jsonl"
    results_file = run_dir / "results.jsonl"
    hallucination_file = run_dir / "hallucination_results.jsonl"
    calibration_file = run_dir / "calibration_results.json"
    cluster_summary_file = run_dir / "cluster_summary.json"
    cluster_report_file = run_dir / "cluster_report.md"

    run_summary = load_json(summary_json_path) or {}
    if not run_summary:
        timestamp_str = dt.datetime.fromtimestamp(run_dir.stat().st_mtime).isoformat()
        run_summary = {
            "run_id": run_id,
            "timestamp": timestamp_str,
            "pipeline_status": "SUCCESS" if scores_file.is_file() else "INCOMPLETE",
            "total_duration_seconds": 0.0,
            "dataset": dataset_path.name,
            "test_case_count": len(load_jsonl(results_file)),
            "run_dir": str(run_dir.relative_to(HERE) if run_dir.is_relative_to(HERE) else run_dir),
            "stages": [],
            "warnings": [],
            "errors": [],
        }

    # Recompute metrics from available artifacts
    eval_m = compute_evaluation_metrics(scores_file, dataset_path)
    hal_m = compute_hallucination_metrics(hallucination_file)
    cal_data = load_json(calibration_file) or {}
    cluster_summary_data = load_json(cluster_summary_file) or {}

    clustering_metrics = {
        "status": "SUCCESS" if cluster_summary_file.is_file() else "NOT_RUN",
        "summary_path": str(cluster_summary_file.relative_to(HERE)) if cluster_summary_file.is_file() else None,
        "total_failed": cluster_summary_data.get("total_failed", 0),
        "num_clusters": cluster_summary_data.get("num_clusters", 0),
        "cluster_highlights": [
            {
                "name": cl["name"],
                "expected_behavior": cl["expected_behavior"],
                "count": cl["count"],
                "case_ids": cl["case_ids"],
            }
            for cl in cluster_summary_data.get("clusters", [])
        ],
    }

    run_summary["metrics"] = {
        "evaluation": eval_m,
        "hallucination": hal_m,
        "calibration": {
            "answered_and_scored_cases": cal_data.get("answered_and_scored_cases"),
            "brier_score": cal_data.get("brier_score"),
            "expected_calibration_error": cal_data.get("expected_calibration_error"),
            "plot_path": str((run_dir / "calibration_curve.png").relative_to(HERE)) if (run_dir / "calibration_curve.png").is_file() else None,
        },
        "clustering": clustering_metrics,
    }

    # 1. Save per-run markdown summaries inside run_dir
    run_pipeline_md_path = run_dir / "pipeline_summary.md"

    run_pipeline_md_path.write_text(build_pipeline_summary_markdown(run_summary, include_marker=False), encoding="utf-8")

    # 2. Save updated machine-readable JSON inside run_dir
    summary_json_path.write_text(json.dumps(run_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # 4. Print clean terminal summary
    print_terminal_summary(run_summary)
    return 0


# ── Main Pipeline Orchestrator ───────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Full Evaluation Pipeline Runner for Heva AI Assignment 3.")
    parser.add_argument("--dataset", default="test_dataset.json", help="Path to test dataset JSON.")
    parser.add_argument("--doc", default=None, help="Optional source PDF path passed to evaluate.py.")
    parser.add_argument("--limit", "-n", type=int, default=None, help="Limit number of test cases (smoke testing).")
    parser.add_argument("--case-id", "-c", nargs="+", default=None, help="Specific case IDs to evaluate.")
    parser.add_argument("--delay", type=float, default=13.0, help="Delay in seconds between QA queries (default: 13.0).")
    parser.add_argument("--score-delay", type=float, default=4.5, help="Delay in seconds between scoring judge calls (default: 4.5).")
    parser.add_argument("--hallucination-delay", type=float, default=4.5, help="Delay between hallucination judge calls (default: 4.5).")
    parser.add_argument("--no-judge", action="store_true", help="Skip LLM judge in scoring.py (faster, offline check).")
    parser.add_argument("--skip-stages", nargs="+", default=[], help="Stages to skip (e.g. hallucination).")
    parser.add_argument("--summarize", default=None, help="Generate summaries for an existing run directory.")
    args = parser.parse_args()

    if args.summarize:
        return summarize_existing_run(Path(args.summarize), HERE / args.dataset)

    overall_start_time = time.time()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"pipeline_{stamp}"
    timestamp_str = dt.datetime.now().isoformat()

    run_dir = HERE / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    dataset_path = (HERE / args.dataset).resolve() if not Path(args.dataset).is_absolute() else Path(args.dataset)

    results_file = run_dir / "results.jsonl"
    scores_file = run_dir / "scores.jsonl"
    hallucination_file = run_dir / "hallucination_results.jsonl"
    calibration_file = run_dir / "calibration_results.json"
    calibration_plot_file = run_dir / "calibration_curve.png"
    cluster_summary_file = run_dir / "cluster_summary.json"
    cluster_diagnostics_file = run_dir / "failure_diagnostics.jsonl"
    cluster_report_file = run_dir / "cluster_report.md"
    pipeline_summary_json = run_dir / "pipeline_summary.json"
    per_run_pipeline_md = run_dir / "pipeline_summary.md"

    stages_record = []
    warnings = []
    errors = []

    print(f"\n{'#'*75}")
    print(f"# HEVA AI EVALUATION PIPELINE RUNNER — {run_id}")
    print(f"# Destination: {run_dir}")
    print(f"{'#'*75}\n")

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 1: evaluate.py
    # ─────────────────────────────────────────────────────────────────────────
    stage1_name = "evaluate"
    if stage1_name in args.skip_stages:
        stages_record.append({
            "name": stage1_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": 0, "output_path": None, "log_path": None,
        })
        warnings.append("Stage evaluate was skipped by user request.")
    else:
        cmd1 = [sys.executable, HERE / "evaluate.py", "--dataset", str(dataset_path),
                "--output", str(results_file), "--delay", str(args.delay)]
        if args.limit is not None:
            cmd1 += ["--limit", str(args.limit)]
        if args.case_id:
            cmd1 += ["--case-id", *args.case_id]
        if args.doc:
            cmd1 += ["--doc", str(args.doc)]

        ec1, dur1, log1 = run_stage(stage1_name, cmd1, logs_dir / "evaluate.log")
        valid1 = results_file.is_file() and results_file.stat().st_size > 0
        status1 = "SUCCESS" if ec1 == 0 and valid1 else "FAILED"
        if status1 == "FAILED":
            errors.append(f"Stage evaluate failed with exit code {ec1} or missing output.")

        stages_record.append({
            "name": stage1_name,
            "status": status1,
            "duration_seconds": dur1,
            "exit_code": ec1,
            "output_path": str(results_file.relative_to(HERE)) if valid1 else None,
            "log_path": log1,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 2: scoring.py
    # ─────────────────────────────────────────────────────────────────────────
    stage2_name = "scoring"
    if stage2_name in args.skip_stages:
        stages_record.append({
            "name": stage2_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": 0, "output_path": None, "log_path": None,
        })
        warnings.append("Stage scoring was skipped by user request.")
    elif not results_file.is_file() or results_file.stat().st_size == 0:
        stages_record.append({
            "name": stage2_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": -1, "output_path": None, "log_path": None,
        })
        errors.append("Stage scoring skipped because results.jsonl from evaluate is missing.")
    else:
        cmd2 = [sys.executable, HERE / "scoring.py", "--input", str(results_file),
                "--output", str(scores_file), "--delay", str(args.score_delay)]
        if args.no_judge:
            cmd2.append("--no-judge")

        ec2, dur2, log2 = run_stage(stage2_name, cmd2, logs_dir / "scoring.log")
        valid2 = scores_file.is_file() and scores_file.stat().st_size > 0
        status2 = "SUCCESS" if ec2 == 0 and valid2 else "FAILED"
        if status2 == "FAILED":
            errors.append(f"Stage scoring failed with exit code {ec2} or missing output.")

        stages_record.append({
            "name": stage2_name,
            "status": status2,
            "duration_seconds": dur2,
            "exit_code": ec2,
            "output_path": str(scores_file.relative_to(HERE)) if valid2 else None,
            "log_path": log2,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 3: hallucination.py
    # ─────────────────────────────────────────────────────────────────────────
    stage3_name = "hallucination"
    if stage3_name in args.skip_stages:
        stages_record.append({
            "name": stage3_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": 0, "output_path": None, "log_path": None,
        })
        warnings.append("Stage hallucination was skipped by user request.")
    elif not results_file.is_file() or results_file.stat().st_size == 0:
        stages_record.append({
            "name": stage3_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": -1, "output_path": None, "log_path": None,
        })
        errors.append("Stage hallucination skipped because results.jsonl from evaluate is missing.")
    else:
        cmd3 = [sys.executable, HERE / "hallucination.py", "--input", str(results_file),
                "--output", str(hallucination_file), "--delay", str(args.hallucination_delay)]
        if args.limit is not None:
            cmd3 += ["--limit", str(args.limit)]

        ec3, dur3, log3 = run_stage(stage3_name, cmd3, logs_dir / "hallucination.log")
        valid3 = hallucination_file.is_file()
        status3 = "SUCCESS" if ec3 == 0 and valid3 else "FAILED"
        if status3 == "FAILED":
            errors.append(f"Stage hallucination failed with exit code {ec3} or missing output.")

        stages_record.append({
            "name": stage3_name,
            "status": status3,
            "duration_seconds": dur3,
            "exit_code": ec3,
            "output_path": str(hallucination_file.relative_to(HERE)) if valid3 else None,
            "log_path": log3,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 4: calibration.py
    # ─────────────────────────────────────────────────────────────────────────
    stage4_name = "calibration"
    if stage4_name in args.skip_stages:
        stages_record.append({
            "name": stage4_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": 0, "output_path": None, "log_path": None,
        })
        warnings.append("Stage calibration was skipped by user request.")
    elif not results_file.is_file() or not scores_file.is_file():
        stages_record.append({
            "name": stage4_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": -1, "output_path": None, "log_path": None,
        })
        errors.append("Stage calibration skipped because results.jsonl or scores.jsonl is missing.")
    else:
        cmd4 = [sys.executable, HERE / "calibration.py",
                "--results", str(results_file),
                "--scores", str(scores_file),
                "--output", str(calibration_file),
                "--plot", str(calibration_plot_file)]

        ec4, dur4, log4 = run_stage(stage4_name, cmd4, logs_dir / "calibration.log")
        valid4 = calibration_file.is_file()
        status4 = "SUCCESS" if ec4 == 0 and valid4 else "FAILED"
        if status4 == "FAILED":
            errors.append(f"Stage calibration failed with exit code {ec4} or missing output.")

        stages_record.append({
            "name": stage4_name,
            "status": status4,
            "duration_seconds": dur4,
            "exit_code": ec4,
            "output_path": str(calibration_file.relative_to(HERE)) if valid4 else None,
            "log_path": log4,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 5: cluster.py
    # ─────────────────────────────────────────────────────────────────────────
    stage5_name = "cluster"
    cluster_summary_data = None
    if stage5_name in args.skip_stages:
        stages_record.append({
            "name": stage5_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": 0, "output_path": None, "log_path": None,
        })
        warnings.append("Stage cluster was skipped by user request.")
    elif not results_file.is_file() or not scores_file.is_file():
        stages_record.append({
            "name": stage5_name, "status": "SKIPPED", "duration_seconds": 0.0,
            "exit_code": -1, "output_path": None, "log_path": None,
        })
        errors.append("Stage cluster skipped because results.jsonl or scores.jsonl is missing.")
    else:
        cmd5 = [
            sys.executable, HERE / "cluster.py",
            "--results", str(results_file),
            "--scores", str(scores_file),
            "--dataset", str(dataset_path),
            "--output-summary", str(cluster_summary_file),
            "--output-report", str(cluster_report_file),
            "--output-jsonl", str(cluster_diagnostics_file),
        ]
        if args.doc:
            cmd5 += ["--document", str(args.doc)]

        ec5, dur5, log5 = run_stage(stage5_name, cmd5, logs_dir / "cluster.log")
        valid5 = cluster_summary_file.is_file()
        status5 = "SUCCESS" if ec5 == 0 and valid5 else "FAILED"
        if status5 == "FAILED":
            errors.append(f"Stage cluster failed with exit code {ec5} or missing cluster_summary.json.")
        else:
            cluster_summary_data = load_json(cluster_summary_file)

        stages_record.append({
            "name": stage5_name,
            "status": status5,
            "duration_seconds": dur5,
            "exit_code": ec5,
            "output_path": str(cluster_summary_file.relative_to(HERE)) if valid5 else None,
            "log_path": log5,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Pipeline Status Determination
    # ─────────────────────────────────────────────────────────────────────────
    total_pipeline_duration = time.time() - overall_start_time

    critical_stages = [s for s in stages_record if s["name"] in ("evaluate", "scoring")]
    critical_failed = any(s["status"] == "FAILED" for s in critical_stages)
    any_failed = any(s["status"] == "FAILED" for s in stages_record)
    any_skipped = any(s["status"] == "SKIPPED" for s in stages_record)

    if critical_failed:
        overall_status = "FAILED"
    elif any_failed or any_skipped:
        overall_status = "INCOMPLETE"
    else:
        overall_status = "SUCCESS"

    # ─────────────────────────────────────────────────────────────────────────
    # Gather Metrics & Highlights
    # ─────────────────────────────────────────────────────────────────────────
    eval_metrics = compute_evaluation_metrics(scores_file, dataset_path)
    hal_metrics = compute_hallucination_metrics(hallucination_file)
    cal_data = load_json(calibration_file) or {}

    clustering_metrics = {
        "status": next((s["status"] for s in stages_record if s["name"] == "cluster"), "NOT_RUN"),
        "summary_path": str(cluster_summary_file.relative_to(HERE)) if cluster_summary_file.is_file() else None,
        "diagnostics_path": str(cluster_diagnostics_file.relative_to(HERE)) if cluster_diagnostics_file.is_file() else None,
        "total_failed": cluster_summary_data.get("total_failed", 0) if cluster_summary_data else 0,
        "num_clusters": cluster_summary_data.get("num_clusters", 0) if cluster_summary_data else 0,
        "cluster_highlights": [
            {
                "name": cl["name"],
                "expected_behavior": cl["expected_behavior"],
                "count": cl["count"],
                "case_ids": cl["case_ids"],
            }
            for cl in (cluster_summary_data.get("clusters", []) if cluster_summary_data else [])
        ],
    }

    test_case_count = len(load_jsonl(results_file)) or (args.limit if args.limit else 50)

    run_summary_json_data = {
        "run_id": run_id,
        "timestamp": timestamp_str,
        "pipeline_status": overall_status,
        "total_duration_seconds": round(total_pipeline_duration, 2),
        "dataset": str(dataset_path.relative_to(HERE) if dataset_path.is_relative_to(HERE) else dataset_path.name),
        "test_case_count": test_case_count,
        "run_dir": str(run_dir.relative_to(HERE)),
        "stages": stages_record,
        "metrics": {
            "evaluation": eval_metrics,
            "hallucination": hal_metrics,
            "calibration": {
                "answered_and_scored_cases": cal_data.get("answered_and_scored_cases"),
                "brier_score": cal_data.get("brier_score"),
                "expected_calibration_error": cal_data.get("expected_calibration_error"),
                "plot_path": str(calibration_plot_file.relative_to(HERE)) if calibration_plot_file.is_file() else None,
            },
            "clustering": clustering_metrics,
        },
        "reports": {
            "pipeline_summary_md": f"{run_dir.name}/pipeline_summary.md",
        },
        "warnings": warnings,
        "errors": errors,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # Write Per-Run Summaries (Strictly inside run directory)
    # ─────────────────────────────────────────────────────────────────────────
    # 1. Machine-readable JSON in run directory
    pipeline_summary_json.write_text(json.dumps(run_summary_json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Per-run Markdown summary in run directory
    per_run_pipeline_md.write_text(build_pipeline_summary_markdown(run_summary_json_data, include_marker=False), encoding="utf-8")



    # 4. Output clean terminal summary for all stages
    print_terminal_summary(run_summary_json_data)

    return 0 if overall_status == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
