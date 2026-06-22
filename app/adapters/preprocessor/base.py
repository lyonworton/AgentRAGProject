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
    tables: list[dict] = field(default_factory=list)  # Output: converted markdown tables


@dataclass
class ChunkedDocument:
    """Result of chunking an ExtractedPDF into parent groups and child chunks."""
    child_chunks: list[dict]              # Each: {chunk_id, parent_group_id, text, metadata}
    parent_groups: dict                   # {pg_id: {text, content_start, content_end, child_ids, heading}}
    cleaned_full_text: str                # The full text passed through all prior steps


class BaseStep(ABC):
    """Base class for all preprocessor steps."""

    @abstractmethod
    async def run(self, data: ExtractedPDF) -> ExtractedPDF | ChunkedDocument: ...
