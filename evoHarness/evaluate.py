#!/usr/bin/env python3
"""
Adversarial Evaluation Harness — Test Runner.

Executes test cases from test_dataset.json against the GroundTruth QA application.
Reuses the indexed document (BM25 retriever) across all queries, captures structured
actual responses alongside expected ground truth, handles failures gracefully, and
records results to results.jsonl.
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Any, Optional, Union

# ── Dynamic Path Setup ───────────────────────────────────────────────────────
# Locate DocumentClassifier relative to this script or current working directory
SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent

DOC_CLASSIFIER_DIR = WORKSPACE_ROOT / "DocumentClassifier"
if not DOC_CLASSIFIER_DIR.exists():
    # Fallback if run from a different root structure
    DOC_CLASSIFIER_DIR = Path.cwd() / "DocumentClassifier"

if str(DOC_CLASSIFIER_DIR) not in sys.path:
    sys.path.insert(0, str(DOC_CLASSIFIER_DIR))

# Ensure environment variables from .env are loaded (search locations)
from dotenv import load_dotenv

for candidate_env in [
    SCRIPT_DIR / ".env",
    Path.cwd() / ".env",
    DOC_CLASSIFIER_DIR / ".env",
    WORKSPACE_ROOT / ".env",
]:
    if candidate_env.is_file():
        load_dotenv(candidate_env)
        break

# Import existing application modules
from app.config import Config, load_config
from app.document import ProcessedDocument, process_document
from app.qa_system import ask
from app.schemas import QAResponse

# Ensure stdout/stderr handles UTF-8 on Windows consoles without charmap crash
if sys.platform == "win32":
    try:
        if sys.stdout.encoding != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr.encoding != "utf-8":
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eval_harness")


# ── Secret Sanitization ──────────────────────────────────────────────────────


def sanitize_text(text: Optional[str], secret: Optional[str]) -> Optional[str]:
    """Redact secret API keys from strings before logging or writing."""
    if not text or not secret:
        return text
    sanitized = text.replace(secret, "[REDACTED_API_KEY]")
    import urllib.parse
    encoded_secret = urllib.parse.quote(secret)
    if encoded_secret != secret:
        sanitized = sanitized.replace(encoded_secret, "[REDACTED_API_KEY]")
    return sanitized


# ── Document & Dataset Discovery ─────────────────────────────────────────────


def find_document(custom_path: Optional[str] = None) -> Path:
    """Locate the document to be indexed and queried."""
    if custom_path:
        p = Path(custom_path)
        if not p.is_file():
            raise FileNotFoundError(f"Specified document not found: {p}")
        return p

    # Search standard docs/ folder inside DocumentClassifier
    docs_dir = DOC_CLASSIFIER_DIR / "docs"
    if docs_dir.exists():
        supported = {".pdf", ".txt", ".md", ".text"}
        candidates = [f for f in docs_dir.iterdir() if f.is_file() and f.suffix.lower() in supported]
        if candidates:
            return candidates[0]

    raise FileNotFoundError(
        f"No document found in {docs_dir}. Please specify path via --doc."
    )


def resolve_dataset_path(dataset_path_str: str) -> Path:
    """Find the dataset file checking multiple standard locations."""
    path = Path(dataset_path_str)
    if path.is_file():
        return path

    candidates = [
        SCRIPT_DIR / dataset_path_str,
        Path.cwd() / dataset_path_str,
        DOC_CLASSIFIER_DIR / dataset_path_str,
        # Check alternative file extension if .json was requested but .jsonl exists
        SCRIPT_DIR / "test_dataset.json",
        DOC_CLASSIFIER_DIR / "test_dataset.jsonl",
    ]

    for c in candidates:
        if c.is_file():
            return c

    raise FileNotFoundError(
        f"Dataset file '{dataset_path_str}' could not be found. "
        f"Searched: {[str(c) for c in candidates]}"
    )


def load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    """Load test cases from JSON or JSONL file.

    Handles:
    - Root object with a 'cases' key: {"cases": [...]}
    - Direct JSON array: [...]
    - JSON Lines (JSONL): one JSON object per line
    """
    content = dataset_path.read_text(encoding="utf-8").strip()
    if not content:
        return []

    # 1. Try standard JSON
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "cases" in data:
            return data["cases"]
        elif isinstance(data, list):
            return data
        else:
            raise ValueError(
                f"Unexpected JSON format in {dataset_path.name}: expected dict with 'cases' or list."
            )
    except json.JSONDecodeError:
        # 2. Try JSONL
        cases = []
        for line_num, line in enumerate(content.splitlines(), 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                cases.append(json.loads(line_str))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Failed to parse line {line_num} in {dataset_path.name}: {exc}"
                ) from exc
        return cases


# ── Evaluation Runner ────────────────────────────────────────────────────────


def run_evaluation(
    dataset_path: Path,
    output_path: Path,
    document_path: Path,
    config: Config,
    limit: Optional[int] = None,
    filter_ids: Optional[list[str]] = None,
    delay: float = 13.0,
) -> None:
    """Run evaluation cases and stream results to JSONL output file."""
    # Load test cases
    logger.info("Loading test cases from: %s", dataset_path)
    cases = load_dataset(dataset_path)
    logger.info("Loaded %d test cases in total.", len(cases))

    # Apply case ID filter if requested
    if filter_ids:
        filter_set = set(filter_ids)
        cases = [c for c in cases if c.get("id") in filter_set]
        logger.info("Filtered to %d case(s) matching IDs: %s", len(cases), filter_ids)

    # Apply limit if requested
    if limit is not None and limit > 0:
        cases = cases[:limit]
        logger.info("Limiting execution to first %d case(s).", len(cases))

    if not cases:
        logger.warning("No test cases to execute.")
        return

    # Index document ONCE
    logger.info("Indexing source document: %s (%s)", document_path.name, document_path)
    logger.info("Building BM25 retriever index (this happens once and is reused for all cases)...")
    processed_doc: ProcessedDocument = process_document(
        document_path,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )
    logger.info(
        "Document indexed successfully: %d pages, %d chunks.",
        processed_doc.report.extracted_pages,
        len(processed_doc.chunks),
    )

    # Ensure output parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_count = len(cases)
    success_count = 0
    failure_count = 0

    logger.info("Starting test execution -> streaming results to: %s\n", output_path)

    with open(output_path, "w", encoding="utf-8") as out_f:
        for index, case in enumerate(cases, 1):
            case_id = case.get("id", f"UNKNOWN_{index}")
            category = case.get("category", "unspecified")
            question = str(case.get("question", "")).strip()

            print(f"[{index}/{total_count}] Case {case_id} [{category}]")
            print(f"      Question: {question[:90]}{'...' if len(question) > 90 else ''}")

            actual_response_dict: Optional[dict[str, Any]] = None
            error_message: Optional[str] = None

            try:
                if not question:
                    raise ValueError("Question field is empty in test case.")

                # Call the existing application's question-answering logic
                response: QAResponse = ask(
                    document=processed_doc,
                    question=question,
                    config=config,
                )
                actual_response_dict = response.model_dump()
                success_count += 1

                status_summary = (
                    f"Abstained ({response.abstention_reason[:30]}...)"
                    if response.abstained
                    else f"Answered (conf={response.confidence:.0%}, pages={response.page_numbers})"
                )
                print(f"      [OK] Status: {status_summary}\n")

            except Exception as exc:
                failure_count += 1
                raw_err = f"{type(exc).__name__}: {exc}"
                error_message = sanitize_text(raw_err, config.api_key)
                print(f"      [FAIL] Error: {error_message}\n")

            # Capture structured record
            record = {
                "id": case_id,
                "category": category,
                "question": question,
                "expected_behavior": case.get("expected_behavior"),
                "expected_answer": case.get("expected_answer"),
                "source_pages": case.get("source_pages"),
                "verification_status": case.get("verification_status"),
                "search_terms": case.get("search_terms"),
                "verification_note": case.get("verification_note"),
                "actual_response": actual_response_dict,
                "error": error_message,
            }

            # Write line-delimited JSON and flush immediately
            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()

            # Pacing delay between cases to stay within free-tier rate limits (5 RPM)
            if delay > 0 and index < total_count:
                print(f"      [PAUSE] Waiting {delay:.1f}s to respect API rate limits...")
                time.sleep(delay)

    # Final summary display
    print("=" * 65)
    print("EVALUATION RUN COMPLETE")
    print("=" * 65)
    print(f"Total Cases:     {total_count}")
    print(f"Completed:       {success_count}")
    print(f"Failed (Errors): {failure_count}")
    print(f"Saved Results:   {output_path.resolve()}")
    print("=" * 65)


# ── CLI Entry Point ──────────────────────────────────────────────────────────


def main() -> None:
    """Parse arguments and start the evaluation runner."""
    parser = argparse.ArgumentParser(
        description="GroundTruth QA Adversarial Evaluation Harness Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--dataset",
        "-d",
        type=str,
        default="test_dataset.json",
        help="Path or filename of the test dataset (JSON or JSONL).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="results.jsonl",
        help="Path where output JSONL results will be saved.",
    )
    parser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Limit the number of test cases to run (e.g. 2 for quick testing).",
    )
    parser.add_argument(
        "--case-id",
        "-c",
        nargs="+",
        default=None,
        help="Specific test case ID(s) to execute (e.g. -c TC001 TC002).",
    )
    parser.add_argument(
        "--doc",
        type=str,
        default=None,
        help="Path to source document PDF. Auto-detected from DocumentClassifier/docs if omitted.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=13.0,
        help="Delay in seconds between test cases to respect API rate limits (default: 13.0s for 5 RPM).",
    )

    args = parser.parse_args()

    # Load configuration
    try:
        config = load_config()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print("Ensure GEMINI_API_KEY is set in your environment or in a .env file.", file=sys.stderr)
        sys.exit(1)

    # Locate dataset and document
    try:
        dataset_path = resolve_dataset_path(args.dataset)
    except FileNotFoundError as exc:
        print(f"Dataset error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        doc_path = find_document(args.doc)
    except FileNotFoundError as exc:
        print(f"Document error: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = SCRIPT_DIR / args.output

    run_evaluation(
        dataset_path=dataset_path,
        output_path=output_path,
        document_path=doc_path,
        config=config,
        limit=args.limit,
        filter_ids=args.case_id,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
