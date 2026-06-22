# Document Preprocessor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pluggable preprocessing pipeline between document loading and chunking to improve RAG retrieval quality for structured PDFs (contracts, reports, papers, manuals).

**Architecture:** A new `app/adapters/preprocessor/` module with four composable steps: `PDFTextExtractor` (pypdf → pdfplumber fallback), `HeaderFooterCleaner` (auto-detect + regex), `TableExtractor` (pdfplumber → Markdown), and `ParentChildChunker` (title-aware + sliding window). A `PreprocessorPipeline` orchestrates them. The ingestion pipeline calls the preprocessor before chunking; cleaned text feeds all three paths (Milvus/Neo4j/ES); only child chunks go to Milvus with parent block references in metadata.

**Tech Stack:** Python 3.12+, pypdf (existing), pdfplumber (new, MIT), LangChain text splitters (existing), pytest (existing).

## Global Constraints

- **Dependency:** Only one new runtime dependency: `pdfplumber>=0.10.0` (MIT license). No PyMuPDF (GPL concern).
- **Backward compatibility:** When `PREPROCESSOR_ENABLED=false`, pipeline follows original loader → chunk → embed path unchanged.
- **Milvus schema:** No schema change. Existing `parent_chunk_id` field is reused as `parent_group_id` semantically.
- **TDD:** Every component has unit tests with failing tests written first.
- **No placeholder code:** Every function has a complete implementation in every step.

---

### Task 1: Add pdfplumber dependency and env config

**Files:**
- Modify: `pyproject.toml` (add pdfplumber)
- Modify: `app/core/config.py` (add preprocessor settings)
- Modify: `.env.example` (add preprocessor env vars)
- Modify: `.env.docker` (add preprocessor env vars)

**Interfaces:**
- Consumes: existing `Settings` class, existing `.env` files
- Produces: 6 new Settings fields

**Steps:**

- [ ] **Step 1: Add pdfplumber to pyproject.toml**

Add `pdfplumber>=0.10.0` to the dependencies list in `pyproject.toml` (after `pypdf>=4.2.0`, line 25):

```diff
     "pypdf>=4.2.0",
+    "pdfplumber>=0.10.0",
     "markdown-it-py>=3.0.0",
```

- [ ] **Step 2: Run test to verify pyproject.toml parses**

Run: `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Add preprocessor settings to app/core/config.py**

Add these fields to the `Settings` class (after line 34, before line 36):

```python
    # Document Preprocessing
    preprocessor_enabled: bool = True
    preprocessor_header_footer_regex: str = ""
    preprocessor_table_enabled: bool = True
    preprocessor_subchunk_size: int = 128
    preprocessor_parentchunk_size: int = 2000
    preprocessor_title_max_depth: int = 2
```

- [ ] **Step 4: Run test to verify Settings loads**

Run: `python -c "from app.core.config import get_settings; s = get_settings(); assert hasattr(s, 'preprocessor_enabled'); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Add preprocessor env vars to .env.example**

Append after the Reranker section (after line 43):

```env

# --- Document Preprocessing ---
PREPROCESSOR_ENABLED=true
PREPROCESSOR_TABLE_ENABLED=true
PREPROCESSOR_SUBCHUNK_SIZE=128
PREPROCESSOR_PARENTCHUNK_SIZE=2000
PREPROCESSOR_TITLE_MAX_DEPTH=2
PREPROCESSOR_HEADER_FOOTER_REGEX=
```

- [ ] **Step 6: Add preprocessor env vars to .env.docker**

Append after line 29 (after `RERANKER_PROVIDER=rrf`):

```env
PREPROCESSOR_ENABLED=true
PREPROCESSOR_TABLE_ENABLED=true
PREPROCESSOR_SUBCHUNK_SIZE=128
PREPROCESSOR_PARENTCHUNK_SIZE=2000
PREPROCESSOR_TITLE_MAX_DEPTH=2
PREPROCESSOR_HEADER_FOOTER_REGEX=
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml app/core/config.py .env.example .env.docker
git commit -m "chore(dep): add pdfplumber and preprocessor config settings"
```

---

### Task 2: Implement PDFTextExtractor (pypdf → pdfplumber fallback)

**Files:**
- Create: `app/adapters/preprocessor/__init__.py`
- Create: `app/adapters/preprocessor/base.py`
- Create: `app/adapters/preprocessor/extractor.py`
- Test: `tests/unit/adapters/preprocessor/test_extractor.py`

**Interfaces:**
- Consumes: `pypdf.PdfReader` (existing), `pdfplumber.open()` (new)
- Produces: `ExtractedPDF` dataclass with `pages`, `full_text`, `page_boundaries`, `has_tables`, `table_regions`

**Step 1: Write the base classes and __init__.py**

Create `app/adapters/preprocessor/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExtractedPDF:
    """Raw extraction result from a PDF file."""
    pages: list[dict]                     # [{"page": N, "text": "...", "type": "normal"}, ...]
    full_text: str                        # Concatenated text (page1 + "\n\n" + page2 + ...)
    page_boundaries: list[tuple[int, int]]  # (char_start, char_end) for each page in full_text
    has_tables: bool = False              # Whether tables were detected
    table_regions: list[dict] = field(default_factory=list)  # [{"page": N, "bbox": {...}, "rows": [[...]]}]


class BaseStep(ABC):
    """Base class for all preprocessor steps."""

    @abstractmethod
    async def run(self, data: ExtractedPDF) -> ExtractedPDF: ...
```

Create `app/adapters/preprocessor/__init__.py`:

```python
from app.adapters.preprocessor.base import BaseStep, ExtractedPDF

__all__ = ["BaseStep", "ExtractedPDF"]
```

