# Regression Test Report

## Summary

- Baseline: `baseline/results.jsonl` and `baseline/scores.jsonl`
- Candidate: `/Users/kaif/Web Development/internship/HevaAI/evoHarness/runs/regression_20261014_211633/results.jsonl` and `/Users/kaif/Web Development/internship/HevaAI/evoHarness/runs/regression_20261014_211633/scores.jsonl`
- Cases matched by ID: **50**
- Baseline cases missing from candidate scores: **0**
- New candidate score IDs: **0**
- Baseline pass rate: **0.7** (35/50)
- Candidate pass rate: **0.86** (43/50)
- Status changes: **10**
- Regressions (PASS → FAIL): **1**
- Improvements (FAIL → PASS): **9**
- Answer text changed: **32**
- Abstention behavior changed: **11**

## Case-level score changes

| Case | Category | Baseline | Candidate | Interpretation |
|---|---|---|---|---|
| TC006 | straightforward | FAIL | PASS | Improvement |
| TC014 | straightforward | FAIL | PASS | Improvement |
| TC016 | paraphrase | PASS | FAIL | Regression |
| TC017 | paraphrase | FAIL | PASS | Improvement |
| TC018 | paraphrase | FAIL | PASS | Improvement |
| TC020 | paraphrase | FAIL | PASS | Improvement |
| TC024 | paraphrase | FAIL | PASS | Improvement |
| TC025 | paraphrase | FAIL | PASS | Improvement |
| TC027 | irrelevant_context | FAIL | PASS | Improvement |
| TC049 | unanswerable | FAIL | PASS | Improvement |

## Results by input category

| Category | Cases | Baseline pass/fail | Candidate pass/fail | Regressions | Improvements |
|---|---:|---:|---:|---:|---:|
| false_premise | 7 | 4/3 | 4/3 | 0 | 0 |
| irrelevant_context | 8 | 6/2 | 7/1 | 0 | 1 |
| paraphrase | 10 | 4/6 | 8/2 | 1 | 5 |
| straightforward | 15 | 12/3 | 14/1 | 0 | 2 |
| unanswerable | 10 | 9/1 | 10/0 | 0 | 1 |

## Answer changes requiring review

### TC002 (straightforward)
- Score status: FAIL → FAIL
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel's total Intel Products revenue in 2025 was $49.1 billion (or $49,147 million).
- Candidate answer: Intel's total Intel Products revenue was $49.1 billion (or $49,147 million) in 2025.

### TC003 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: In 2024, Intel's total consolidated revenue was $53,101 million ($53.1 billion), while total Intel Products revenue was $49.5 billion ($49,471 million).
- Candidate answer: Intel's total consolidated revenue in 2024 was $53.1 billion (or $53,101 million). Additionally, total Intel Products revenue specifically was $49.5 billion in 2024.

### TC004 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: In 2025, Intel's net income (loss) attributable to Intel was a loss of $267 million.
- Candidate answer: In 2025, Intel's net income (loss) attributable to Intel was a net loss of $267 million.

### TC005 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel spent $13.8 billion (specifically $13,774 million) on research and development in 2025.
- Candidate answer: In 2025, Intel spent $13.8 billion (specifically $13,774 million) on research and development.

### TC006 (straightforward)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: Intel reported $14,265 million in cash and cash equivalents as of December 27, 2025.

### TC007 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel's stock is listed on the Nasdaq Global Select Market under the trading symbol INTC.
- Candidate answer: Intel's common stock is traded on the Nasdaq Global Select Market.

### TC008 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel's stock ticker symbol is INTC.
- Candidate answer: Intel's common stock trades under the ticker symbol INTC.

### TC010 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: According to the CEO letter, more than 200 notebook designs were launched on Series 3.
- Candidate answer: According to the CEO letter, more than 200 notebook designs were launched on Core Ultra Series 3.

### TC011 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel Foundry's revenue in 2025, which includes intersegment financial activity, was $17,826 million (or $17.8 billion).
- Candidate answer: Intel Foundry's revenue in 2025, including intersegment activity, was $17,826 million.

