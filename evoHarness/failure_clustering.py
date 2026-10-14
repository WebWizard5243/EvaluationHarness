
import argparse
import importlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


def jsonl(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"[WARN] Bad JSON at {path}:{n}: {exc}")
    return rows


def read_cases(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        for key in ("cases", "test_cases", "data"):
            if isinstance(data.get(key), list):
                return data[key]
        raise ValueError(f"No test case list found in {path}")
    if not isinstance(data, list):
        raise ValueError(f"Expected a list in {path}")
    return data


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def variants(answer):
    s = norm(answer)
    out = {s}
    out.add(re.sub(r"[$€£,%]", "", s))
    out.add(re.sub(r"(?<=\d),(?=\d)", "", s))
    # Numeric equivalents such as 14.265 billion and 14,265 million.
    for m in re.finditer(r"(?<!\w)(\d[\d,]*(?:\.\d+)?)(?:\s*)(billion|million|thousand|bn|mn|k)?", s):
        raw, unit = m.group(1).replace(",", ""), (m.group(2) or "").lower()
        try:
            num = float(raw)
        except ValueError:
            continue
        out.add(raw)
        if unit in ("billion", "bn"):
            out.update({f"{num * 1000:g}", f"{num * 1_000_000_000:g}"})
        elif unit in ("million", "mn"):
            out.update({f"{num / 1000:g}", f"{num * 1_000_000:g}"})
    return sorted((x for x in out if len(x) >= 3), key=len, reverse=True)


def clue_match(text, answer):
    text = norm(text)
    # Normalize comma-separated numbers (e.g. 14,265 -> 14265) so the
    # expected-answer variant "14.265 billion" can match a table in millions.
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    for v in variants(answer):
        candidate = re.sub(r"(?<=\d),(?=\d)", "", v)
        if candidate and candidate in text:
            return True, candidate
    return (False, None) if text else (None, None)


def get_doc(explicit):
    if explicit:
        p = Path(explicit).expanduser()
        p = p if p.is_absolute() else (HERE / p).resolve()
        if not p.exists():
            raise FileNotFoundError(p)
        return p
    for p in (
        HERE / "IntelCompanyDocumentation.pdf",
        HERE.parent / "DocumentClassifier" / "docs" / "IntelCompanyDocumentation.pdf",
        HERE.parent / "DocumentClassifier" / "IntelCompanyDocumentation.pdf",
    ):
        if p.exists():
            return p.resolve()
    return None


def build_index(pdf, top_k):
    root = HERE.parent / "DocumentClassifier"
    if not (root / "app" / "document.py").exists():
        raise RuntimeError(f"Cannot find DocumentClassifier app at {root}")
    # Ensure imports come from the sibling project, not a same-named local app.
    for name in ("app.document", "app.config", "app"):
        sys.modules.pop(name, None)
    sys.path.insert(0, str(root))
    config_mod = importlib.import_module("app.config")
    document_mod = importlib.import_module("app.document")
    config = config_mod.load_config()
    processed = document_mod.process_document(
        pdf, chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap
    )
    print(f"[INFO] Indexed {processed.report.extracted_pages} pages / "
          f"{len(processed.chunks)} chunks.")
    return processed, top_k


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", default="results.jsonl")
    ap.add_argument("--scores", default="scores.jsonl")
    ap.add_argument("--dataset", default="test_dataset.json")
    ap.add_argument("--document", help="PDF path; auto-detected if omitted")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--output-jsonl", default="failure_diagnostics.jsonl")
    ap.add_argument("--output-report", default="failure_cluster_report.md")
    args = ap.parse_args()

    results = jsonl((HERE / args.results).resolve())
    scores = jsonl((HERE / args.scores).resolve())
    cases = read_cases((HERE / args.dataset).resolve())
    by_result = {str(x.get("id")): x for x in results if x.get("id") is not None}
    by_score = {str(x.get("id")): x for x in scores if x.get("id") is not None}
    by_case = {str(x.get("id")): x for x in cases if x.get("id") is not None}

    def is_fail(s):
        status = str(s.get("status", "")).lower()
        return status in {"fail", "failed", "false_abstention", "incorrect_answer",
                          "failure_to_abstain", "failure_to_correct_false_premise"} or (
            s.get("passed") is False or s.get("is_correct") is False
        )

    failed_ids = sorted({cid for cid, score in by_score.items() if is_fail(score)})
    pdf = get_doc(args.document)
    processed = None
    if pdf:
        try:
            processed, _ = build_index(pdf, args.top_k)
        except Exception as exc:
            print(f"[WARN] Live retrieval diagnostic unavailable: {exc}")
    else:
        print("[WARN] Source PDF not found; use --document to enable retrieval diagnostics.")

    rows = []
    for cid in failed_ids:
        result, score, case = by_result.get(cid, {}), by_score[cid], by_case.get(cid, {})
        actual = result.get("actual_response") or {}
        question = str(case.get("question") or result.get("question") or "")
        expected = case.get("expected_answer") or result.get("expected_answer") or ""
        chunks, indexed_matches = [], []
        if processed is not None:
            chunks = processed.retrieve(query=question, top_k=args.top_k)
            for c in processed.chunks:
                found, clue = clue_match(c.text, expected)
                if found:
                    indexed_matches.append({
                        "page": c.page_number, "chunk_id": c.chunk_id,
                        "matched_clue": clue, "text_excerpt": c.text[:1200]
                    })
        retrieved_text = "\n".join(c.text for c in chunks)
        top_match, top_clue = clue_match(retrieved_text, expected) if processed is not None else (None, None)
        index_match = bool(indexed_matches) if processed is not None else None
        abstained = actual.get("abstained")
        error = result.get("error")
        failure_type = str(score.get("failure_type") or score.get("failure_mode") or
                           score.get("status") or "unknown").lower()
        # Some result rows omit the abstained flag (None) even when the scorer
        # explicitly classifies the case as a false abstention. Preserve the raw
        # value, but use the scorer label only as a fallback for diagnostics.
        abstention_for_diagnostics = abstained
        if abstention_for_diagnostics is None and "false_abstention" in failure_type:
            abstention_for_diagnostics = True

        # Diagnostic patterns are derived from trace observations, not hardcoded
        # assumptions that all failures of one score label share a cause.
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

        rows.append({
            "id": cid, "category": case.get("category") or result.get("category"),
            "question": question, "expected_behavior": case.get("expected_behavior"),
            "expected_answer": expected, "actual_answer": actual.get("answer"),
            "abstained": abstained, "confidence": actual.get("confidence"),
            "abstention_reason": actual.get("abstention_reason"),
            "score_status": score.get("status"), "failure_type": failure_type,
            "score_reason": score.get("reason") or score.get("explanation") or score.get("details"),
            "retrieval_diagnostic_available": processed is not None,
            "expected_answer_clue_found_in_index": index_match,
            "indexed_match_pages": sorted({x["page"] for x in indexed_matches}),
            "indexed_matches": indexed_matches[:10],
            "expected_answer_clue_in_top_k": top_match, "top_k_match_clue": top_clue,
            "retrieved_pages": [c.page_number for c in chunks],
            "retrieved_chunks": [{"page": c.page_number, "chunk_id": c.chunk_id,
                                  "text_excerpt": c.text[:1800]} for c in chunks],
            "diagnostic_pattern": pattern, "diagnostic_observation": observation,
            "root_cause_confirmed": False,
            "note": "Diagnostic pattern is not proof of causation. Validate the excerpts before asserting a root cause."
        })

    out_jsonl = (HERE / args.output_jsonl).resolve()
    with out_jsonl.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Cluster on observed diagnostic signature and expected behavior. Keep
    # dataset category as per-case metadata, not as a cluster key: e.g. a
    # straightforward question and one with irrelevant context can share the
    # same retrieval-miss cluster while retaining their different categories.
    groups = defaultdict(list)
    for row in rows:
        key = (row["diagnostic_pattern"], str(row["expected_behavior"]))
        groups[key].append(row)

    counts = Counter(row["diagnostic_pattern"] for row in rows)
    lines = [
        "# Evidence-Driven Failure Cluster Report", "",
        f"- Failed cases analyzed: **{len(rows)}**",
        f"- Live retrieval diagnostics: **{'available' if processed is not None else 'unavailable'}**",
        f"- Top-k: **{args.top_k}**",
        "- Candidate clusters are based on observed diagnostic signatures, not causal proof.",
        "- Lexical/numeric matching is heuristic: a miss does not prove semantic absence.",
        "", "## Diagnostic pattern counts", ""
    ]
    lines += [f"- `{k}`: **{v}** case(s)" for k, v in counts.most_common()]
    lines += ["", "## Candidate behavioral clusters", ""]
    for i, (key, members) in enumerate(sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])), 1):
        pattern, expected_behavior = key
        categories = sorted({str(m.get("category")) for m in members})
        lines += [f"### Cluster {i}: `{pattern}`", "",
                  f"- Cases: {', '.join(m['id'] for m in members)}",
                  f"- Expected behavior: `{expected_behavior}`",
                  f"- Dataset categories represented: `{', '.join(categories)}`", ""]
        for m in members:
            lines += [
                f"**{m['id']} — {m['question']}**",
                f"- Scoring label: `{m['failure_type']}`; abstained: `{m['abstained']}`.",
                f"- Observation: {m['diagnostic_observation']}",
                f"- Expected-answer clue in index: `{m['expected_answer_clue_found_in_index']}`; "
                f"in top-k: `{m['expected_answer_clue_in_top_k']}`; retrieved pages: `{m['retrieved_pages']}`.",
            ]
            if m["indexed_match_pages"]:
                lines.append(f"- Indexed matching pages: `{m['indexed_match_pages']}`.")
            if m["score_reason"]:
                lines.append(f"- Scorer explanation: {str(m['score_reason'])[:400]}")
            lines.append("")
        lines += [
            "**Validation needed:** compare the stored chunks and full source passage. Split this cluster if the cases show different mechanisms.",
            ""
        ]
    lines += [
        "## Per-case summary", "",
        "| Case | Scoring label | Diagnostic pattern | In index | In top-k | Retrieved pages |",
        "|---|---|---|---|---|---|"
    ]
    for r in rows:
        lines.append(f"| {r['id']} | `{r['failure_type']}` | `{r['diagnostic_pattern']}` | "
                     f"`{r['expected_answer_clue_found_in_index']}` | "
                     f"`{r['expected_answer_clue_in_top_k']}` | `{r['retrieved_pages']}` |")
    lines += [
        "", "## Limitations and interpretation", "",
        "1. Expected-answer matching is lexical/numeric and can miss paraphrases or find an irrelevant occurrence.",
        "2. An indexed clue missing from top-k supports a retrieval-miss diagnosis, but does not prove BM25 is the sole cause.",
        "3. A clue in top-k alongside abstention suggests answer-generation/evidence-use behavior needs inspection.",
        "4. Root causes are intentionally not marked confirmed automatically.",
        "5. The report should be used to discover candidate patterns; validate them against the source and traces before final submission.",
        "", "## Next validation", "",
        "Review the retrieved excerpts for each candidate cluster, document the evidence for/against a shared mechanism, and record a proposed fix. Rerun evaluation after any fix to measure regressions.",
        ""
    ]
    report = (HERE / args.output_report).resolve()
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nAnalyzed {len(rows)} failed case(s).")
    for pattern, count in counts.most_common():
        print(f"  {pattern}: {count}")
    print(f"Saved diagnostics: {out_jsonl}")
    print(f"Saved report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