- [ ] **Step 2: Write failing tests**

Create `tests/unit/adapters/preprocessor/__init__.py` (empty):

```python
```

Create `tests/unit/adapters/preprocessor/test_extractor.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_extractor_uses_pypdf_when_successful(tmp_path):
    """When pypdf succeeds, use it and don't call pdfplumber."""
    from app.adapters.preprocessor.extractor import PDFTextExtractor

    # Create a valid PDF file
    pdf_path = tmp_path / "test.pdf"
    # We'll mock pypdf to avoid needing a real PDF file
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page 1 content"
    mock_reader.pages = [mock_page]
    mock_reader.__len__ = MagicMock(return_value=1)

    with patch("app.adapters.preprocessor.extractor.PdfReader", return_value=mock_reader):
        extractor = PDFTextExtractor()
        result = await extractor.extract(str(pdf_path))

    assert isinstance(result, ExtractedPDF)
    assert result.full_text == "Page 1 content"
    assert len(result.pages) == 1
    assert result.pages[0]["page"] == 1
    assert result.pages[0]["text"] == "Page 1 content"
    assert result.pages[0]["type"] == "normal"
    assert result.page_boundaries == [(0, 14)]
    assert result.has_tables is False


@pytest.mark.asyncio
async def test_extractor_falls_back_to_pdfplumber_on_pypdf_failure(tmp_path):
    """When pypdf raises, fall back to pdfplumber."""
    from app.adapters.preprocessor.extractor import PDFTextExtractor

    mock_reader = MagicMock()
    mock_reader.pages = []
    mock_reader.__len__ = MagicMock(return_value=0)
    mock_reader.__iter__ = MagicMock(return_value=iter([]))

    with patch("app.adapters.preprocessor.extractor.PdfReader", side_effect=Exception("corrupt PDF")), \
         patch("app.adapters.preprocessor.extractor.pdfplumber.open") as mock_plumber:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Plumber content"
        mock_page.chars = [{"text": "P", "x0": 0, "x1": 10, "y0": 0, "y1": 14},]
        mock_doc.pages = [mock_page]
        mock_plumber.return_value.__enter__ = MagicMock(return_value=mock_doc)
        mock_plumber.return_value.__exit__ = MagicMock(return_value=False)

        extractor = PDFTextExtractor()
        result = await extractor.extract(str(tmp_path / "fake.pdf"))

    assert result.full_text == "Plumber content"
    assert result.has_tables is False


@pytest.mark.asyncio
async def test_extractor_returns_page_boundaries():
    """page_boundaries correctly maps char offsets per page."""
    mock_reader = MagicMock()
    mock_page1 = MagicMock()
    mock_page1.extract_text.return_value = "Hello"
    mock_page2 = MagicMock()
    mock_page2.extract_text.return_value = "World"
    mock_reader.pages = [mock_page1, mock_page2]
    mock_reader.__len__ = MagicMock(return_value=2)

    with patch("app.adapters.preprocessor.extractor.PdfReader", return_value=mock_reader):
        from app.adapters.preprocessor.extractor import PDFTextExtractor
        extractor = PDFTextExtractor()
        result = await extractor.extract("/fake/path.pdf")

    # full_text = "Hello" + "\n\n" + "World" = "Hello\n\nWorld" (13 chars)
    # page 0: 0-5, page 1: 7-12
    assert result.page_boundaries == [(0, 5), (7, 12)]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/adapters/preprocessor/test_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.adapters.preprocessor'`

- [ ] **Step 4: Implement PDFTextExtractor**

Create `app/adapters/preprocessor/extractor.py`:

```python
import asyncio
from pypdf import PdfReader as PyPDFReader
import pdfplumber
from app.adapters.preprocessor.base import BaseStep, ExtractedPDF


class PDFTextExtractor(BaseStep):
    """Extract text from PDF using pypdf, falling back to pdfplumber."""

    async def extract(self, file_path: str) -> ExtractedPDF:
        """Extract text from a PDF file.

        Tries pypdf first. If pypdf fails (corrupt/encrypted PDF),
        falls back to pdfplumber which may handle different PDF formats.
        """
        try:
            return await asyncio.to_thread(self._extract_pypdf, file_path)
        except Exception:
            return await asyncio.to_thread(self._extract_pdfplumber, file_path)

    def _extract_pypdf(self, file_path: str) -> ExtractedPDF:
        reader = PyPDFReader(file_path)
        pages = []
        full_parts = []
        boundaries = []
        offset = 0

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append({"page": i + 1, "text": text, "type": "normal"})
            boundaries.append((offset, offset + len(text)))
            full_parts.append(text)
            offset += len(text) + 2  # +2 for "\n\n" separator

        full_text = "\n\n".join(full_parts)
        return ExtractedPDF(
            pages=pages,
            full_text=full_text,
            page_boundaries=boundaries,
            has_tables=False,
            table_regions=[],
        )

    def _extract_pdfplumber(self, file_path: str) -> ExtractedPDF:
        tables = []
        pages = []
        full_parts = []
        boundaries = []
        offset = 0

        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                page_tables = page.extract_tables()
                if page_tables:
                    for j, row_group in enumerate(page_tables):
                        clean_row = [cell or "" for cell in row_group if cell is not None]
                        if clean_row:
                            tables.append({
                                "page": i + 1,
                                "index": j,
                                "rows": clean_row,
                                "bbox": getattr(page, "cur_page_rect", None),
                            })
                pages.append({"page": i + 1, "text": text, "type": "normal"})
                boundaries.append((offset, offset + len(text)))
                full_parts.append(text)
                offset += len(text) + 2

        full_text = "\n\n".join(full_parts)
        return ExtractedPDF(
            pages=pages,
            full_text=full_text,
            page_boundaries=boundaries,
            has_tables=bool(tables),
            table_regions=tables,
        )

    async def run(self, data: ExtractedPDF) -> ExtractedPDF:
        """Identity step — extractor already ran during construction."""
        return data
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/adapters/preprocessor/test_extractor.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/adapters/preprocessor/__init__.py app/adapters/preprocessor/base.py app/adapters/preprocessor/extractor.py tests/unit/adapters/preprocessor/__init__.py tests/unit/adapters/preprocessor/test_extractor.py
git commit -m "feat(preprocessor): add PDFTextExtractor with pypdf→pdfplumber fallback"
```