### TC013 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Sales outside the United States accounted for 70% of Intel's revenue for the fiscal year ended December 27, 2025.
- Candidate answer: Sales outside the United States accounted for 70% of Intel's total revenue for the fiscal year ended December 27, 2025.

### TC014 (straightforward)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: Intel Products is composed of two operating segments: CCG and DCAI.

### TC015 (straightforward)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: The Board of Directors has ultimate oversight of cybersecurity risk, managing it as a part of the enterprise risk management program.
- Candidate answer: The Board of Directors has ultimate oversight of cybersecurity risk at Intel, managing it as part of the enterprise risk management program.

### TC016 (paraphrase)
- Score status: PASS → FAIL
- Baseline abstained: `False`; candidate abstained: `True`
- Baseline answer: Lip-Bu Tan became Intel's Chief Executive Officer, with an offer letter dated March 10, 2025, and new hire grants dated March 18, 2025, marking 2025 as his first year as CEO.
- Candidate answer: 

### TC017 (paraphrase)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: In fiscal 2025 (for the year ended December 27, 2025), Intel generated a total consolidated revenue of $52,853 million.

### TC018 (paraphrase)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: No, Intel's revenue did not increase from 2024 to 2025; instead, it decreased by $248 million to $52.9 billion.

### TC020 (paraphrase)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: Intel had a cash and cash-equivalent balance of $14,265 million at fiscal year-end 2025 (December 27, 2025).

### TC021 (paraphrase)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel's common stock is listed on the Nasdaq Global Select Market and its trading symbol is INTC.
- Candidate answer: Intel's common stock is traded on the Nasdaq Global Select Market under the symbol INTC.

### TC022 (paraphrase)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: For Intel 18A, the highlighted transistor technology is RibbonFET (an implementation of a gate-all-around transistor), and the highlighted power-delivery technology is PowerVia (an implementation of backside power delivery).
- Candidate answer: The technologies highlighted for Intel 18A are RibbonFET, which is an implementation of a gate-all-around transistor designed for faster switching speeds in a smaller footprint, and PowerVia, an implementation of backside power delivery designed to optimize signal transmission.

### TC023 (paraphrase)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel announced that more than 200 notebook designs launched on the Intel Core Ultra Series 3, making it the most broadly adopted AI PC platform in Intel's history.
- Candidate answer: Intel announced that Core Ultra Series 3 powers over 200 notebook designs from leading global partners, making it the most broadly adopted AI PC platform in Intel's history.

### TC024 (paraphrase)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: The Board of Directors holds ultimate oversight responsibility for cybersecurity risk.

### TC025 (paraphrase)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: No, Intel Foundry did not make an operating profit in 2025; instead, it incurred an operating loss of $10,318 million.

### TC027 (irrelevant_context)
- Score status: FAIL → PASS
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: Intel's revenue in 2025 was $52.9 billion.

### TC028 (irrelevant_context)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: Intel 18A introduces two breakthrough technologies: RibbonFET (gate-all-around transistors) and PowerVia (backside power delivery).
- Candidate answer: Intel 18A introduces two breakthrough industry technologies: RibbonFET (gate-all-around transistors) and PowerVia (backside power delivery).

### TC032 (irrelevant_context)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: At the board level, Intel's cybersecurity program is reviewed and overseen by the Board of Directors, which is assisted by the Audit & Finance Committee.
- Candidate answer: At the board level, Intel's cybersecurity program is regularly reviewed by the Audit & Finance Committee, which assists the Board of Directors and reports to them.

### TC034 (false_premise)
- Score status: FAIL → FAIL
- Baseline abstained: `True`; candidate abstained: `False`
- Baseline answer: 
- Candidate answer: The premise of the question is contradicted by the provided excerpts, which state that Intel's revenue in 2025 was $52.9 billion (with 2024 revenue being $53.1 billion), rather than $53.101 billion. For 2025, the $52.9 billion revenue result was driven by Intel Products revenue being roughly flat with 2024, primarily because lower CCG revenue was substantially offset by higher DCAI revenue.

### TC035 (false_premise)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: The premise of the question is incorrect. Intel did not report a positive net income attributable to Intel in 2025; rather, it reported a net loss of $267 million.
- Candidate answer: The excerpts contradict the premise of the question. Intel did not report a positive net income attributable to Intel in 2025; instead, it reported a net loss attributable to Intel of $267 million.

