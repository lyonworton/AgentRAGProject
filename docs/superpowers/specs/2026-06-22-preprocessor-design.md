# Document Preprocessor Design

## 1. Overview

Add a pluggable preprocessing pipeline between document loading and chunking. Handles structured PDFs (contracts, reports, papers, manuals) with text cleaning, table extraction, header/footer removal, and parent-child chunking.

**Goal**: Improve RAG retrieval quality for structured documents by producing clean text and enabling precise chunk-level search with full-context parent block return.

## 2. Architecture

```
PDF Loader (pypdf)
       │
       ▼
PDFTextExtractor ──→ pypdf → pdfplumber fallback
       │
       ▼
HeaderFooterCleaner ──→ auto-detect + regex blacklist
       │
       ▼
TableExtractor ──→ pdfplumber → Markdown tables
       │
       ▼
ParentChildChunker ──→ title-aware + sliding window
       │
       ▼
   cleaned_doc.content ──→ Neo4j path
   cleaned_doc.content ──→ ES keyword path
   child_chunks + embeddings ──→ Milvus (only child chunks stored)
```

### Integration Points

- `app/ingestion/pipeline.py::run_semantic_path()`: calls `preprocess()` before `chunk_text()`
- `app/ingestion/pipeline.py::run_graph_path()`: reads `doc.content` (already cleaned)
- `app/ingestion/pipeline.py::run_keyword_path()`: reads `doc.content` (already cleaned)
- `app/adapters/vector_store/milvus.py::search()`: `SearchResult` gains `content_start`/`content_end` from metadata

### Backward Compatibility

- New env var `PREPROCESSOR_ENABLED` defaults to `true`
- When disabled, pipeline follows the original loader → chunk → embed path
- Existing Milvus collections are unaffected (child chunks have `content_start`/`content_end` in metadata)

## 3. Directory Structure

```
app/adapters/preprocessor/
├── __init__.py          # PreprocessorPipeline, BaseStep exports
├── base.py              # BaseStep abstract class
├── extractor.py         # PDFTextExtractor (pypdf → pdfplumber fallback)
├── cleaner.py           # HeaderFooterCleaner
├── table.py             # TableExtractor
└── chunker.py           # ParentChildChunker

app/ingestion/preprocessor.py  # PreprocessorPipeline orchestration
```

## 4. Components

### 4.1 PDFTextExtractor

Two-stage PDF text extraction with fallback.

**Input**: file path
**Output**: `ExtractedPDF` dataclass

```python
@dataclass
class ExtractedPDF:
    pages: list[dict]       # [{"page": N, "text": "...", "type": "normal|header|footer|table|body"}, ...]
    full_text: str          # Raw concatenated text (page 1 + "\n\n" + page 2 + ...)
    page_boundaries: list[tuple[int, int]]  # (char_start, char_end) for each page in full_text
    has_tables: bool        # Whether pdfplumber detected tables
    table_regions: list[dict]  # [{"page": N, "bbox": {...}, "rows": [[...]]}]  (from pdfplumber fallback only)
```

**Strategy**:
1. Try `pypdf.PdfReader.extract_text()` page by page
2. If pypdf fails (corrupt/encrypted PDF), fall back to `pdfplumber`
3. If pdfplumber succeeds, also extract table regions for `TableExtractor`

**Dependencies**: `pypdf` (already in pyproject.toml), `pdfplumber` (new dependency)

### 4.2 HeaderFooterCleaner

Auto-detects repeated text at top/bottom of pages, filters by regex.

**Input**: `ExtractedPDF`
**Output**: `CleanedPDF`

```python
@dataclass
class CleanedPDF:
    pages: list[dict]       # Same structure, with header/footer regions marked
    full_text: str          # Cleaned text (headers/footers removed)
    header_footer_removed: int  # Count of removed blocks
```

**Algorithm**:
1. **Auto-detect**: Group page-top text (first 2 lines) and page-bottom text (last 2 lines) by similarity. If the same text appears on ≥3 pages at the same position, mark as header/footer.
2. **Regex filter**: Apply user-configured regex patterns from env (`PREPROCESSOR_HEADER_FOOTER_REGEX`, comma-separated).
3. **Strip**: Remove matched header/footer text from each page, mark as `type: "header"` or `type: "footer"`.

**Env config**:
```
PREPROCESSOR_HEADER_FOOTER_REGEX=^第\s*\d+\s*页,^\s*[Cc]onfidential,^©\s*\d{4}
```

### 4.3 TableExtractor

Extract tables from PDF pages and convert to Markdown.

**Input**: `CleanedPDF` + `ExtractedPDF.table_regions`
**Output**: `TableCleanedPDF`

```python
@dataclass
class TableCleanedPDF:
    full_text: str          # Tables replaced with Markdown placeholders
    tables: list[dict]      # [{"page": N, "markdown": "| Col1 | Col2 |\n|------|------|", "position": (start, end)}]
```

**Strategy**:
- If pdfplumber was used (fallback path), tables are already extracted → convert to Markdown
- If pypdf succeeded, tables are NOT extracted by pypdf → use pdfplumber in read-only mode just for table detection on pages that likely contain tables (heuristic: pages with ≥3 columns of aligned text)
- Convert each table to Markdown format

**Markdown table format**:
```markdown
| Col1 | Col2 | Col3 |
|------|------|------|
| val1 | val2 | val3 |
```

### 4.4 ParentChildChunker

Generates child chunks (for embedding/search) with parent block references.

**Input**: `TableCleanedPDF` (cleaned full text + page metadata)
**Output**: `ChunkedDocument`

