# Evidence-Driven Failure Cluster Report

- Failed cases analyzed: **7**
- Live retrieval diagnostics: **available**
- Top-k: **10**
- Candidate clusters are based on observed diagnostic signatures, not causal proof.
- Lexical/numeric matching is heuristic: a miss does not prove semantic absence.

## Diagnostic pattern counts

- `indexed_answer_clue_missing_from_top_k`: **4** case(s)
- `false_premise_not_corrected`: **1** case(s)
- `answer_clue_in_top_k_but_abstained`: **1** case(s)
- `answered_when_abstention_expected`: **1** case(s)

## Candidate behavioral clusters

### Cluster 1: `indexed_answer_clue_missing_from_top_k`

- Cases: TC002, TC019, TC030
- Expected behavior: `answer`
- Dataset categories represented: `irrelevant_context, paraphrase, straightforward`

**TC002 — What was Intel's total revenue in 2025?**
- Scoring label: `incorrect_answer`; abstained: `False`.
- Observation: An expected-answer clue occurs in the indexed corpus but not in top-k; this is a retrieval miss signal, though the raw abstention field does not confirm abstention.
- Retrieved pages: `[28, 28, 80, 80, 27, 27, 33, 32, 32, 33]`.
- Scorer explanation: The actual answer provides the Total Intel Products revenue ($49.1 billion), but the reference answer for Intel's total overall revenue is $52.853 billion, meaning the system provided a different metric.

**TC019 — What was Intel's R&D investment, in expense terms, for 2025?**
- Scoring label: `false_abstention`; abstained: `True`.
- Observation: An expected-answer clue occurs in the indexed corpus but not in top-k; consistent with a retrieval miss. The scorer labels this as a false abstention.
- Retrieved pages: `[79, 86, 79, 86, 94, 112, 39, 39, 33, 33]`.
- Scorer explanation: The application abstained when an answer was expected.

**TC030 — I'm comparing hotel prices for a holiday. What was Intel's R&D expense in 2025?**
- Scoring label: `false_abstention`; abstained: `True`.
- Observation: An expected-answer clue occurs in the indexed corpus but not in top-k; consistent with a retrieval miss. The scorer labels this as a false abstention.
- Retrieved pages: `[79, 79, 39, 39, 108, 108, 33, 33, 41, 87]`.
- Scorer explanation: The application abstained when an answer was expected.

### Cluster 2: `answer_clue_in_top_k_but_abstained`

- Cases: TC040
- Expected behavior: `correct_false_premise`
- Dataset categories represented: `false_premise`

**TC040 — Since all Intel revenue came from the US in 2025, how much was domestic revenue?**
- Scoring label: `failure_to_correct_false_premise`; abstained: `True`.
- Observation: An expected-answer clue occurs in retrieved text although the QA response abstained.
- Retrieved pages: `[28, 31, 28, 31, 29, 80, 29, 30, 80, 30]`.
- Scorer explanation: The application abstained instead of correcting the false premise.

### Cluster 3: `answered_when_abstention_expected`

- Cases: TC049
- Expected behavior: `abstain`
- Dataset categories represented: `unanswerable`

**TC049 — What was the exact reason every individual customer did not buy an Intel product in 2025?**
- Scoring label: `failure_to_abstain`; abstained: `False`.
- Observation: The system answered a case whose expected behavior was abstention.
- Retrieved pages: `[125, 18, 125, 18, 31, 31, 21, 48, 14, 5]`.
- Scorer explanation: The application answered when abstention was expected.

### Cluster 4: `false_premise_not_corrected`

- Cases: TC034
- Expected behavior: `correct_false_premise`
- Dataset categories represented: `false_premise`

**TC034 — Since Intel earned $53.101 billion in revenue in 2025, what drove that result?**
- Scoring label: `false_premise_not_corrected`; abstained: `False`.
- Observation: Scorer marked false-premise correction as failed; inspect whether corrective evidence was retrieved and used.
- Retrieved pages: `[28, 28, 71, 31, 71, 31, 29, 29, 30, 30]`.
- Scorer explanation: The expected behavior was to correct the false premise and not invent a cause for the misstated figure. The actual answer accepted the premise regarding what drove the $53.101 billion revenue (treating it as $52.9 billion) and provided reasons from the text, violating the correct_false_premise constraint.

### Cluster 5: `indexed_answer_clue_missing_from_top_k`

- Cases: TC039
- Expected behavior: `correct_false_premise`
- Dataset categories represented: `false_premise`

**TC039 — Intel Foundry earned $10.318 billion in operating profit in 2025. What drove its success?**
- Scoring label: `failure_to_correct_false_premise`; abstained: `True`.
- Observation: An expected-answer clue occurs in the indexed corpus but not in top-k; consistent with a retrieval miss. The scorer labels this as a false abstention.
- Retrieved pages: `[32, 32, 28, 28, 30, 29, 13, 79, 85, 79]`.
- Scorer explanation: The application abstained instead of correcting the false premise.

## Per-case summary

| Case | Scoring label | Diagnostic pattern | Retrieved pages |
|---|---|---|---|
| TC002 | `incorrect_answer` | `indexed_answer_clue_missing_from_top_k` | `[28, 28, 80, 80, 27, 27, 33, 32, 32, 33]` |
| TC019 | `false_abstention` | `indexed_answer_clue_missing_from_top_k` | `[79, 86, 79, 86, 94, 112, 39, 39, 33, 33]` |
| TC030 | `false_abstention` | `indexed_answer_clue_missing_from_top_k` | `[79, 79, 39, 39, 108, 108, 33, 33, 41, 87]` |
| TC034 | `false_premise_not_corrected` | `false_premise_not_corrected` | `[28, 28, 71, 31, 71, 31, 29, 29, 30, 30]` |
| TC039 | `failure_to_correct_false_premise` | `indexed_answer_clue_missing_from_top_k` | `[32, 32, 28, 28, 30, 29, 13, 79, 85, 79]` |
| TC040 | `failure_to_correct_false_premise` | `answer_clue_in_top_k_but_abstained` | `[28, 31, 28, 31, 29, 80, 29, 30, 80, 30]` |
| TC049 | `failure_to_abstain` | `answered_when_abstention_expected` | `[125, 18, 125, 18, 31, 31, 21, 48, 14, 5]` |