from app.adapters.embedding.openai_embed import OpenAIEmbedding

async def embed_chunks(chunks):
    embedder = OpenAIEmbedding()
    return await embedder.aembed_documents([c["text"] for c in chunks])
