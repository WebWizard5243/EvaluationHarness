import argparse
import json
from pathlib import Path
import matplotlib.pyplot as plt

def load_jsonl(filename):
    with open(filename, encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def collect_observations(results, scores):
    scores_by_id = {s["id"]: s for s in scores}
    observations = []

    for result in results:
        actual = result.get("actual_response") or {}
        score = scores_by_id.get(result["id"])

        if not score or actual.get("abstained") is not False:
            continue

        # REVIEW is not a verified correctness label.
        if score["status"] not in ("PASS", "FAIL"):
            continue

        confidence = actual.get("confidence")

        if not isinstance(confidence, (int, float)):
            continue
        if not 0 <= confidence <= 1:
            continue

        observations.append({
            "id": result["id"],
            "confidence": float(confidence),
            "correct": int(score["status"] == "PASS"),
        })

    return observations


def calculate_metrics(observations, bins=5):
    n = len(observations)

    if n == 0:
        raise ValueError("No scored, answered cases available.")

    brier = sum(
        (row["confidence"] - row["correct"]) ** 2
        for row in observations
    ) / n

    calibration_bins = []

    for i in range(bins):
        lower = i / bins
        upper = (i + 1) / bins

        members = [
            row for row in observations
            if lower <= row["confidence"] < upper
            or (i == bins - 1 and row["confidence"] == 1)
        ]

        if not members:
            continue

        avg_confidence = sum(x["confidence"] for x in members) / len(members)
        accuracy = sum(x["correct"] for x in members) / len(members)

        calibration_bins.append({
            "count": len(members),
            "avg_confidence": avg_confidence,
            "accuracy": accuracy,
        })

    ece = sum(
        (b["count"] / n) * abs(b["accuracy"] - b["avg_confidence"])
        for b in calibration_bins
    )

    return brier, ece, calibration_bins


def main():
    parser = argparse.ArgumentParser(description="Calculate confidence calibration metrics.")
    parser.add_argument("--results", default="results.jsonl", help="Results JSONL file path.")
    parser.add_argument("--scores", default="scores.jsonl", help="Scores JSONL file path.")
    parser.add_argument("--output", default=None, help="Optional output JSON path for calibration metrics.")
    parser.add_argument("--plot", default="calibration_curve.png", help="Path to save reliability diagram.")
    parser.add_argument("--bins", type=int, default=5, help="Number of calibration bins.")
    args = parser.parse_args()

    results = load_jsonl(args.results)
    scores = load_jsonl(args.scores)

    observations = collect_observations(results, scores)
    
    if not observations:
        print("\n===== CONFIDENCE CALIBRATION =====")
        print("Answered and scored cases: 0")
        print("Warning: No scored, answered cases available for calibration.")
        metrics = {
            "answered_and_scored_cases": 0,
            "brier_score": None,
            "expected_calibration_error": None,
            "bins": [],
        }
        if args.output:
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        return

    brier, ece, bins = calculate_metrics(observations, bins=args.bins)

    print("\n===== CONFIDENCE CALIBRATION =====")
    print(f"Answered and scored cases: {len(observations)}")
    print(f"Brier score: {brier:.4f}")
    print(f"Expected Calibration Error: {ece:.4f}")

    plot_path = Path(args.plot)
    plot_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(7, 6))
    plt.plot([0, 1], [0, 1], "--", label="Perfect calibration")
    plt.plot(
        [b["avg_confidence"] for b in bins],
        [b["accuracy"] for b in bins],
        marker="o",
        label="Observed calibration",
    )
    plt.xlabel("Average reported confidence")
    plt.ylabel("Observed accuracy")
    plt.title("GroundTruth QA - Reliability Diagram")
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path, dpi=160)
    plt.close()

    print(f"Saved {plot_path}")

    metrics = {
        "answered_and_scored_cases": len(observations),
        "brier_score": round(brier, 4),
        "expected_calibration_error": round(ece, 4),
        "bins": bins,
    }

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Saved calibration metrics to: {out_p}")


if __name__ == "__main__":
    main()
