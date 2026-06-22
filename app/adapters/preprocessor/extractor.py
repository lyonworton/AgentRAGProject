import asyncio
from pypdf import PdfReader
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
        reader = PdfReader(file_path)
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
        """Identity step - extractor already ran during construction."""
        return data
