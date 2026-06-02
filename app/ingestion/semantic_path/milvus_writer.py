import uuid
from app.adapters.vector_store.milvus import MilvusStore

async def write_chunks_to_milvus(collection_name, document_id, chunks, embeddings):
    store = MilvusStore()
    records = [{"chunk_id": uuid.uuid4().hex[:12], "document_id": document_id,
        "text": c["text"], "metadata": c.get("metadata", {}), "chunk_index": i,
        "parent_chunk_id": ""} for i, c in enumerate(chunks)]
    await store.insert(collection_name, records, embeddings)
    return len(records)
