import asyncio
import json
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.long_term_memory import LongTermMemory

logger = structlog.get_logger()


class LongTermMemoryStore:
    """Long-term memory backed by PostgreSQL + optional Milvus semantic search."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: str,
        type: str,
        content: dict,
        confidence: float = 1.0,
        source_trace_id: str | None = None,
        entity: str | None = None,
    ) -> LongTermMemory:
        embedding = None
        try:
            from app.core.embedding_factory import get_embedder
            embedder = get_embedder()
            text_to_embed = json.dumps(content, ensure_ascii=False)
            embedding = await embedder.aembed_query(text_to_embed)
        except Exception:
            logger.warning("memory.embedding_failed", type=type, exc_info=True)

        mem = LongTermMemory(
            user_id=user_id,
            type=type,
            entity=entity,
            content=content,
            embedding=embedding,
            confidence=confidence,
            source_trace_id=source_trace_id,
            status="active",
        )
        self.db.add(mem)
        await self.db.flush()

        if embedding:
            task = asyncio.create_task(self._write_to_milvus(mem.id, embedding, content))
            task.add_done_callback(
                lambda t: logger.error("memory.milvus_write_failed", memory_id=mem.id,
                                        error=str(t.exception())) if t.exception() else None
            )

        return mem

    async def _write_to_milvus(self, memory_id: str, embedding: list[float], content: dict) -> None:
        try:
            from app.adapters.vector_store.milvus import MilvusStore
            store = MilvusStore()
            text = json.dumps(content, ensure_ascii=False)
            await store.upsert_memory(memory_id, embedding, text)
        except Exception:
            logger.warning("memory.milvus_upsert_failed", memory_id=memory_id, exc_info=True)

    async def search_by_embedding(
        self, query: str, user_id: str, top_k: int = 10
    ) -> list[LongTermMemory]:
        try:
            from app.adapters.vector_store.milvus import MilvusStore
            embedder = get_embedder()
            qe = await embedder.aembed_query(query)
            store = MilvusStore()
            hits = await store.search_memories(qe, top_k=top_k)
            memory_ids = [h.memory_id for h in hits if h.memory_id]
            if not memory_ids:
                return []
            result = await self.db.execute(
                select(LongTermMemory).where(
                    LongTermMemory.id.in_(memory_ids),
                    LongTermMemory.user_id == user_id,
                    LongTermMemory.status == "active",
                )
            )
            return list(result.scalars().all())
        except Exception:
            logger.warning("memory.search_by_embedding_failed", exc_info=True)
            return []

    async def list_by_user(
        self, user_id: str, type: str | None = None, limit: int = 50
    ) -> list[LongTermMemory]:
        stmt = select(LongTermMemory).where(
            LongTermMemory.user_id == user_id,
            LongTermMemory.status == "active",
        )
        if type:
            stmt = stmt.where(LongTermMemory.type == type)
        stmt = stmt.order_by(LongTermMemory.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get(self, memory_id: str) -> LongTermMemory | None:
        return await self.db.get(LongTermMemory, memory_id)

    async def delete(self, memory_id: str) -> None:
        mem = await self.db.get(LongTermMemory, memory_id)
        if mem:
            mem.status = "deleted"
            await self.db.flush()