```python
@dataclass
class ChunkedDocument:
    child_chunks: list[dict]  # [{"chunk_id": ..., "parent_group_id": ..., "text": ..., "metadata": {...}}, ...]
    parent_groups: dict       # {parent_id: {"text": ..., "content_start": ..., "content_end": ..., "child_ids": [...]}}
    cleaned_full_text: str    # Final cleaned text for doc.content
```

**Algorithm**:
1. **Detect document structure**: Scan for heading patterns (e.g., "Chapter 1", "Article 3.1", "1. Introduction", "# Title", "**Section**").
2. **Build parent blocks**: Split text by headings. Each heading section becomes a parent block.
   - If a section ≤ `parent_chunk_size` (default 2000 chars): one parent block
   - If a section > `parent_chunk_size`: split into multiple parent blocks (sliding window with overlap)
3. **Generate child chunks**: Within each parent block, split into small chunks of `subchunk_size` (default 128 chars).
4. **Enrich metadata**: Each child chunk gets:
   ```json
   {
     "parent_group_id": "<parent_id>",
     "source_page": 3,
     "content_type": "body|header|footer|table",
     "content_start": 1234,
     "content_end": 1362
   }
   ```

**Heading detection patterns**:
```python
HEADING_PATTERNS = [
    r"^#{1,6}\s+.+$",                    # Markdown headings
    r"^\d+(?:\.\d+)*\s+[A-Za-z一-鿿].+$",  # "1. Introduction", "第三章"
    r"^(Chapter|Section|Article|Part)\s+\d+",        # Case-insensitive
    r"^[A-Z][^.]{10,}$",                          # Short all-caps-ish lines
]
```

## 5. Data Flow: Insertion

```
1. run_ingest_pipeline(job_id, collection_id, user_id, source, ...)
   │
   ├─ parsed = await loader.load(fp)
   │
   ├─ IF preprocessor_enabled:
   │   ├─ extracted = await PDFTextExtractor().extract(parsed.content, parsed.metadata)
   │   ├─ cleaned = await HeaderFooterCleaner().clean(extracted)
   │   ├─ with_tables = await TableExtractor().extract_tables(cleaned)
   │   ├─ chunked = await ParentChildChunker().chunk(with_tables)
   │   │
   │   ├─ # Update doc.content with cleaned full text (3 paths)
   │   ├─ doc.content = chunked.cleaned_full_text
   │   ├─ # Use child_chunks for embedding
   │   └─ chunks = chunked.child_chunks
   │
   └─ ELSE (backward compat):
       └─ chunks = await chunk_text(parsed.content, metadata)
```

## 6. Data Flow: Retrieval

```
1. User query → agent → MilvusStore.search(collection, query_embedding, top_k)
   │
   ├─ Milvus returns child chunks with metadata:
   │   {"chunk_id": "abc", "parent_group_id": "parent_123",
   │    "content_start": 1234, "content_end": 1362,
   │    "source_page": 3, "content_type": "body"}
   │
   ├─ Agent retrieves doc.content from PostgreSQL using document_id
   │
   └─ Expand: doc.content[content_start:content_end] → parent block text
       → Return parent block text to LLM (NOT the child chunk text)
```

## 7. Configuration

### New Settings (app/core/config.py)

```python
preprocessor_enabled: bool = True
preprocessor_header_footer_regex: str = ""       # Comma-separated regex patterns
preprocessor_table_enabled: bool = True
preprocessor_subchunk_size: int = 128            # Child chunk size in characters
preprocessor_parentchunk_size: int = 2000        # Parent block max size
preprocessor_title_max_depth: int = 2            # Heading depth to detect (1-6)
```

### .env.example additions

```env
# Document Preprocessing
PREPROCESSOR_ENABLED=true
PREPROCESSOR_TABLE_ENABLED=true
PREPROCESSOR_SUBCHUNK_SIZE=128
PREPROCESSOR_PARENTCHUNK_SIZE=2000
PREPROCESSOR_TITLE_MAX_DEPTH=2
PREPROCESSOR_HEADER_FOOTER_REGEX=
```

## 8. Dependencies

### New dependency

| Package | Purpose | License |
|---------|---------|---------|
| `pdfplumber>=0.10.0` | Table extraction + PDF fallback | MIT |

### Existing dependencies reused

| Package | Current Use | New Use |
|---------|-------------|---------|
| `pypdf` | PDF text extraction | Unchanged |
| `langchain-text-splitters` | Chunking | Parent-child chunking logic |

## 9. Testing Strategy

### Unit tests (tests/unit/adapters/preprocessor/)
- `test_pdf_extractor_pypdf_success.py` — pypdf extraction, page boundaries
- `test_pdf_extractor_fallback.py` — pypdf fails, pdfplumber succeeds
- `test_header_footer_cleaner_auto.py` — Auto-detect repeated headers/footers
- `test_header_footer_cleaner_regex.py` — Custom regex filtering
- `test_table_extractor_markdown.py` — Table → Markdown conversion
- `test_parent_child_chunker_headings.py` — Heading-based splitting
- `test_parent_child_chunker_sliding.py` — Long section sliding window
- `test_parent_child_chunker_metadata.py` — content_start/end correctness
- `test_preprocessor_pipeline_integration.py` — Full pipeline end-to-end

### Integration tests (tests/integration/)
- `test_ingest_with_preprocessor_enabled.py` — Full ingest pipeline with preprocessor
- `test_ingest_with_preprocessor_disabled.py` — Backward compatibility
- `test_retrieve_parent_child_chunks.py` — Search child → expand to parent

### Migration notes

No database migration needed. `doc.content` is already `Text` type. Milvus schema already has `parent_chunk_id` field (used as `parent_group_id` semantically).
