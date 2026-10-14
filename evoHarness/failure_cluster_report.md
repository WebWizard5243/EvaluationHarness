# Failure Clustering Report

- Scored failures: 15
- Method: deterministic, rule-based preliminary clustering
- Root causes: hypotheses, not confirmed without retrieval traces

## Cluster distribution

| Cluster | Cases |
|---|---:|
| `failure_to_abstain` | 1 |
| `false_abstention` | 10 |
| `false_premise_handling` | 3 |
| `wrong_fact_or_metric_selection` | 1 |

## Case-level findings

### TC002 — `wrong_fact_or_metric_selection`

- Category: straightforward
- Observed failure: `incorrect_answer`
- Question: What was Intel's total revenue in 2025?
- Abstained: False
- Confidence: 0.9
- Evidence recorded: True
- Root-cause hypothesis: Possible confusion between total consolidated revenue and Intel Products segment revenue. Inspect retrieved chunks and answer-generation logic.

### TC006 — `false_abstention`

- Category: straightforward
- Observed failure: `false_abstention`
- Question: How much cash and cash equivalents did Intel report at December 27, 2025?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC014 — `false_abstention`

- Category: straightforward
- Observed failure: `false_abstention`
- Question: Which two groups make up Intel Products?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC017 — `false_abstention`

- Category: paraphrase
- Observed failure: `false_abstention`
- Question: How much sales revenue did Intel generate in fiscal 2025?
- Abstained: True
- Confidence: 0.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC018 — `false_abstention`

- Category: paraphrase
- Observed failure: `false_abstention`
- Question: Did Intel's revenue increase from 2024 to 2025?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC019 — `false_abstention`

- Category: paraphrase
- Observed failure: `false_abstention`
- Question: What was Intel's R&D investment, in expense terms, for 2025?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC020 — `false_abstention`

- Category: paraphrase
- Observed failure: `false_abstention`
- Question: What cash and cash-equivalent balance did Intel have at fiscal year-end 2025?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC024 — `false_abstention`

- Category: paraphrase
- Observed failure: `false_abstention`
- Question: Which Intel governance body carries the highest-level responsibility for cybersecurity risk oversight?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC025 — `false_abstention`

- Category: paraphrase
- Observed failure: `false_abstention`
- Question: Did Intel Foundry make an operating profit in 2025, and what was the result?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC027 — `false_abstention`

- Category: irrelevant_context
- Observed failure: `false_abstention`
- Question: I enjoy tracking stock markets and comparing technology firms. What was Intel's 2025 revenue?
- Abstained: True
- Confidence: 0.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC030 — `false_abstention`

- Category: irrelevant_context
- Observed failure: `false_abstention`
- Question: I'm comparing hotel prices for a holiday. What was Intel's R&D expense in 2025?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained on an answerable question. The recorded response contains no evidence, so retrieval failure is a hypothesis, not a confirmed cause.

### TC034 — `false_premise_handling`

- Category: false_premise
- Observed failure: `failure_to_correct_false_premise`
- Question: Since Intel earned $53.101 billion in revenue in 2025, what drove that result?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained instead of correcting the false premise. Check whether the relevant corrective evidence was retrieved.

### TC039 — `false_premise_handling`

- Category: false_premise
- Observed failure: `failure_to_correct_false_premise`
- Question: Intel Foundry earned $10.318 billion in operating profit in 2025. What drove its success?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained instead of correcting the false premise. Check whether the relevant corrective evidence was retrieved.

### TC040 — `false_premise_handling`

- Category: false_premise
- Observed failure: `failure_to_correct_false_premise`
- Question: Since all Intel revenue came from the US in 2025, how much was domestic revenue?
- Abstained: True
- Confidence: 1.0
- Evidence recorded: False
- Root-cause hypothesis: The system abstained instead of correcting the false premise. Check whether the relevant corrective evidence was retrieved.

### TC049 — `failure_to_abstain`

- Category: unanswerable
- Observed failure: `failure_to_abstain`
- Question: What was the exact reason every individual customer did not buy an Intel product in 2025?
- Abstained: False
- Confidence: 1.0
- Evidence recorded: True
- Root-cause hypothesis: The system answered a question labelled unanswerable. Check whether it made an unsupported inference or mistook partial evidence for sufficient evidence.