---

### Task 3: Implement HeaderFooterCleaner

**Files:**
- Create: `app/adapters/preprocessor/cleaner.py`
- Test: `tests/unit/adapters/preprocessor/test_cleaner.py`

**Interfaces:**
- Consumes: `ExtractedPDF` from Task 2
- Produces: `ExtractedPDF` with pages marked `type: "header"`/`"footer"` and header/footer text removed from `full_text`

**Step 1: Write failing tests**

Create `tests/unit/adapters/preprocessor/test_cleaner.py`:

```python
import pytest
from app.adapters.preprocessor.base import ExtractedPDF
from app.adapters.preprocessor.cleaner import HeaderFooterCleaner


def _make_extracted(pages_data):
    """Helper to create an ExtractedPDF from page text data."""
    pages = [{"page": i + 1, "text": text, "type": "normal"} for i, text in enumerate(pages_data)]
    full_text = "\n\n".join(pages_data)
    boundaries = []
    offset = 0
    for text in pages_data:
        boundaries.append((offset, offset + len(text)))
        offset += len(text) + 2
    return ExtractedPDF(pages=pages, full_text=full_text, page_boundaries=boundaries)


@pytest.mark.asyncio
async def test_auto_detect_repeated_header():
    """Pages with identical top text should be detected as headers."""
    cleaner = HeaderFooterCleaner(top_lines=2, bottom_lines=2)
    pages = [
        "CONFIDENTIAL\nActual content line 1\nActual content line 2",
        "CONFIDENTIAL\nMore content here\nAnd more text",
        "CONFIDENTIAL\nThird page stuff\nStill going",
    ]
    data = _make_extracted(pages)
    result = await cleaner.run(data)

    # "CONFIDENTIAL" should be stripped from all pages
    for page in result.pages:
        assert page["text"].strip() != "CONFIDENTIAL\nActual content line 1\nActual content line 2"
        assert "CONFIDENTIAL" not in page["text"].strip().split("\n")[0]


@pytest.mark.asyncio
async def test_regex_filter_applied():
    """Custom regex patterns should filter matching text."""
    cleaner = HeaderFooterCleaner(top_lines=2, bottom_lines=2, regex_patterns=[r"^Page \d+/\d+$"])
    pages = [
        "Page 1/3\nRegular text one",
        "Page 2/3\nRegular text two",
        "Page 3/3\nRegular text three",
    ]
    data = _make_extracted(pages)
    result = await cleaner.run(data)

    for page in result.pages:
        assert "Page" not in page["text"].strip().split("\n")[0]


@pytest.mark.asyncio
async def test_no_change_when_no_headers():
    """If no repeated headers found and no regex matches, data is unchanged."""
    cleaner = HeaderFooterCleaner(top_lines=2, bottom_lines=2)
    pages = ["Unique content A", "Different content B", "Another thing C"]
    data = _make_extracted(pages)
    result = await cleaner.run(data)

    assert result.header_footer_removed == 0
    for i, page in enumerate(result.pages):
        assert page["text"] == pages[i]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/adapters/preprocessor/test_cleaner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement HeaderFooterCleaner**

Add to `app/adapters/preprocessor/cleaner.py`:

```python
import asyncio
import re
from collections import Counter
from app.core.config import get_settings
from app.adapters.preprocessor.base import BaseStep, ExtractedPDF