### TC036 (false_premise)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: The excerpts contradict the premise that Pat Gelsinger was Intel's CEO throughout 2025. Intel entered into a retirement and separation agreement with Patrick Gelsinger dated December 1, 2024, and Lip-Bu Tan served as the Chief Executive Officer during 2025, which was noted as his first year as CEO.
- Candidate answer: The excerpts contradict the premise that Pat Gelsinger was Intel's CEO throughout 2025. Intel experienced CEO transitions in 2024 and 2025, and Patrick Gelsinger entered into a retirement and separation agreement on December 1, 2024. Furthermore, Lip-Bu Tan is listed as the Chief Executive Officer.

### TC037 (false_premise)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: The premise of the question contradicts the provided excerpts. Intel Core Ultra Series 3 is built on Intel 18A, not Intel 3. It is Intel 18A that introduced the two breakthrough technologies, RibbonFET and PowerVia. Intel 3 is instead referenced in relation to the manufacturing of Intel Core Ultra Series 2 products.
- Candidate answer: The premise of the question is contradicted by the provided documents. Intel Core Ultra Series 3 is manufactured using Intel 18A process technology rather than Intel 3 (which is used for certain versions of Intel Core Ultra Series 2). Additionally, the two breakthrough technologies—RibbonFET and PowerVia—were introduced by Intel 18A, not Intel 3.

### TC038 (false_premise)
- Score status: PASS → PASS
- Baseline abstained: `False`; candidate abstained: `False`
- Baseline answer: The excerpts contradict the premise that only 20 notebook designs launched on Core Ultra Series 3. Rather, the documents state that more than 200 notebook designs launched on Series 3, making it the most broadly adopted AI PC platform in Intel's history. Series 3 processors are the first compute platform built on Intel 18A—the most advanced semiconductor process technology designed and manufactured in the United States—and introduce two breakthrough industry technologies: RibbonFET (gate-all-aro
- Candidate answer: The excerpts contradict the premise that only 20 notebook designs launched on Core Ultra Series 3, stating instead that more than 200 notebook designs launched. Core Ultra Series 3 is the first compute platform built on Intel 18A, featuring breakthrough technologies such as RibbonFET (gate-all-around transistors) and PowerVia (backside power delivery). Additionally, these mobile processors offer improved CPU, AI, and graphics performance while maintaining power efficiency, making Series 3 the mo

### TC046 (unanswerable)
- Score status: PASS → PASS
- Baseline abstained: `True`; candidate abstained: `True`
- Baseline answer: 
- Candidate answer: I cannot answer this question because the provided document excerpts do not contain information regarding passwords for Intel's internal systems.

### TC047 (unanswerable)
- Score status: PASS → PASS
- Baseline abstained: `True`; candidate abstained: `True`
- Baseline answer: The provided document excerpts do not contain information regarding the number of notebook designs that will have launched on Core Ultra Series 3 by the end of 2030.
- Candidate answer: 

### TC049 (unanswerable)
- Score status: FAIL → PASS
- Baseline abstained: `False`; candidate abstained: `True`
- Baseline answer: The premise that every individual customer did not buy an Intel product in 2025 is contradicted by the excerpts, as Intel generated $52.9 billion in revenue that year. While certain revenue segments experienced decreases due to factors such as reduced incentives, customer inventory reductions, and supply constraints affecting market demand, customers did continue to purchase Intel products.
- Candidate answer: I am abstaining from answering because the provided excerpts do not contain information about why every individual customer did not buy an Intel product in 2025.


## Interpretation and limitations

- A PASS → FAIL transition is a regression signal; inspect the case before attributing a cause.
- A FAIL → PASS transition is an improvement signal.
- Changed answer text is not automatically a regression: it may be a harmless wording change or a correctness change.
- Compare only runs using the same dataset version, scoring rubric, model/configuration, and source document where possible.
- If model outputs are nondeterministic, rerun ambiguous cases before making strong claims.
- Baseline and candidate files are read-only inputs to this script; it writes only the report and JSON comparison.
