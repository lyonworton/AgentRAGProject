import structlog
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings
from app.core.di import async_session

logger = structlog.get_logger()
settings = get_settings()

BACKOFF = [60, 300, 900, 3600]


async def enqueue_repair(doc_id: str, failed_path: str, attempt: int = 0):
    """将修复任务入队 ARQ。"""
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis.enqueue_job(
        "repair_document_path", doc_id, failed_path, attempt
    )


async def repair_document_path(ctx, doc_id: str, failed_path: str, attempt: int):
    """ARQ job: 修复单个文档的单个存储路径，指数退避重试。"""
    if attempt >= len(BACKOFF):
        logger.warning("repair abandoned", doc_id=doc_id, path=failed_path)
        return

    try:
        if failed_path == "neo4j":
            await _repair_graph_path(doc_id)
        elif failed_path == "es":
            await _repair_keyword_path(doc_id)

        await _update_path_status(doc_id, failed_path, "ok")
        await _check_all_ok_and_set_ready(doc_id)
        logger.info("repair succeeded", doc_id=doc_id, path=failed_path)

    except Exception as e:
        if attempt + 1 < len(BACKOFF):
            delay = BACKOFF[attempt]
            logger.warning(
                "repair failed, re-enqueuing",
                doc_id=doc_id, path=failed_path,
                attempt=attempt, next_delay=delay, error=str(e),
            )
            await ctx["redis"].enqueue_job(
                "repair_document_path", doc_id, failed_path, attempt + 1,
                _defer_by=delay,
            )
        else:
            logger.error(
                "repair abandoned after max attempts",
                doc_id=doc_id, path=failed_path, error=str(e),
            )


async def _repair_graph_path(doc_id: str):
    from app.ingestion.pipeline import run_graph_path
    doc = await _load_document(doc_id)
    await run_graph_path(doc)


async def _repair_keyword_path(doc_id: str):
    from app.ingestion.pipeline import run_keyword_path
    doc = await _load_document(doc_id)
    await run_keyword_path(doc, doc.collection_id)


async def _load_document(doc_id: str):
    from app.domain.document import Document

    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if doc is None:
            raise ValueError(f"Document {doc_id} not found")
        return doc


async def _update_path_status(doc_id: str, path: str, status: str):
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if doc:
            current = doc.path_status or {}
            current[path] = status
            doc.path_status = current
            await db.commit()


async def _check_all_ok_and_set_ready(doc_id: str):
    async with async_session() as db:
        doc = await db.get(Document, doc_id)
        if doc and doc.path_status:
            if all(v == "ok" for v in doc.path_status.values()):
                doc.status = "ready"
                await db.commit()