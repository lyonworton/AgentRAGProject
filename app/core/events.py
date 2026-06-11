import structlog
from app.core.config import get_settings

logger = structlog.get_logger()


async def on_startup():
    import asyncio

    settings = get_settings()
    logger.info("app starting", env=settings.app_env)

    # Phase 2: Prewarm Neo4j + ES connections (warn-only on failure)
    try:
        from app.core.di import get_kg_store
        await get_kg_store()
        logger.info("neo4j connected")
    except Exception as e:
        logger.warning("neo4j unavailable, KG features disabled", error=str(e))

    try:
        from app.core.di import get_search_store
        await get_search_store()
        logger.info("elasticsearch connected")
    except Exception as e:
        logger.warning("elasticsearch unavailable, keyword search disabled", error=str(e))

    # Prewarm embedding model in a thread pool (doesn't block event loop)
    try:
        from app.core.embedding_factory import get_embedder
        embedder = get_embedder()
        await asyncio.to_thread(embedder._load_model)
        logger.info("embedding model prewarmed")
    except Exception as e:
        logger.warning("embedding model unavailable, vector search disabled", error=str(e))


async def on_shutdown():
    logger.info("app shutting down")

    # Phase 2: Close Neo4j + ES connections
    from app.core import di
    try:
        if di._kg_store is not None:
            await di._kg_store.adisconnect()
    except Exception:
        pass
    try:
        if di._search_store is not None:
            await di._search_store.adisconnect()
    except Exception:
        pass