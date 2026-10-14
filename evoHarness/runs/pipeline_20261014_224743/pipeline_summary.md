# Pipeline Run Summary: `pipeline_20261014_224743`

- **Timestamp:** 2026-10-14T22:47:43.976658
- **Overall Pipeline Status:** **SUCCESS**
- **Total Duration:** 25m 27s
- **Dataset:** `test_dataset.json` (50 cases)
- **Run Directory:** `runs/pipeline_20261014_224743`

## Stage Execution

| Stage | Status | Duration | Exit Code | Output Artifact |
| :--- | :---: | :---: | :---: | :--- |
| `evaluate` | **SUCCESS** | 13m 16s | `0` | `runs/pipeline_20261014_224743/results.jsonl` |
| `scoring` | **SUCCESS** | 5m 37s | `0` | `runs/pipeline_20261014_224743/scores.jsonl` |
| `hallucination` | **SUCCESS** | 6m 22s | `0` | `runs/pipeline_20261014_224743/hallucination_results.jsonl` |
| `calibration` | **SUCCESS** | 1.2s | `0` | `runs/pipeline_20261014_224743/calibration_results.json` |
| `cluster` | **SUCCESS** | 9.7s | `0` | `runs/pipeline_20261014_224743/cluster_summary.json` |

## Accuracy & Category Breakdown

- **Overall Pass Rate:** **86.0%** (43/50 cases)
- **Fail:** 7 | **Review:** 0

| Category | Total | Pass | Fail | Review | Pass Rate |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `false_premise` | 7 | 4 | 3 | 0 | 57.1% |
| `irrelevant_context` | 8 | 7 | 1 | 0 | 87.5% |
| `paraphrase` | 10 | 9 | 1 | 0 | 90.0% |
| `straightforward` | 15 | 14 | 1 | 0 | 93.3% |
| `unanswerable` | 10 | 9 | 1 | 0 | 90.0% |

### Failure Distribution

- `failure_to_abstain`: **1** case(s)
- `failure_to_correct_false_premise`: **2** case(s)
- `false_abstention`: **2** case(s)
- `false_premise_not_corrected`: **1** case(s)
- `incorrect_answer`: **1** case(s)

## Hallucination Evaluation

- **Total Cases Evaluated:** 50
- **Status Counts:** `NOT_APPLICABLE`: 13, `NOT_ESTABLISHED`: 5, `SUPPORTED`: 32

## Confidence Calibration

- **Answered & Scored Cases:** 37
- **Brier Score:** `0.0741`
- **Expected Calibration Error (ECE):** `0.0757`
- **Reliability Diagram:** `runs/pipeline_20261014_224743/calibration_curve.png`

## Failure Clustering

- **Status:** `SUCCESS`
- **Failed Cases Analyzed:** 7
- **Clusters Found:** 5
- **Per-Run Cluster Summary:** `runs/pipeline_20261014_224743/cluster_summary.json`
- **Per-Run Cluster Report:** `cluster_failure.md`

| Cluster Name | Expected Behavior | Failures | Case IDs |
| :--- | :--- | :---: | :--- |
| `indexed_answer_clue_missing_from_top_k` | `answer` | 3 | TC002, TC019, TC030 |
| `answer_clue_in_top_k_but_abstained` | `correct_false_premise` | 1 | TC040 |
| `answered_when_abstention_expected` | `abstain` | 1 | TC049 |
| `false_premise_not_corrected` | `correct_false_premise` | 1 | TC034 |
| `indexed_answer_clue_missing_from_top_k` | `correct_false_premise` | 1 | TC039 |
