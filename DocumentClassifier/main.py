#!/usr/bin/env python3
"""
GroundTruth QA — Command-line interface.

Automatically loads and indexes the document from the docs/ folder once,
then provides an interactive prompt for asking questions with chunk-level
retrieval and source page citations.
"""

import sys
import json
import logging
from pathlib import Path

from app.config import load_config
from app.document import process_document, ProcessedDocument
from app.qa_system import ask

# Configure logging — warnings and above to stderr by default
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
)

# ── Constants ────────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent / "docs"
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".text"}


# ── Document discovery ───────────────────────────────────────────────────────


def _find_document() -> Path:
    """Find a single document file inside the docs/ folder.

    Returns:
        Path to the document file.

    Raises:
        FileNotFoundError: If docs/ is missing or empty.
    """
    if not DOCS_DIR.exists():
        raise FileNotFoundError(
            f"The docs/ folder does not exist. "
            f"Please create it at: {DOCS_DIR}"
        )

    files = [
        f for f in DOCS_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        raise FileNotFoundError(
            f"No supported documents found in docs/. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # Use the first supported file found
    return files[0]


# ── Display ──────────────────────────────────────────────────────────────────


def _print_response(data: dict) -> None:
    """Pretty-print the QA response to stdout."""
    print("\n" + "=" * 65)
    print("ANSWER")
    print("=" * 65)

    if data.get("abstained"):
        print(f"\n⚠  Abstained: {data.get('abstention_reason', 'N/A')}")
    else:
        print(f"\n{data['answer']}")

    page_numbers = data.get("page_numbers") or []
    if page_numbers:
        pages_str = ", ".join(str(p) for p in sorted(page_numbers))
        print(f"\n📍 Source Page(s): {pages_str}")

    evidence = data.get("evidence") or []
    if evidence:
        print("\n— Supporting Evidence —")
        for i, quote in enumerate(evidence, 1):
            print(f"  {i}. {quote}")

    confidence = data.get("confidence", 0.0)
    print(f"\nConfidence: {confidence:.0%}")
    print("=" * 65)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    """Run the interactive CLI."""
    print("\n╔═════════════════════════════════════════════════════════════╗")
    print("║                  GroundTruth QA System                      ║")
    print("╚═════════════════════════════════════════════════════════════╝\n")

    # ── Load configuration ───────────────────────────────────────────────
    try:
        config = load_config()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Discover document ────────────────────────────────────────────────
    try:
        doc_path = _find_document()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"📄 Found Document: {doc_path.name}")
    print(f"   File size:      {doc_path.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"   Model:          {config.model}")
    print(f"   Top chunks:     {config.top_k_chunks}\n")

    # ── Process document once ────────────────────────────────────────────
    print("Indexing document (extracting pages and building BM25 index)…")
    try:
        processed_doc: ProcessedDocument = process_document(
            doc_path,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
    except Exception as exc:
        print(f"Error processing document: {exc}", file=sys.stderr)
        sys.exit(1)

    report = processed_doc.report
    print(
        f"✔ Processed {report.extracted_pages}/{report.total_pages} page(s) "
        f"into {report.total_chunks} search chunks."
    )
    if report.empty_pages:
        print(f"  ⚠ Note: {len(report.empty_pages)} empty page(s) detected: {report.empty_pages[:10]}")
    if report.failed_pages:
        print(f"  ⚠ Warning: {len(report.failed_pages)} page(s) failed extraction: {list(report.failed_pages.keys())[:10]}")

    print("\nDocument ready! Ask questions below (type 'quit' to exit).\n")

    # ── Interactive question loop ────────────────────────────────────────
    while True:
        try:
            question = input("❓ Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        # ── Query the QA system ──────────────────────────────────────────
        print("\nSearching relevant excerpts and generating grounded answer…\n")
        try:
            response = ask(
                document=processed_doc,
                question=question,
                config=config,
            )
        except ValueError as exc:
            print(f"Input error: {exc}\n", file=sys.stderr)
            continue
        except RuntimeError as exc:
            print(f"System error: {exc}\n", file=sys.stderr)
            continue

        # _print_response(response.model_dump())

        # Raw JSON
        print("\n— Raw Structured JSON —")
        print(json.dumps(response.model_dump(), indent=2))
        print()


if __name__ == "__main__":
    main()
