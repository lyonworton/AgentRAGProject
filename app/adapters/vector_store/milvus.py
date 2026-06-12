from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
from app.adapters.vector_store.base import BaseVectorStore, SearchResult
from app.core.config import get_settings
settings = get_settings()

class MilvusStore(BaseVectorStore):
    def __init__(self):
        connections.connect(alias="default", host=settings.milvus_host, port=settings.milvus_port)

    async def create_collection(self, name, dim):
        if utility.has_collection(name): return
        schema = CollectionSchema(fields=[
            FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema("chunk_id", DataType.VARCHAR, max_length=64),
            FieldSchema("document_id", DataType.VARCHAR, max_length=64),
            FieldSchema("text", DataType.VARCHAR, max_length=65535),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema("metadata", DataType.JSON),
            FieldSchema("chunk_index", DataType.INT32),
            FieldSchema("parent_chunk_id", DataType.VARCHAR, max_length=64, nullable=True),
        ])
        col = Collection(name, schema)
        col.create_index("embedding", {"metric_type":"COSINE","index_type":"IVF_FLAT","params":{"nlist":128}})
        col.load()

    async def insert(self, name, chunks, embeddings):
        col = Collection(name)
        rows = [{ "chunk_id":ch["chunk_id"],"document_id":ch["document_id"],"text":ch["text"],
            "embedding":embeddings[i],"metadata":ch.get("metadata",{}),
            "chunk_index":ch.get("chunk_index",0),"parent_chunk_id":ch.get("parent_chunk_id","")} for i,ch in enumerate(chunks)]
        col.insert(rows); col.flush()

    async def search(self, name, qe, top_k=10):
        col = Collection(name); col.load()
        results = col.search(data=[qe],anns_field="embedding",
            param={"metric_type":"COSINE","params":{"nprobe":16}},limit=top_k,
            output_fields=["chunk_id","document_id","text","metadata"])
        return [SearchResult(chunk_id=hit.entity.get("chunk_id"),document_id=hit.entity.get("document_id"),
            text=hit.entity.get("text"),score=hit.score,metadata=hit.entity.get("metadata",{})) for hits in results for hit in hits]

    async def delete_collection(self, name):
        if utility.has_collection(name): utility.drop_collection(name)

    async def delete_by_document(self, name, doc_id):
        Collection(name).delete(f'document_id == "{doc_id}"')

    # === Memory collection support ===
    _MEMORIES_READY = False

    async def ensure_memories_collection(self, dim: int = 1024) -> None:
        """Create the memories collection if it does not exist."""
        name = "memories"
        if utility.has_collection(name):
            MilvusStore._MEMORIES_READY = True
            return
        schema = CollectionSchema(fields=[
            FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema("memory_id", DataType.VARCHAR, max_length=64),
            FieldSchema("text", DataType.VARCHAR, max_length=65535),
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=dim),
        ])
        col = Collection(name, schema)
        col.create_index("embedding", {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}})
        col.load()
        MilvusStore._MEMORIES_READY = True

    async def upsert_memory(self, memory_id: str, embedding: list[float], text: str) -> None:
        """Insert or update a memory record in the memories collection."""
        if not MilvusStore._MEMORIES_READY:
            await self.ensure_memories_collection(len(embedding))
        col = Collection("memories")
        rows = [{"memory_id": memory_id, "embedding": embedding, "text": text}]
        col.insert(rows)
        col.flush()

    async def search_memories(self, query_embedding: list[float], top_k: int = 10) -> list[SearchResult]:
        """Search the memories collection by embedding."""
        name = "memories"
        if not utility.has_collection(name):
            return []
        col = Collection(name)
        col.load()
        results = col.search(
            data=[query_embedding], anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}}, limit=top_k,
            output_fields=["memory_id", "text"],
        )
        return [
            SearchResult(
                chunk_id="", document_id="",
                memory_id=hit.entity.get("memory_id"),
                text=hit.entity.get("text", ""),
                score=hit.score, metadata={},
            )
            for hits in results for hit in hits
        ]