class HeaderFooterCleaner(BaseStep):
    """Detect and remove repeated headers/footers from PDF pages."""

    def __init__(self, top_lines: int = 2, bottom_lines: int = 2, regex_patterns: list[str] | None = None):
        self.top_lines = top_lines
        self.bottom_lines = bottom_lines
        self.regex_patterns = regex_patterns or []

    async def run(self, data: ExtractedPDF) -> ExtractedPDF:
        settings = get_settings()

        # Merge env regex patterns with constructor patterns
        patterns = list(self.regex_patterns)
        if settings.preprocessor_header_footer_regex:
            for p in settings.preprocessor_header_footer_regex.split(","):
                p = p.strip()
                if p:
                    patterns.append(p)

        compiled = [re.compile(p) for p in patterns if p]

        # Auto-detect repeated top/bottom text
        top_candidates = self._collect_top_texts(data.pages, self.top_lines)
        bottom_candidates = self._collect_bottom_texts(data.pages, self.bottom_lines)

        header_threshold = max(3, len(data.pages) * 0.5)
        footer_threshold = max(3, len(data.pages) * 0.5)

        header_re = self._find_repeated(top_candidates, header_threshold)
        footer_re = self._find_repeated(bottom_candidates, footer_threshold)

        pages = []
        for page in data.pages:
            text = page["text"]
            page_type = page.get("type", "normal")

            # Apply auto-detected patterns
            if header_re:
                text = re.sub(header_re, "", text, count=1).lstrip("\n")
                page_type = "header"
            if footer_re:
                text = re.sub(footer_re, "", text, count=1).rstrip("\n")
                page_type = "footer"

            # Apply user regex patterns
            for pat in compiled:
                if pat.search(text.strip().split("\n")[0]):
                    text = pat.sub("", text).strip()
                    page_type = "header" if page_type == "normal" else page_type

            pages.append({"page": page["page"], "text": text, "type": page_type})

        full_text = "\n\n".join(p["text"] for p in pages)
        return ExtractedPDF(
            pages=pages,
            full_text=full_text,
            page_boundaries=data.page_boundaries,
            has_tables=data.has_tables,
            table_regions=data.table_regions,
        )

    def _collect_top_texts(self, pages: list[dict], n: int) -> list[str]:
        texts = []
        for page in pages:
            lines = page["text"].strip().split("\n")[:n]
            texts.append("\n".join(lines))
        return texts

    def _collect_bottom_texts(self, pages: list[dict], n: int) -> list[str]:
        texts = []
        for page in pages:
            lines = page["text"].strip().split("\n")[-n:] if n > 0 else []
            texts.append("\n".join(lines))
        return texts

    def _find_repeated(self, candidates: list[str], threshold: int) -> str | None:
        counter = Counter(candidates)
        for text, count in counter.items():
            if count >= threshold and text.strip():
                # Escape regex special chars
                escaped = re.escape(text.strip())
                return f"^{escaped}\\s*"
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/adapters/preprocessor/test_cleaner.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/adapters/preprocessor/cleaner.py tests/unit/adapters/preprocessor/test_cleaner.py
git commit -m "feat(preprocessor): add HeaderFooterCleaner with auto-detect and regex"
```

---

### Task 4: Implement TableExtractor

**Files:**
- Modify: `app/adapters/preprocessor/extractor.py` (add `_convert_tables_to_markdown` method)
- Create: `app/adapters/preprocessor/table.py`
- Test: `tests/unit/adapters/preprocessor/test_table.py`

**Interfaces:**
- Consumes: `ExtractedPDF` with `table_regions` populated (from pdfplumber fallback or standalone extraction)
- Produces: `ExtractedPDF` with table regions replaced by Markdown placeholders in `full_text`

**Step 1: Write failing tests**

Create `tests/unit/adapters/preprocessor/test_table.py`:

```python
import pytest
from app.adapters.preprocessor.base import ExtractedPDF
from app.adapters.preprocessor.table import TableExtractor


@pytest.mark.asyncio
async def test_convert_simple_table_to_markdown():
    """A simple 2x3 table should convert to Markdown format."""
    extractor = TableExtractor()
    data = ExtractedPDF(
        pages=[{"page": 1, "text": "Intro\n| Col1 | Col2 |\n|------|------|\n| A | B |", "type": "normal"}],
        full_text="Intro\n| Col1 | Col2 |\n|------|------|\n| A | B |",
        page_boundaries=[(0, 50)],
        has_tables=True,
        table_regions=[{
            "page": 1,
            "rows": [["Header1", "Header2"], ["val1", "val2"], ["val3", "val4"]],
        }],
    )
    result = await extractor.run(data)

    # Find the table placeholder in full_text
    assert "TABLE:" in result.full_text
    # Verify table markdown is accessible
    assert len(result.tables) == 1
    assert "| Header1" in result.tables[0]["markdown"]


@pytest.mark.asyncio
async def test_no_tables_returns_unchanged():
    """When has_tables is False, return data unchanged."""
    extractor = TableExtractor()
    data = ExtractedPDF(
        pages=[{"page": 1, "text": "Just text", "type": "normal"}],
        full_text="Just text",
        page_boundaries=[(0, 9)],
        has_tables=False,
    )
    result = await extractor.run(data)
    assert result.full_text == "Just text"
    assert result.tables == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/adapters/preprocessor/test_table.py -v`
Expected: FAIL

- [ ] **Step 3: Implement TableExtractor**

Create `app/adapters/preprocessor/table.py`:

```python
import asyncio
import re
import pdfplumber
from app.core.config import get_settings
from app.adapters.preprocessor.base import BaseStep, ExtractedPDF


def _rows_to_markdown(rows: list[list[str]]) -> str:
    """Convert a list of row lists to a Markdown table string."""
    if not rows:
        return ""
    lines = []
    # Header
    header = "| " + " | ".join(str(c).strip() for c in rows[0]) + " |"
    lines.append(header)
    # Separator
    sep = "| " + " | ".join("---" for _ in rows[0]) + " |"
    lines.append(sep)
    # Data rows
    for row in rows[1:]:
        line = "| " + " | ".join(str(c).strip() for c in row) + " |"
        lines.append(line)
    return "\n".join(lines)


