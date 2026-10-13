# GroundTruth QA

A document-based question-answering application powered by the Gemini API. GroundTruth QA processes documents of any length (including 100+ page corporate PDFs) without truncation, retrieving the most relevant sections across the entire document and returning strictly grounded answers with source page numbers and quotations.

## Features

- **Full-Document Retrieval without Truncation** — Long documents and PDFs are split into overlapping chunks, indexed via a fast, zero-dependency BM25 retriever, and searched across all pages.
- **Page Number Attribution** — Every supporting piece of evidence references the exact page number where it appears.
- **Single-Pass Processing & Session Reuse** — Documents are extracted, chunked, and indexed once upon startup, enabling instant responses across multiple questions in the same session.
- **Robust PDF Handling** — Explicit tracking and reporting of empty pages and extraction errors per page.
- **Strict Grounding & Abstention** — Gemini answers using only the retrieved excerpts as its sole factual source and declines to answer with an explicit reason when evidence is missing.
- **Validated Structured Schema** — Validated with Pydantic v2.
- **Exponential Back-Off Retry Logic** — Handles transient API demand spikes (503) and rate limits (429) automatically.
- **Prompt-Injection Defense** — Document text is treated strictly as untrusted data.

## Project Structure

```
├── app/
│   ├── __init__.py        # Package exports
│   ├── config.py          # Environment settings & model configuration
│   ├── document.py        # PDF extraction, chunking, and BM25 retriever
│   ├── qa_system.py       # Core QA orchestration & Gemini API integration
│   └── schemas.py         # Pydantic response schema (QAResponse)
├── docs/                  # Put your document(s) here (PDF, TXT, MD)
├── main.py                # Interactive CLI
├── .env.example           # Environment template
├── .gitignore
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Set up virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
cp .env.example .env
```

Add your Gemini API key in `.env`:
```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
```

### 3. Place your document

Put your document (e.g., `IntelCompanyDocumentation.pdf`) into the `docs/` directory.

### 4. Run the application

```bash
python main.py
```

The system indexes the document once, prints extraction statistics, and starts an interactive prompt:

```
📄 Found Document: IntelCompanyDocumentation.pdf
   File size:      33.04 MB
   Model:          gemini-2.5-flash
   Top chunks:     5

Indexing document (extracting pages and building BM25 index)…
✔ Processed 126/126 page(s) into 1154 search chunks.

Document ready! Ask questions below (type 'quit' to exit).

❓ Question: was 2025 the ceo first year at intel?
```

Example response:

```
=================================================================
ANSWER
=================================================================

Yes, according to the letter from the Intel CEO, 2025 was the CEO's first year in that role.

📍 Source Page(s): 3

— Supporting Evidence —
  1. [Page 3] "2025 was a pivotal year for Intel. During my first year as CEO, we took decisive steps to reset the company..."

Confidence: 100%
=================================================================
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Gemini API key from AI Studio |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `GEMINI_TEMPERATURE` | `0.2` | Sampling temperature |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Maximum tokens in model response |
| `QA_TOP_K_CHUNKS` | `5` | Number of relevant chunks retrieved per question |
| `QA_CHUNK_SIZE` | `1200` | Target character count per chunk |
| `QA_CHUNK_OVERLAP` | `250` | Overlap characters between consecutive chunks |

## Programmatic Usage

You can process a document once and query it programmatically:

```python
from app.document import process_document
from app.qa_system import ask

# Process and index once
doc = process_document("docs/IntelCompanyDocumentation.pdf")

# Ask questions repeatedly using the indexed document
response = ask(
    document=doc,
    question="Under what ticker symbol does Intel trade?",
)

print(response.answer)        # "Intel's common stock trades under the symbol INTC..."
print(response.page_numbers)  # [5, 59, 125]
print(response.evidence)      # ['[Page 125] "Intel\'s common stock trades on NASDAQ..."']
print(response.confidence)    # 1.0
print(response.abstained)     # False
```

## Response Schema

| Field | Type | Description |
|---|---|---|
| `answer` | `str` | Grounded answer derived solely from retrieved excerpts |
| `evidence` | `list[str]` | Supporting quotations with source page numbers |
| `confidence` | `float` | Reliability estimate between 0.0 and 1.0 |
| `abstained` | `bool` | True if the system declined to answer |
| `abstention_reason` | `str \| null` | Explanation when abstaining, otherwise `null` |
| `page_numbers` | `list[int]` | Source page numbers where evidence was found |
