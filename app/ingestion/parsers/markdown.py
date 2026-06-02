from app.ingestion.parsers.base import BaseParser

class MarkdownParser(BaseParser):
    async def parse(self, file_path):
        with open(file_path, "r", encoding="utf-8") as f: return f.read()
