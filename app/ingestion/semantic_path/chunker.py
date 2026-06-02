from app.adapters.chunker.recursive import RecursiveChunker

async def chunk_text(text, metadata, chunk_size=1024):
    chunker = RecursiveChunker(chunk_size=chunk_size, chunk_overlap=128)
    return await chunker.split(text, metadata)
