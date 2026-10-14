# Heva AI — Adversarial Evaluation Harness

An end-to-end evaluation suite for a Retrieval-Augmented Generation (RAG) question-answering system built on Intel's 2025 Annual Report. Covers correctness scoring, hallucination detection, confidence calibration, failure clustering, and regression testing.

---

## Repository Layout

```
HevaAI/
├── .env                          # API key (not committed)
├── DocumentClassifier/           # Core QA application
│   ├── app/
│   │   ├── config.py             # Configuration & env loading
│   │   ├── document.py           # PDF ingestion & BM25 retriever
│   │   ├── qa_system.py          # ask() — retrieval + Gemini answering
│   │   └── schemas.py            # Pydantic response models
│   ├── docs/                     # Place source PDF here
│   ├── main.py                   # Interactive CLI entry point
│   └── requirements.txt
└── evoHarness/                   # Evaluation harness
    ├── test_dataset.json         # 50 adversarial test cases (5 categories)
    ├── run_pipeline.py           # ★ Full pipeline runner (all 5 stages)
    ├── run_regression.py         # Regression runner (baseline comparison)
    ├── evaluate.py               # Stage 1 — QA evaluation
    ├── scoring.py                # Stage 2 — Pass/Fail scoring
    ├── hallucination.py          # Stage 3 — Evidence grounding check
    ├── calibration.py            # Stage 4 — Confidence calibration
    ├── cluster.py                # Stage 5 — Failure clustering
    ├── failure_clustering.py     # Core clustering logic (used by cluster.py)
    ├── baseline/                 # Frozen baseline for regression testing
    │   ├── results.jsonl
    │   └── scores.jsonl
    └── runs/                     # All pipeline & regression run outputs
        └── pipeline_YYYYMMDD_HHMMSS/
            ├── results.jsonl
            ├── scores.jsonl
            ├── hallucination_results.jsonl
            ├── calibration_results.json
            ├── calibration_curve.png
            ├── cluster_summary.json
            ├── failure_diagnostics.jsonl
            ├── pipeline_summary.json
            ├── pipeline_summary.md
            └── logs/
```

---

## Prerequisites

