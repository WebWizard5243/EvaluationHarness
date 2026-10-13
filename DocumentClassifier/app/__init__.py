"""GroundTruth QA — document-based question-answering package."""

from app.schemas import QAResponse
from app.config import Config, load_config
from app.document import (
    DocumentChunk,
    ExtractionReport,
    ProcessedDocument,
    process_document,
    process_pdf,
    process_text,
)
from app.qa_system import ask

__all__ = [
    "QAResponse",
    "Config",
    "load_config",
    "DocumentChunk",
    "ExtractionReport",
    "ProcessedDocument",
    "process_document",
    "process_pdf",
    "process_text",
    "ask",
]