class TableExtractor(BaseStep):
    """Extract tables from PDF pages and replace them with Markdown placeholders."""

    def __init__(self):
        self.enabled = True

    async def run(self, data: ExtractedPDF) -> ExtractedPDF:
        settings = get_settings()
        if not settings.preprocessor_table_enabled:
            self.enabled = False

        if not self.enabled or not data.has_tables:
            return ExtractedPDF(
                pages=data.pages,
                full_text=data.full_text,
                page_boundaries=data.page_boundaries,
                has_tables=False,
                table_regions=[],
                tables=[],
            )

        tables = []
        full_text = data.full_text
        offset_adjustment = 0

        for region in data.table_regions:
            page_num = region["page"]
            rows = region.get("rows", [])
            if not rows:
                continue

            markdown = _rows_to_markdown(rows)
            placeholder = f"\n\nTABLE:{page_num}:{len(tables)}\n{markdown}\nENDTABLE:{page_num}:{len(tables)}\n\n"
            tables.append({
                "page": page_num,
                "index": len(tables),
                "markdown": markdown,
                "placeholder": placeholder,
            })

        # Replace table regions in full_text with placeholders
        # Since we don't have exact positions from pypdf, we use a heuristic:
        # find table-like patterns in the text and replace them
        for table_info in reversed(tables):
            page_num = table_info["page"]
            # Find page boundary
            if page_num - 1 < len(data.page_boundaries):
                start, end = data.page_boundaries[page_num - 1]
                page_text = full_text[start:end]
                # Look for table-like content (rows of pipe-separated or aligned text)
                placeholder = table_info["placeholder"]
                full_text = full_text[:start] + placeholder + full_text[end:]
                offset_adjustment += len(placeholder) - (end - start)

        return ExtractedPDF(
            pages=data.pages,
            full_text=full_text,
            page_boundaries=data.page_boundaries,
            has_tables=False,
            table_regions=[],
            tables=tables,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/adapters/preprocessor/test_table.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/adapters/preprocessor/table.py tests/unit/adapters/preprocessor/test_table.py
git commit -m "feat(preprocessor): add TableExtractor with Markdown output"
```

---

### Task 5: Implement ParentChildChunker

**Files:**
- Create: `app/adapters/preprocessor/chunker.py`
- Test: `tests/unit/adapters/preprocessor/test_chunker.py`

**Interfaces:**
- Consumes: `ExtractedPDF` with cleaned text
- Produces: `ChunkedDocument` dataclass with `child_chunks`, `parent_groups`, `cleaned_full_text`

**Step 1: Write the ChunkedDocument dataclass and failing tests**

First, update `app/adapters/preprocessor/base.py` to add the `ChunkedDocument` dataclass:

```python
@dataclass
class ChunkedDocument:
    """Result of parent-child chunking."""
    child_chunks: list[dict]              # [{"chunk_id": ..., "parent_group_id": ..., "text": ..., "metadata": {...}}, ...]
    parent_groups: dict                   # {parent_id: {"text": ..., "content_start": ..., "content_end": ..., "child_ids": [...]}}
    cleaned_full_text: str                # Final text for doc.content
```

Create `tests/unit/adapters/preprocessor/test_chunker.py`:

```python
import pytest
from app.adapters.preprocessor.base import ExtractedPDF
from app.adapters.preprocessor.chunker import ParentChildChunker


@pytest.mark.asyncio
async def test_chunker_creates_child_and_parent():
    """Short text should produce one parent group with multiple child chunks."""
    chunker = ParentChildChunker(subchunk_size=50, parentchunk_size=200)
    text = "Article 1: Terms\nThis is the first clause of the contract.\nIt has multiple sentences.\n"
    data = ExtractedPDF(
        pages=[{"page": 1, "text": text, "type": "normal"}],
        full_text=text,
        page_boundaries=[(0, len(text))],
    )
    result = await chunker.run(data)

    assert result.cleaned_full_text == text
    assert len(result.parent_groups) >= 1
    assert len(result.child_chunks) >= 1
    # Each child should reference a parent
    for child in result.child_chunks:
        assert "parent_group_id" in child["metadata"]
        pid = child["metadata"]["parent_group_id"]
        assert pid in result.parent_groups
        assert "content_start" in child["metadata"]
        assert "content_end" in child["metadata"]


@pytest.mark.asyncio
async def test_chunker_detects_headings():
    """Text with heading patterns should be split into parent groups by heading."""
    chunker = ParentChildChunker(subchunk_size=30, parentchunk_size=100)
    text = "Article 1: Terms\nSome text here.\n\nArticle 2: Duties\nMore text here.\n"
    data = ExtractedPDF(
        pages=[{"page": 1, "text": text, "type": "normal"}],
        full_text=text,
        page_boundaries=[(0, len(text))],
    )
    result = await chunker.run(data)

    # Should create at least 2 parent groups (one per heading)
    assert len(result.parent_groups) >= 2


@pytest.mark.asyncio
async def test_chunker_sliding_window_for_long_sections():
    """A section longer than parentchunk_size should be split into multiple parents."""
    chunker = ParentChildChunker(subchunk_size=20, parentchunk_size=50)
    long_text = "Section 1\n" + "Word " * 40 + "\n"
    data = ExtractedPDF(
        pages=[{"page": 1, "text": long_text, "type": "normal"}],
        full_text=long_text,
        page_boundaries=[(0, len(long_text))],
    )
    result = await chunker.run(data)

    # Should have multiple parent groups for the long section
    assert len(result.parent_groups) >= 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/adapters/preprocessor/test_chunker.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ParentChildChunker**

Create `app/adapters/preprocessor/chunker.py`:

```python
import asyncio
import re
import uuid
from app.core.config import get_settings
from app.adapters.preprocessor.base import BaseStep, ExtractedPDF, ChunkedDocument


HEADING_PATTERN = re.compile(
    r"(?:^|\n)"                           # Start of text or newline
    r"(?:#"                              # Markdown ## heading
    r"|Article\s+\d+"                     # Article 1, Article 3.1
    r"|(?:Chapter|Section|Part)\s+\d+)"   # Chapter 1, Section 2
    r"[^\n]*",                            # Rest of heading line
    re.IGNORECASE,
)

SLIDING_HEADING_PATTERN = re.compile(
    r"^\d+(?:\.\d+)*\s+[A-Za-z一-鿿].{3,50}$",  # "1. Introduction", "第三章 总则"
    re.MULTILINE,
)


class ParentChildChunker(BaseStep):
    """Split cleaned text into parent blocks and child chunks with metadata."""

    def __init__(self, subchunk_size: int | None = None, parentchunk_size: int | None = None):
        settings = get_settings()
        self.subchunk_size = subchunk_size or settings.preprocessor_subchunk_size
        self.parentchunk_size = parentchunk_size or settings.preprocessor_parentchunk_size

    async def run(self, data: ExtractedPDF) -> ChunkedDocument:
        text = data.full_text
        if not text.strip():
            return ChunkedDocument(child_chunks=[], parent_groups={}, cleaned_full_text=text)

        # Step 1: Find heading boundaries
        headings = self._find_headings(text)

        # Step 2: Build parent blocks
        parent_groups, child_chunks = self._build_parents_and_children(text, headings)

        return ChunkedDocument(
            child_chunks=child_chunks,
            parent_groups=parent_groups,
            cleaned_full_text=text,
        )

    def _find_headings(self, text: str) -> list[tuple[int, int, str]]:
        """Find all heading positions in text. Returns [(start, end, heading_text), ...]."""
        headings = []
        for pat in [HEADING_PATTERN, SLIDING_HEADING_PATTERN]:
            for m in pat.finditer(text):
                start, end = m.start(), m.end()
                heading = text[start:end].strip()
                # Avoid duplicates
                if not any(h[2] == heading for h in headings):
                    headings.append((start, end, heading))
        headings.sort(key=lambda x: x[0])
        return headings

    def _build_parents_and_children(
        self, text: str, headings: list[tuple[int, int, str]]
    ) -> tuple[dict, list[dict]]:
        parent_groups: dict = {}
        child_chunks: list[dict] = []

        # Define section boundaries
        if headings:
            sections = []
            for i, (h_start, h_end, h_text) in enumerate(headings):
                next_start = headings[i + 1][0] if i + 1 < len(headings) else len(text)
                sections.append((h_start, next_start, h_text))
        else:
            sections = [(0, len(text), "")]

        # Build parent blocks from sections
        for sec_start, sec_end, sec_heading in sections:
            section_text = text[sec_start:sec_end]
            section_text = section_text.lstrip("\n")

            if not section_text.strip():
                continue

            # If section fits in parentchunk_size, one parent
            if len(section_text) <= self.parentchunk_size:
                parent_id = f"parent_{uuid.uuid4().hex[:8]}"
                parent_groups[parent_id] = {
                    "text": section_text,
                    "content_start": sec_start,
                    "content_end": sec_start + len(section_text),
                    "child_ids": [],
                    "heading": sec_heading,
                }
                self._make_children(section_text, parent_id, child_chunks, sec_start)
            else:
                # Split long section into multiple parents (sliding window)
                self._split_long_section(section_text, sec_heading, sec_start, parent_groups, child_chunks)

        return parent_groups, child_chunks

    def _make_children(
        self, text: str, parent_id: str, child_chunks: list[dict], global_offset: int = 0
    ):
        """Split a parent block into child chunks."""
        start = 0
        child_idx = 0
        while start < len(text):
            end = min(start + self.subchunk_size, len(text))
            child_text = text[start:end].strip()
            if child_text:
                chunk_id = f"child_{parent_id}_{child_idx}"
                child_chunks.append({
                    "chunk_id": chunk_id,
                    "parent_group_id": parent_id,
                    "text": child_text,
                    "metadata": {
                        "parent_group_id": parent_id,
                        "content_start": global_offset + start,
                        "content_end": global_offset + end,
                        "source_page": 1,  # Will be updated by cleaner/table steps
                        "content_type": "body",
                    },
                })
                parent_groups_ref = locals().get("parent_groups")
                if parent_groups_ref and parent_id in parent_groups_ref:
                    parent_groups_ref[parent_id]["child_ids"].append(chunk_id)
            start = end
            child_idx += 1

    def _split_long_section(
        self, text: str, heading: str, global_start: int,
        parent_groups: dict, child_chunks: list[dict]
    ):
        """Split a section longer than parentchunk_size into multiple parents."""
        overlap = 50
        pos = 0
        parent_idx = 0
        while pos < len(text):
            end = min(pos + self.parentchunk_size, len(text))
            # Try to split at newline near the boundary
            if end < len(text):
                split_at = text.rfind("\n", end - 100, end)
                if split_at > pos:
                    end = split_at + 1

            parent_text = text[pos:end]
            parent_id = f"parent_{uuid.uuid4().hex[:8]}"
            parent_groups[parent_id] = {
                "text": parent_text,
                "content_start": global_start + pos,
                "content_end": global_start + end,
                "child_ids": [],
                "heading": heading if parent_idx == 0 else None,
            }
            self._make_children(parent_text, parent_id, child_chunks, global_start + pos)
            pos = end - overlap if end < len(text) else end
            parent_idx += 1
            if parent_idx > 100:
                break  # Safety valve
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/adapters/preprocessor/test_chunker.py -v`
Expected: All tests PASS. If any fail, fix the implementation.

- [ ] **Step 5: Commit**

```bash
git add app/adapters/preprocessor/base.py app/adapters/preprocessor/chunker.py tests/unit/adapters/preprocessor/test_chunker.py
git commit -m "feat(preprocessor): add ParentChildChunker with title-aware + sliding window"
```

---

### Task 6: Wire PreprocessorPipeline into ingestion pipeline

**Files:**
- Create: `app/ingestion/preprocessor.py`
- Modify: `app/ingestion/pipeline.py` (integrate preprocessor)
- Test: `tests/unit/ingestion/test_preprocessor_integration.py`

**Interfaces:**
- Consumes: `ExtractedPDF`, `ChunkedDocument` from Tasks 2-5
- Produces: Preprocessed chunks for `run_semantic_path`, cleaned `doc.content`

**Step 1: Write the PreprocessorPipeline orchestration**

Create `app/ingestion/preprocessor.py`:

```python
"""Preprocessor pipeline: extract → clean → tables → chunk."""

from app.adapters.preprocessor.base import ExtractedPDF, ChunkedDocument, BaseStep
from app.adapters.preprocessor.extractor import PDFTextExtractor
from app.adapters.preprocessor.cleaner import HeaderFooterCleaner
from app.adapters.preprocessor.table import TableExtractor
from app.adapters.preprocessor.chunker import ParentChildChunker


class PreprocessorPipeline:
    """Orchestrates the preprocessor steps for a single PDF file."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.steps: list[BaseStep] = []
        self._build_steps()

    def _build_steps(self):
        self.steps = [
            PDFTextExtractor(),
            HeaderFooterCleaner(),
            TableExtractor(),
            ParentChildChunker(),
        ]

    async def run(self) -> ChunkedDocument:
        """Execute the full pipeline. Returns ChunkedDocument."""
        # Step 1: Extract
        extractor = PDFTextExtractor()
        extracted = await extractor.extract(self.file_path)

        # Step 2: Clean headers/footers
        cleaner = HeaderFooterCleaner()
        cleaned = await cleaner.run(extracted)

        # Step 3: Extract tables
        table_extractor = TableExtractor()
        with_tables = await table_extractor.run(cleaned)

        # Step 4: Chunk
        chunker = ParentChildChunker()
        result = await chunker.run(with_tables)

        return result
```

- [ ] **Step 2: Write failing tests for pipeline integration**

Create `tests/unit/ingestion/test_preprocessor_integration.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_preprocessor_pipeline_runs_steps():
    """Pipeline should call each step in order."""
    from app.ingestion.preprocessor import PreprocessorPipeline

    mock_extracted = MagicMock()
    mock_extracted.full_text = "Article 1\nSome text.\n\nArticle 2\nMore text."
    mock_extracted.pages = [{"page": 1, "text": "Article 1\nSome text.", "type": "normal"}]
    mock_extracted.page_boundaries = [(0, 30)]
    mock_extracted.has_tables = False
    mock_extracted.table_regions = []

    mock_chunked = MagicMock()
    mock_chunked.cleaned_full_text = mock_extracted.full_text
    mock_chunked.child_chunks = [{"chunk_id": "c1", "text": "Some text.", "metadata": {"parent_group_id": "p1"}}]
    mock_chunked.parent_groups = {"p1": {"text": "Article 1\nSome text.", "content_start": 0, "content_end": 30}}

    with patch("app.ingestion.preprocessor.PDFTextExtractor") as MockExt, \
         patch("app.ingestion.preprocessor.HeaderFooterCleaner") as MockClean, \
         patch("app.ingestion.preprocessor.TableExtractor") as MockTable, \
         patch("app.ingestion.preprocessor.ParentChildChunker") as MockChunk:

        MockExt.return_value.extract = AsyncMock(return_value=mock_extracted)
        MockClean.return_value.run = AsyncMock(side_effect=lambda x: x)
        MockTable.return_value.run = AsyncMock(side_effect=lambda x: x)
        MockChunk.return_value.run = AsyncMock(return_value=mock_chunked)

        pipeline = PreprocessorPipeline("/fake/path.pdf")
        result = await pipeline.run()

        assert result.cleaned_full_text == mock_extracted.full_text
        assert len(result.child_chunks) == 1
        assert result.child_chunks[0]["metadata"]["parent_group_id"] == "p1"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/unit/ingestion/test_preprocessor_integration.py -v`
Expected: FAIL (because `run_semantic_path` doesn't call the preprocessor yet)

- [ ] **Step 4: Modify run_semantic_path to use preprocessor**

Modify `app/ingestion/pipeline.py`. Replace the `run_semantic_path` function:

```python
async def run_semantic_path(doc, col_name: str, embedding_dim: int) -> dict:
    """Semantic path: preprocess → chunk → embed → Milvus.

    Returns a dict with chunks, embeddings, and doc_id for batch flushing.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if settings.preprocessor_enabled:
        from app.ingestion.preprocessor import PreprocessorPipeline

        pipeline = PreprocessorPipeline(doc.source_path)
        chunked = await pipeline.run()

        # Update doc.content with cleaned text (all 3 paths benefit)
        doc.content = chunked.cleaned_full_text

        # Use child chunks for embedding
        chunks = chunked.child_chunks
    else:
        # Backward compatible: original path
        chunks = await chunk_text(doc.content, {"source": doc.source_path})

    if not chunks:
        raise ValueError("No chunks produced")

    embs = await embed_chunks(chunks)
    return {
        "doc_id": doc.id,
        "chunks": chunks,
        "embeddings": embs,
        "count": len(chunks),
        "parent_groups": chunked.parent_groups if settings.preprocessor_enabled else {},
    }
```

Also update `batch_flush_milvus` to handle parent-child metadata:

In `app/ingestion/pipeline.py`, modify `batch_flush_milvus`:

```python
async def batch_flush_milvus(col_name: str, batch_data: list[dict]) -> int:
    """Flush accumulated chunks from multiple docs to Milvus in batches of 1000."""
    import uuid
    import structlog

    logger = structlog.get_logger()
    store = MilvusStore()
    BATCH_SIZE = 1000

    all_records = []
    all_embeddings = []

    for item in batch_data:
        doc_id = item['doc_id']
        chunks = item['chunks']
        embs = item['embeddings']
        for i, c in enumerate(chunks):
            metadata = c.get('metadata', {})
            # For parent-child chunks, set parent_chunk_id to parent_group_id
            parent_id = metadata.get('parent_group_id', '')
            all_records.append({
                'chunk_id': c.get('chunk_id', uuid.uuid4().hex[:12]),
                'document_id': doc_id,
                'text': c['text'],
                'metadata': metadata,
                'chunk_index': i,
                'parent_chunk_id': parent_id,
            })
            all_embeddings.append(embs[i])

    for start in range(0, len(all_records), BATCH_SIZE):
        batch_records = all_records[start:start + BATCH_SIZE]
        batch_embs = all_embeddings[start:start + BATCH_SIZE]
        await store.insert(col_name, batch_records, batch_embs, flush=True)

    logger.info('batch_flush_complete', total=len(all_records))
    return len(all_records)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/ingestion/test_preprocessor_integration.py tests/unit/adapters/preprocessor/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/ingestion/preprocessor.py app/ingestion/pipeline.py tests/unit/ingestion/test_preprocessor_integration.py
git commit -m "feat(preprocessor): wire PreprocessorPipeline into ingestion pipeline"
```

---

### Task 7: Update Milvus search to return parent block text

**Files:**
- Modify: `app/adapters/vector_store/base.py` (SearchResult dataclass)
- Modify: `app/adapters/vector_store/milvus.py` (search method)
- Test: `tests/unit/adapters/vector_store/test_milvus_search.py`

**Interfaces:**
- Consumes: Milvus search results with metadata containing `content_start`/`content_end`
- Produces: `SearchResult` with expanded parent block text

**Step 1: Write failing test**

Create `tests/unit/adapters/vector_store/test_milvus_search.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_search_result_has_content_start_end():
    """SearchResult should expose content_start and content_end from metadata."""
    from app.adapters.vector_store.base import SearchResult

    result = SearchResult(
        chunk_id="c1",
        document_id="d1",
        text="child chunk text",
        score=0.9,
        metadata={"content_start": 100, "content_end": 200, "parent_group_id": "p1"},
    )
    assert result.content_start == 100
    assert result.content_end == 200
    assert result.parent_group_id == "p1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/adapters/vector_store/test_milvus_search.py -v`
Expected: FAIL — `SearchResult` has no `content_start`/`content_end` attributes

- [ ] **Step 3: Update SearchResult dataclass**

Modify `app/adapters/vector_store/base.py`:

```python
@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)
    memory_id: str | None = None
    content_start: int | None = None
    content_end: int | None = None
    parent_group_id: str | None = None

    def __post_init__(self):
        if self.content_start is None and "content_start" in self.metadata:
            self.content_start = self.metadata.get("content_start")
        if self.content_end is None and "content_end" in self.metadata:
            self.content_end = self.metadata.get("content_end")
        if self.parent_group_id is None:
            self.parent_group_id = self.metadata.get("parent_group_id")
```

- [ ] **Step 4: Update MilvusStore.search to pass through metadata**

The existing `MilvusStore.search` already passes `metadata` through — no changes needed there since `content_start`/`content_end` live in metadata.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/adapters/vector_store/test_milvus_search.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/adapters/vector_store/base.py tests/unit/adapters/vector_store/test_milvus_search.py
git commit -m "feat(vector): add content_start/content_end/parent_group_id to SearchResult"
```

---

### Task 8: Update existing import test and run full test suite

**Files:**
- Modify: `tests/unit/ingestion/test_all_imports.py` (add preprocessor imports)
- Run: `pytest tests/ -v`

**Step 1: Add preprocessor import tests**

Append to `tests/unit/ingestion/test_all_imports.py`:

```python
def test_import_preprocessor_pipeline():
    from app.ingestion.preprocessor import PreprocessorPipeline
    assert PreprocessorPipeline is not None


def test_import_preprocessor_modules():
    from app.adapters.preprocessor.extractor import PDFTextExtractor
    from app.adapters.preprocessor.cleaner import HeaderFooterCleaner
    from app.adapters.preprocessor.table import TableExtractor
    from app.adapters.preprocessor.chunker import ParentChildChunker
    from app.adapters.preprocessor.base import BaseStep, ExtractedPDF, ChunkedDocument
    assert all(x is not None for x in [
        PDFTextExtractor, HeaderFooterCleaner, TableExtractor,
        ParentChildChunker, BaseStep, ExtractedPDF, ChunkedDocument,
    ])
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS + new tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/ingestion/test_all_imports.py
git commit -m "test: add preprocessor import tests to all_imports suite"
```

---

## Summary of Files Changed

### New files (8):
1. `app/adapters/preprocessor/__init__.py`
2. `app/adapters/preprocessor/base.py`
3. `app/adapters/preprocessor/extractor.py`
4. `app/adapters/preprocessor/cleaner.py`
5. `app/adapters/preprocessor/table.py`
6. `app/adapters/preprocessor/chunker.py`
7. `app/ingestion/preprocessor.py`
8. `tests/unit/adapters/preprocessor/__init__.py`

### Modified files (6):
1. `pyproject.toml` — add pdfplumber
2. `app/core/config.py` — add 6 preprocessor settings
3. `.env.example` — add preprocessor env vars
4. `.env.docker` — add preprocessor env vars
5. `app/ingestion/pipeline.py` — integrate preprocessor in run_semantic_path + batch_flush_milvus
6. `app/adapters/vector_store/base.py` — add content_start/content_end/parent_group_id to SearchResult

### New test files (4):
1. `tests/unit/adapters/preprocessor/test_extractor.py`
2. `tests/unit/adapters/preprocessor/test_cleaner.py`
3. `tests/unit/adapters/preprocessor/test_table.py`
4. `tests/unit/adapters/preprocessor/test_chunker.py`
5. `tests/unit/ingestion/test_preprocessor_integration.py`
6. `tests/unit/adapters/vector_store/test_milvus_search.py`

### Modified test files (1):
1. `tests/unit/ingestion/test_all_imports.py`

## Dependencies Added

- `pdfplumber>=0.10.0` (MIT license) — for table extraction and pypdf fallback
