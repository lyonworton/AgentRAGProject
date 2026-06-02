from pypdf import PdfReader
from app.ingestion.parsers.base import BaseParser

class PDFParser(BaseParser):
    async def parse(self, file_path):
        reader = PdfReader(file_path)
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
