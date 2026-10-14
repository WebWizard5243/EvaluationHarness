"""
Document processing and retrieval module for GroundTruth QA.

Handles:
- PDF text extraction with explicit tracking of empty pages and extraction failures.
- Overlapping chunk generation with preserved page numbers and boundaries.
- Lightweight, zero-dependency BM25 retrieval for ranking chunks.
- Document pre-processing and session reuse.
"""

import re
import math
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union
from collections import Counter

from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

# ── Standard Stopwords ────────────────────────────────────────────────────────

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "could", "did", "do", "does",
    "doing", "down", "during", "each", "few", "for", "from", "further", "had",
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on",
    "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "she", "should", "so", "some", "such", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "wasn't", "we", "were", "weren't", "what", "when", "where",
    "which", "while", "who", "whom", "why", "with", "would", "you", "your", "yours"
}


def tokenize(text: str) -> list[str]:
    """Extract alphanumeric terms (minimum 2 chars) for indexing/search."""
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_\-\.]{2,}\b", text)]


# ── Data Models ───────────────────────────────────────────────────────────────


@dataclass
class DocumentChunk:
    """A slice of document text tagged with source metadata."""

    chunk_id: str
    text: str
    page_number: int  # 1-indexed source page
    char_start: int
    char_end: int
    source_name: str


@dataclass
class ExtractionReport:
    """Detailed summary of document extraction results."""

    total_pages: int
    extracted_pages: int
    empty_pages: list[int] = field(default_factory=list)
    failed_pages: dict[int, str] = field(default_factory=dict)
    total_chunks: int = 0


# ── Pure-Python BM25 Retriever ───────────────────────────────────────────────


class BM25Retriever:
    """Okapi BM25 index over document chunks with zero external dependencies."""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.N = len(chunks)

        # Precompute tokens and frequencies
        self.chunk_tokens: list[list[str]] = []
        self.chunk_token_counts: list[Counter] = []
        self.chunk_lens: list[int] = []
        self.df: Counter = Counter()

        for chunk in chunks:
            raw_tokens = tokenize(chunk.text)
            filtered = [t for t in raw_tokens if t not in STOPWORDS]
            # Fall back to raw tokens if all tokens were stopwords
            tokens = filtered if filtered else raw_tokens

            self.chunk_tokens.append(tokens)
            counts = Counter(tokens)
            self.chunk_token_counts.append(counts)
            self.chunk_lens.append(len(tokens))

            for t in set(tokens):
                self.df[t] += 1

        self.avgdl = (sum(self.chunk_lens) / self.N) if self.N > 0 else 1.0

    
    def score_chunk(
        self,
        chunk_idx: int,
        query_tokens: list[str],
        query_text: str,
    ) -> float:
        """Score a chunk using BM25 plus phrase and term-proximity signals."""
        if self.N == 0:
            return 0.0

        chunk = self.chunks[chunk_idx]
        chunk_text = chunk.text.lower()
        doc_len = self.chunk_lens[chunk_idx]
        counts = self.chunk_token_counts[chunk_idx]

        score = 0.0
        terms_matched = 0

        # 1. Existing BM25 term scoring
        for qt in query_tokens:
            if qt in counts:
                terms_matched += 1
                n_qt = self.df.get(qt, 0)
                idf = math.log(
                    (self.N - n_qt + 0.5) / (n_qt + 0.5) + 1.0
                )
                freq = counts[qt]
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (
                    1.0 - self.b + self.b * (doc_len / self.avgdl)
                )
                score += idf * (numerator / denominator)

        if query_tokens and terms_matched:
            coverage = terms_matched / len(query_tokens)
            score *= 1.0 + 0.5 * coverage

        # 2. Phrase bonus: use original text so stopwords like "and"
        #    are retained. Test progressively shorter query n-grams.
        normalized_query = re.sub(
            r"\s+", " ", query_text.lower()
        ).strip(" ?.,!;:")

        normalized_chunk = re.sub(
            r"\s+", " ", chunk_text
        )

        query_words = re.findall(r"\b[\w.-]+\b", normalized_query)
        phrase_bonus = 0.0

        # Longer exact phrases are more informative than shorter ones.
        max_n = min(5, len(query_words))
        for n in range(2, max_n + 1):
            for start in range(len(query_words) - n + 1):
                phrase = " ".join(query_words[start:start + n])

                if phrase in normalized_chunk:
                    phrase_bonus += 0.5 * (n - 1)

        score += phrase_bonus

        # 3. Proximity bonus: reward chunks where query terms occur
        #    close together, even if punctuation separates them.
        positions = {}
        for token in set(query_tokens):
            matches = [
                m.start()
                for m in re.finditer(
                    rf"\b{re.escape(token)}\b", normalized_chunk
                )
            ]
            if matches:
                positions[token] = matches

        matched_terms = list(positions.keys())

        if len(matched_terms) >= 2:
            # Find the narrowest span covering all matched query terms.
            occurrences = sorted(
                (pos, token)
                for token, offsets in positions.items()
                for pos in offsets
            )

            left = 0
            window_counts = {}
            best_span = len(normalized_chunk)
            required = len(matched_terms)

            for right, (pos, token) in enumerate(occurrences):
                window_counts[token] = window_counts.get(token, 0) + 1

                while len(window_counts) == required:
                    best_span = min(
                        best_span,
                        occurrences[right][0] - occurrences[left][0],
                    )
                    left_token = occurrences[left][1]
                    window_counts[left_token] -= 1
                    if window_counts[left_token] == 0:
                        del window_counts[left_token]
                    left += 1

            # Closer terms receive a larger bonus.
            score += 3.0 * required / (1.0 + best_span / 100.0)

        # 4. Combined-condition bonus: reward chunks that contain
        #    all searchable query terms, not just a partial overlap.
        if query_tokens and terms_matched == len(set(query_tokens)):
            score += 2.0

        return score



    
    
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        min_score: float = 0.01,
    ) -> list[DocumentChunk]:
        """Retrieve the top_k most relevant chunks for a question."""
        if not self.chunks:
            return []

        raw_query_tokens = tokenize(query)
        filtered_query_tokens = [t for t in raw_query_tokens if t not in STOPWORDS]
        query_tokens = filtered_query_tokens if filtered_query_tokens else raw_query_tokens

        if not query_tokens:
            # Return initial chunks if query has no searchable terms
            return self.chunks[:top_k]

        scored_chunks: list[tuple[float, int]] = []
        for idx in range(self.N):
            s = self.score_chunk(idx, query_tokens, query)
            if s > min_score:
                scored_chunks.append((s, idx))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        selected: list[DocumentChunk] = []
        seen_pages: Counter = Counter()

        # Prioritize diversity across pages while picking the highest scoring chunks
        for score, idx in scored_chunks:
            chunk = self.chunks[idx]
            # Allow up to 2 chunks per page to avoid a single long page dominating
            if seen_pages[chunk.page_number] < 2 or len(scored_chunks) <= top_k:
                selected.append(chunk)
                seen_pages[chunk.page_number] += 1
            if len(selected) >= top_k:
                break

        # Fallback if diversified filter didn't fill top_k
        if len(selected) < top_k and scored_chunks:
            for score, idx in scored_chunks:
                chunk = self.chunks[idx]
                if chunk not in selected:
                    selected.append(chunk)
                if len(selected) >= top_k:
                    break

        return selected


