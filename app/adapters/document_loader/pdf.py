import os
from pypdf import PdfReader
from app.adapters.document_loader.base import BaseLoader, ParsedDocument

class PDFLoader(BaseLoader):
    async def load(self, file_path):
        reader = PdfReader(file_path)
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        stat = os.stat(file_path)
        return ParsedDocument(title=os.path.basename(file_path), content=text,
            mime_type="application/pdf", file_size=stat.st_size, metadata={"total_pages": len(reader.pages)})
