from app.core.embedding_factory import get_embedder

async def embed_chunks(chunks):
    embedder = get_embedder()
    return await embedder.aembed_documents([c["text"] for c in chunks])
