from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# === Phase 2: KG + Search store singletons ===

_kg_store = None
_search_store = None


async def get_kg_store():
    global _kg_store
    if _kg_store is None:
        from app.adapters.kg.neo4j import Neo4jKGStore
        _kg_store = Neo4jKGStore()
        await _kg_store.aconnect()
    return _kg_store


async def get_search_store():
    global _search_store
    if _search_store is None:
        from app.adapters.search.elasticsearch import ElasticsearchStore
        _search_store = ElasticsearchStore()
        await _search_store.aconnect()
    return _search_store