from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.adapters.chunker.base import BaseChunker

class RecursiveChunker(BaseChunker):
    def __init__(self, chunk_size=1024, chunk_overlap=128):
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size,
            chunk_overlap=chunk_overlap, separators=["\n\n", "\n", ".", " "])

    async def split(self, text, metadata=None):
        docs = self.splitter.create_documents([text], metadatas=[metadata or {}])
        return [{"text": d.page_content, "metadata": d.metadata} for d in docs]