# ── Processed Document Container ─────────────────────────────────────────────


class ProcessedDocument:
    """An indexed, searchable representation of a source document.

    Can be reused across multiple questions in the same session without
    re-reading or re-indexing.
    """

    def __init__(
        self,
        source_name: str,
        chunks: list[DocumentChunk],
        report: ExtractionReport,
    ):
        self.source_name = source_name
        self.chunks = chunks
        self.report = report
        self.retriever = BM25Retriever(chunks)

    def retrieve(self, query: str, top_k: int = 10) -> list[DocumentChunk]:
        """Retrieve the most relevant chunks for the given query."""
        return self.retriever.retrieve(query=query, top_k=top_k)

    def __repr__(self) -> str:
        return (
            f"<ProcessedDocument '{self.source_name}' "
            f"pages={self.report.extracted_pages}/{self.report.total_pages} "
            f"chunks={len(self.chunks)}>"
        )


# ── Chunking Logic ───────────────────────────────────────────────────────────


def chunk_page_text(
    page_text: str,
    page_number: int,
    source_name: str,
    chunk_size: int = 1200,
    chunk_overlap: int = 250,
) -> list[DocumentChunk]:
    """Split page text into overlapping, coherent chunks."""
    text = page_text.strip()
    if not text:
        return []

    if len(text) <= chunk_size:
        return [
            DocumentChunk(
                chunk_id=f"p{page_number}_c1",
                text=text,
                page_number=page_number,
                char_start=0,
                char_end=len(text),
                source_name=source_name,
            )
        ]

    chunks: list[DocumentChunk] = []
    start = 0
    chunk_idx = 1
    step = max(100, chunk_size - chunk_overlap)

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Look for natural paragraph or sentence boundary near the end
        if end < len(text):
            search_window = text[start + int(chunk_size * 0.7) : end]
            boundary_offsets = [
                search_window.rfind("\n\n"),
                search_window.rfind(".\n"),
                search_window.rfind(". "),
                search_window.rfind("; "),
            ]
            valid_breaks = [b for b in boundary_offsets if b != -1]
            if valid_breaks:
                best_break = max(valid_breaks)
                end = start + int(chunk_size * 0.7) + best_break + 1

        chunk_str = text[start:end].strip()
        if chunk_str:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"p{page_number}_c{chunk_idx}",
                    text=chunk_str,
                    page_number=page_number,
                    char_start=start,
                    char_end=end,
                    source_name=source_name,
                )
            )
            chunk_idx += 1

        if end >= len(text):
            break

        start += step

    return chunks


