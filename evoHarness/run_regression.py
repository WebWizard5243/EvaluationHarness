
import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd, cwd=HERE):
    print("\n$", " ".join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], cwd=cwd, check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default="test_dataset.json")
    p.add_argument("--baseline-dir", default="baseline")
    p.add_argument("--doc", default=None, help="Optional source PDF path passed to evaluate.py")
    p.add_argument("--limit", type=int, default=None, help="Run only first N cases (smoke test, not full regression)")
    p.add_argument("--case-id", nargs="+", default=None, help="Run selected case IDs only")
    p.add_argument("--delay", type=float, default=13.0, help="Seconds between QA calls")
    p.add_argument("--score-delay", type=float, default=4.5, help="Seconds between semantic scoring calls")
    p.add_argument("--no-judge", action="store_true", help="Skip semantic scoring; not suitable for final metrics")
    p.add_argument("--compare-existing", action="store_true",
                   help="Do not call models; compare root results.jsonl/scores.jsonl to baseline")
    p.add_argument("--results", default=None, help="Existing candidate results file for --compare-existing")
    p.add_argument("--scores", default=None, help="Existing candidate scores file for --compare-existing")
    p.add_argument("--report", default=None)
    p.add_argument("--json-out", default=None)
    args = p.parse_args()

    if args.compare_existing:
        run_results = Path(args.results or "results.jsonl")
        run_scores = Path(args.scores or "scores.jsonl")
        run_dir = None
    else:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = HERE / "runs" / f"regression_{stamp}"
        run_dir.mkdir(parents=True, exist_ok=False)
        run_results = run_dir / "results.jsonl"
        run_scores = run_dir / "scores.jsonl"

        cmd = [sys.executable, HERE / "evaluate.py", "--dataset", args.dataset,
               "--output", run_results, "--delay", args.delay]
        if args.limit is not None:
            cmd += ["--limit", args.limit]
        if args.case_id:
            cmd += ["--case-id", *args.case_id]
        if args.doc:
            cmd += ["--doc", args.doc]
        run(cmd)

        score_cmd = [sys.executable, HERE / "scoring.py", "--input", run_results,
                     "--output", run_scores, "--delay", args.score_delay]
        if args.no_judge:
            score_cmd.append("--no-judge")
        run(score_cmd)

    report_path = Path(args.report) if args.report else (
        run_dir / "regression_report.md" if run_dir else HERE / "regression_report.md")
    json_path = Path(args.json_out) if args.json_out else (
        run_dir / "regression_comparison.json" if run_dir else HERE / "regression_comparison.json")

    compare_cmd = [
        sys.executable, HERE / "regression.py",
        "--baseline-dir", args.baseline_dir,
        "--dataset", args.dataset,
        "--candidate-results", run_results,
        "--candidate-scores", run_scores,
        "--report", report_path,
        "--json-out", json_path,
    ]
    run(compare_cmd)
    print("\nRegression workflow completed.")
    print(f"Candidate results: {run_results}")
    print(f"Candidate scores:  {run_scores}")
    print(f"Report:            {report_path}")
    print(f"Comparison JSON:   {json_path}")
    if args.limit is not None or args.case_id or args.no_judge:
        print("WARNING: This was a partial/nonstandard run; do not report it as the full 50-case regression result.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: command failed with exit code {exc.returncode}. Existing baseline files were not modified.", file=sys.stderr)
        raise SystemExit(exc.returncode)
