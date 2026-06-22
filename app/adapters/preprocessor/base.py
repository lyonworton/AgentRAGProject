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


class BaseStep(ABC):
    """Base class for all preprocessor steps."""

    @abstractmethod
    async def run(self, data: ExtractedPDF) -> ExtractedPDF: ...