# ── Extraction & Document Loaders ─────────────────────────────────────────────


def process_pdf(
    file_path: Union[str, Path],
    chunk_size: int = 1200,
    chunk_overlap: int = 250,
) -> ProcessedDocument:
    """Extract, chunk, and index a PDF file with explicit error handling.

    Args:
        file_path: Path to the PDF document.
        chunk_size: Target characters per chunk.
        chunk_overlap: Overlap characters between consecutive chunks.

    Returns:
        A ready-to-query ProcessedDocument instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If no text could be extracted from any page.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF document not found: {path}")

    reader = PdfReader(str(path))
    total_pages = len(reader.pages)

    extracted_pages: list[tuple[int, str]] = []
    empty_pages: list[int] = []
    failed_pages: dict[int, str] = {}

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        try:
            text = page.extract_text()
        except Exception as exc:
            logger.warning(
                "Failed to extract text from page %d of %s: %s",
                page_num,
                path.name,
                exc,
            )
            failed_pages[page_num] = f"{type(exc).__name__}: {exc}"
            continue

        if text is None or not text.strip():
            empty_pages.append(page_num)
            continue

        extracted_pages.append((page_num, text.strip()))

    if not extracted_pages:
        raise ValueError(
            f"Failed to extract text from '{path.name}'. "
            f"All {total_pages} page(s) were empty or failed to extract "
            f"({len(empty_pages)} empty, {len(failed_pages)} failed). "
            f"The document may be scanned or image-only."
        )

    # Generate overlapping chunks per page
    all_chunks: list[DocumentChunk] = []
    for page_num, page_text in extracted_pages:
        page_chunks = chunk_page_text(
            page_text=page_text,
            page_number=page_num,
            source_name=path.name,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        all_chunks.extend(page_chunks)

    report = ExtractionReport(
        total_pages=total_pages,
        extracted_pages=len(extracted_pages),
        empty_pages=empty_pages,
        failed_pages=failed_pages,
        total_chunks=len(all_chunks),
    )

    return ProcessedDocument(
        source_name=path.name,
        chunks=all_chunks,
        report=report,
    )


def process_text(
    text: str,
    source_name: str = "document",
    chunk_size: int = 1200,
    chunk_overlap: int = 250,
) -> ProcessedDocument:
    """Process plain-text content into an indexed ProcessedDocument."""
    clean_text = text.strip()
    if not clean_text:
        raise ValueError("Document text must not be empty.")

    chunks = chunk_page_text(
        page_text=clean_text,
        page_number=1,
        source_name=source_name,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    report = ExtractionReport(
        total_pages=1,
        extracted_pages=1,
        empty_pages=[],
        failed_pages={},
        total_chunks=len(chunks),
    )

    return ProcessedDocument(
        source_name=source_name,
        chunks=chunks,
        report=report,
    )


def process_document(
    source: Union[str, Path, ProcessedDocument],
    chunk_size: int = 1200,
    chunk_overlap: int = 250,
) -> ProcessedDocument:
    """Unified entry point for document processing.

    Accepts an existing ProcessedDocument, a Path or path string to a PDF or text
    file, or a raw text string.
    """
    if isinstance(source, ProcessedDocument):
        return source

    # Check if string/path points to an existing file
    potential_path = Path(source) if isinstance(source, (str, Path)) else None
    if potential_path and potential_path.is_file():
        if potential_path.suffix.lower() == ".pdf":
            return process_pdf(
                potential_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        else:
            raw_text = potential_path.read_text(encoding="utf-8")
            return process_text(
                raw_text,
                source_name=potential_path.name,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

    # Treat as raw text string
    if isinstance(source, str):
        return process_text(
            source,
            source_name="text_input",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    raise ValueError(f"Unsupported document source type: {type(source)}")
