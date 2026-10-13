"""
Configuration for the GroundTruth QA system.

Reads settings from environment variables (with .env file support)
and exposes them as a typed configuration object.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env file if present (does not override existing env vars)
load_dotenv()


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables."""

    api_key: str
    model: str
    temperature: float
    max_output_tokens: int
    top_k_chunks: int
    chunk_size: int
    chunk_overlap: int


def load_config() -> Config:
    """Load and validate configuration from environment variables.

    Returns:
        A frozen Config instance.

    Raises:
        ValueError: If GEMINI_API_KEY is missing or empty.
    """
    raw_key = os.getenv("GEMINI_API_KEY", "")
    api_key = raw_key.strip().strip("\"'")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is required. "
            "Copy .env.example to .env and add your API key."
        )

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    try:
        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))
    except ValueError:
        temperature = 0.2

    try:
        max_output_tokens = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "8192"))
    except ValueError:
        max_output_tokens = 8192

    try:
        top_k_chunks = int(os.getenv("QA_TOP_K_CHUNKS", "5"))
    except ValueError:
        top_k_chunks = 10

    try:
        chunk_size = int(os.getenv("QA_CHUNK_SIZE", "1200"))
    except ValueError:
        chunk_size = 1200

    try:
        chunk_overlap = int(os.getenv("QA_CHUNK_OVERLAP", "250"))
    except ValueError:
        chunk_overlap = 250

    return Config(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        top_k_chunks=top_k_chunks,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