- **Python 3.11+**
- **Gemini API key** — get one free at [aistudio.google.com](https://aistudio.google.com/apikey)
- **Intel 2025 Annual Report PDF** placed inside `DocumentClassifier/docs/`

---

## 1. Setup

### Install dependencies

```bash
cd DocumentClassifier
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **Note:** `evoHarness` scripts share the same virtual environment — no separate install needed.

### Configure your API key

Copy the example env file at the project root and fill in your key:

```bash
# From the HevaAI/ root
cp DocumentClassifier/.env.example .env
```

Then open `.env` and set:

```env
GEMINI_API_KEY=your-api-key-here

# Optional — defaults shown
GEMINI_MODEL=gemini-2.5-flash
```

The `.env` file is discovered automatically by all scripts.

---

## 2. Running the Full Evaluation Pipeline

The pipeline runner executes all five evaluation stages in sequence and saves every artifact inside a single timestamped directory under `evoHarness/runs/`.

```bash
cd evoHarness
python run_pipeline.py
```

### What it runs

| Stage | Script | Output |
| :--- | :--- | :--- |
| 1 — QA Evaluation | `evaluate.py` | `results.jsonl` |
| 2 — Scoring | `scoring.py` | `scores.jsonl` |
| 3 — Hallucination Check | `hallucination.py` | `hallucination_results.jsonl` |
| 4 — Calibration | `calibration.py` | `calibration_results.json`, `calibration_curve.png` |
| 5 — Failure Clustering | `cluster.py` | `cluster_summary.json`, `failure_diagnostics.jsonl` |

All outputs land in `evoHarness/runs/pipeline_YYYYMMDD_HHMMSS/`. A human-readable `pipeline_summary.md` and machine-readable `pipeline_summary.json` are also written there.

### Expected runtime

The default run processes all 50 test cases with rate-limit delays baked in:

| Stage | ~Time |
| :--- | :--- |
| evaluate (13 s/case) | ~11 min |
| scoring (4.5 s/case) | ~4 min |
| hallucination (4.5 s/case) | ~6 min |
| calibration + cluster | <15 s |
| **Total** | **~25 min** |

### Useful flags

```bash
# Quick smoke test — run only the first 3 cases
python run_pipeline.py --limit 3

# Run specific cases
python run_pipeline.py --case-id TC001 TC005 TC012

# Skip a stage (e.g. re-run without hallucination)
python run_pipeline.py --skip-stages hallucination

# Custom delays (lower = faster but may hit rate limits)
python run_pipeline.py --delay 10 --score-delay 3 --hallucination-delay 3

# Specify a different dataset
python run_pipeline.py --dataset path/to/other_dataset.json
```

---

## 3. Running Individual Stages

Each script is fully standalone and accepts its own CLI arguments.

### Stage 1 — QA Evaluation

```bash
cd evoHarness
python evaluate.py --dataset test_dataset.json --output results.jsonl
```

### Stage 2 — Scoring

```bash
python scoring.py --input results.jsonl --output scores.jsonl
```

### Stage 3 — Hallucination Detection

```bash
python hallucination.py --input results.jsonl --output hallucination_results.jsonl
```

### Stage 4 — Confidence Calibration

```bash
python calibration.py \
  --results results.jsonl \
  --scores scores.jsonl \
  --output calibration_results.json \
  --plot calibration_curve.png
```

### Stage 5 — Failure Clustering

```bash
python cluster.py \
  --results results.jsonl \
  --scores scores.jsonl \
  --dataset test_dataset.json \
  --output-summary cluster_summary.json \
  --output-jsonl failure_diagnostics.jsonl
```

---

## 4. Regression Testing

The regression runner compares a new evaluation run against the frozen baseline in `evoHarness/baseline/`.

```bash
cd evoHarness
python run_regression.py
```

Results are saved to `evoHarness/runs/regression_YYYYMMDD_HHMMSS/`. The baseline is never modified by this command.

---

## 5. Reproduced Results

The following results were produced by running `python run_pipeline.py` against all 50 test cases on **2026-10-14** (run `pipeline_20261014_224743`).

### Accuracy

| Category | Cases | Pass | Fail | Pass Rate |
| :--- | :---: | :---: | :---: | :---: |
| `straightforward` | 15 | 14 | 1 | 93.3% |
| `paraphrase` | 10 | 9 | 1 | 90.0% |
| `irrelevant_context` | 8 | 7 | 1 | 87.5% |
| `unanswerable` | 10 | 9 | 1 | 90.0% |
| `false_premise` | 7 | 4 | 3 | 57.1% |
| **Overall** | **50** | **43** | **7** | **86.0%** |

### Hallucination (50 cases evaluated)

| Verdict | Count |
| :--- | :---: |
| `SUPPORTED` | 32 |
| `NOT_APPLICABLE` (abstained) | 13 |
| `NOT_ESTABLISHED` | 5 |

### Confidence Calibration (37 answered & scored cases)

| Metric | Value |
| :--- | :---: |
| Brier Score | `0.0741` |
| Expected Calibration Error (ECE) | `0.0757` |

> A Brier score and ECE both close to 0 indicate well-calibrated confidence estimates.

### Failure Clusters (7 failed cases → 5 clusters)

| Cluster | Expected Behavior | Count | Cases |
| :--- | :--- | :---: | :--- |
| `indexed_answer_clue_missing_from_top_k` | `answer` | 3 | TC002, TC019, TC030 |
| `answer_clue_in_top_k_but_abstained` | `correct_false_premise` | 1 | TC040 |
| `answered_when_abstention_expected` | `abstain` | 1 | TC049 |
| `false_premise_not_corrected` | `correct_false_premise` | 1 | TC034 |
| `indexed_answer_clue_missing_from_top_k` | `correct_false_premise` | 1 | TC039 |

---

## 6. Test Dataset

`evoHarness/test_dataset.json` contains **50 hand-crafted adversarial test cases** across five categories designed to stress-test the QA system:

| Category | Count | Purpose |
| :--- | :---: | :--- |
| `straightforward` | 15 | Factual questions directly answered by the document |
| `paraphrase` | 10 | Same facts asked in different phrasing |
| `irrelevant_context` | 8 | Questions with misleading surrounding context |
| `false_premise` | 7 | Questions containing a false factual claim to be corrected |
| `unanswerable` | 10 | Questions the document cannot answer — system must abstain |

---

## 7. Key Design Decisions

- **BM25 retrieval** — the document is indexed once and shared across all 50 queries in a run, keeping latency and cost minimal.
- **LLM judge** — `scoring.py` and `hallucination.py` use a Gemini model as an automated judge to evaluate answer quality and evidence grounding.
- **Rate-limit pacing** — all API-calling stages include configurable inter-call delays (`--delay`, `--score-delay`, `--hallucination-delay`) to stay within free-tier limits.
- **Isolated run directories** — every pipeline execution writes all artifacts exclusively to its own `runs/pipeline_YYYYMMDD_HHMMSS/` folder; nothing is written to the project root.
- **Regression safety** — the baseline and regression runner are completely independent of the pipeline runner and cannot be accidentally overwritten.
