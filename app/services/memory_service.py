from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.long_term_memory import LongTermMemory
from app.memory.long_term import LongTermMemoryStore


async def create_memory(
    db: AsyncSession,
    user_id: str,
    type: str,
    content: dict,
    confidence: float = 1.0,
    source_trace_id: str | None = None,
    entity: str | None = None,
) -> LongTermMemory:
    store = LongTermMemoryStore(db)
    return await store.create(
        user_id=user_id, type=type, content=content,
        confidence=confidence, source_trace_id=source_trace_id, entity=entity,
    )


async def search_memories(
    db: AsyncSession, user_id: str, query: str, top_k: int = 10
) -> list[LongTermMemory]:
    store = LongTermMemoryStore(db)
    return await store.search_by_embedding(query, user_id, top_k=top_k)


async def list_memories(
    db: AsyncSession, user_id: str, type: str | None = None, limit: int = 50
) -> list[LongTermMemory]:
    store = LongTermMemoryStore(db)
    return await store.list_by_user(user_id, type=type, limit=limit)


async def get_memory(db: AsyncSession, memory_id: str) -> LongTermMemory | None:
    store = LongTermMemoryStore(db)
    return await store.get(memory_id)


async def delete_memory(db: AsyncSession, memory_id: str) -> None:
    store = LongTermMemoryStore(db)
    await store.delete(memory_id)