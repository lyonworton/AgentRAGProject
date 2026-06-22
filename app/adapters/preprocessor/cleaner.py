"""Auto-detect and remove repeated headers/footers from extracted PDF pages."""

import re
from collections import Counter

from app.core.config import get_settings
from app.adapters.preprocessor.base import BaseStep, ExtractedPDF


class HeaderFooterCleaner(BaseStep):
    """Detect and remove repeated headers/footers from PDF pages.

    Two mechanisms:
    1. Auto-detect: group repeated top-N / bottom-N lines across pages;
       if a group appears in >= 50 % of pages (minimum 3), treat it as
       header or footer and strip it.
    2. Regex filter: compile patterns from ``regex_patterns`` constructor
       arg AND from ``settings.preprocessor_header_footer_regex`` (comma-
       separated).  If a pattern matches the first line of a page's text,
       the matched portion is removed.

    Pages whose type changes to "header" or "footer" get that type set
    accordingly.
    """

    def __init__(
        self,
        top_lines: int = 2,
        bottom_lines: int = 2,
        regex_patterns: list[str] | None = None,
    ):
        self.top_lines = top_lines
        self.bottom_lines = bottom_lines
        self.regex_patterns = regex_patterns or []

    async def run(self, data: ExtractedPDF) -> ExtractedPDF:
        settings = get_settings()

        # Merge constructor regex patterns with env regex patterns
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

            # Apply auto-detected header pattern
            if header_re:
                text = re.sub(header_re, "", text, count=1).lstrip("\n")
                page_type = "header"

            # Apply auto-detected footer pattern
            if footer_re:
                text = re.sub(footer_re, "", text, count=1).rstrip("\n")
                page_type = "footer"

            # Apply user regex patterns
            for pat in compiled:
                first_line = text.strip().split("\n")[0]
                if pat.search(first_line):
                    # Apply substitution only to the first line
                    lines = text.split("\n")
                    lines[0] = pat.sub("", lines[0]).strip()
                    text = "\n".join(lines)
                    if page_type == "normal":
                        page_type = "header"

            pages.append({
                "page": page["page"],
                "text": text,
                "type": page_type,
            })

        full_text = "\n\n".join(p["text"] for p in pages)
        return ExtractedPDF(
            pages=pages,
            full_text=full_text,
            page_boundaries=data.page_boundaries,
            has_tables=data.has_tables,
            table_regions=data.table_regions,
        )

    @staticmethod
    def _collect_top_texts(pages: list[dict], n: int) -> list[str]:
        """Collect the first N lines of each page individually."""
        texts = []
        for page in pages:
            lines = page["text"].strip().split("\n")[:n]
            texts.append(lines[0] if lines else "")
        return texts

    @staticmethod
    def _collect_bottom_texts(pages: list[dict], n: int) -> list[str]:
        """Collect the last N lines of each page individually."""
        texts = []
        for page in pages:
            lines = page["text"].strip().split("\n")
            if n > 0 and lines:
                last_lines = lines[-n:]
                texts.append(last_lines[-1])
            else:
                texts.append("")
        return texts

    @staticmethod
    def _find_repeated(candidates: list[str], threshold: int) -> str | None:
        counter = Counter(candidates)
        for text, count in counter.items():
            if count >= threshold and text.strip():
                # Escape regex special chars so we match literal text
                escaped = re.escape(text.strip())
                return f"^{escaped}\\s*"
        return None
