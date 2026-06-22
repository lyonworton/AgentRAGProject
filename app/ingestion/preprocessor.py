"""Preprocessor pipeline: PDF extraction -> cleaning -> table extraction -> chunking."""

from app.adapters.preprocessor.extractor import PDFTextExtractor
from app.adapters.preprocessor.cleaner import HeaderFooterCleaner
from app.adapters.preprocessor.table import TableExtractor
from app.adapters.preprocessor.chunker import ParentChildChunker
from app.adapters.preprocessor.base import ChunkedDocument, ExtractedPDF
from app.core.config import get_settings


class PreprocessorPipeline:
    """Orchestrate the full preprocessor chain for a PDF file.

    Steps (in order):
        1. PDFTextExtractor.extract(file_path) -> ExtractedPDF
        2. HeaderFooterCleaner.run(data) -> ExtractedPDF
        3. TableExtractor.run(data) -> ExtractedPDF
        4. ParentChildChunker.run(data) -> ChunkedDocument
    """

    def __init__(self, file_path: str):
        self.file_path = file_path
        settings = get_settings()

        self.extractor = PDFTextExtractor()
        self.cleaner = HeaderFooterCleaner()
        self.table_extractor = TableExtractor()
        self.chunker = ParentChildChunker(
            parentchunk_size=settings.preprocessor_parentchunk_size,
            subchunk_size=settings.preprocessor_subchunk_size,
        )

    async def run(self) -> ChunkedDocument:
        """Execute the full pipeline and return a ChunkedDocument."""
        # Step 1: Extract text from PDF
        extracted: ExtractedPDF = await self.extractor.extract(self.file_path)

        # Step 2: Clean headers/footers
        cleaned: ExtractedPDF = await self.cleaner.run(extracted)

        # Step 3: Extract tables to markdown
        with_tables: ExtractedPDF = await self.table_extractor.run(cleaned)

        # Step 4: Chunk into parent-child structure
        chunked: ChunkedDocument = await self.chunker.run(with_tables)

        return chunked
