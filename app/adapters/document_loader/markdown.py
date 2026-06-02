import os
from app.adapters.document_loader.base import BaseLoader, ParsedDocument

class MarkdownLoader(BaseLoader):
    async def load(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f: text = f.read()
        stat = os.stat(file_path)
        return ParsedDocument(title=os.path.basename(file_path), content=text,
            mime_type="text/markdown", file_size=stat.st_size, metadata={})
