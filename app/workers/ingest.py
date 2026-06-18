import asyncio
from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings
from app.core.di import async_session
from app.ingestion.pipeline import run_ingest_pipeline
from app.ingestion.sources.local import LocalSource
from app.ingestion.sources.web import WebSource
from app.ingestion.sources.database import DBSource

settings = get_settings()

# === Embedding model prewarm (shared across all ARQ worker processes) ===
_embedder_prewarmed = False


def _prewarm_embedder():
    """Lazy-load BGE-M3 model into singleton (blocking, run in thread)."""
    global _embedder_prewarmed
    if _embedder_prewarmed:
        return
    from app.core.embedding_factory import get_embedder
    embedder = get_embedder()
    embedder._load_model()  # blocks, but only once per process
    _embedder_prewarmed = True


async def start_ingest_job(
    ctx,
    job_id: str,
    collection_id: str,
    user_id: str,
    source_type: str,
    source_config: dict,
    embedding_dim: int = -1,
):
    """ARQ job: 启动摄入管道。

    Pre-warms the embedding model on first call to avoid 20s+ cold start
    during the actual embedding phase.

    Args:
        source_type: "local" | "web" | "database"
        source_config:
            - local: {"file_paths": [...]}
            - web: {"urls": [...], "max_depth": 1}
            - database: {"db_url": "...", "query": "...",
                         "title_column": "...", "content_columns": [...]}
    """
    if source_type == "local":
        source = LocalSource(source_config["file_paths"])
    elif source_type == "web":
        source = WebSource(
            source_config["urls"],
            source_config.get("max_depth", 1),
        )
    elif source_type == "database":
        source = DBSource(
            source_config["db_url"],
            source_config["query"],
            source_config["title_column"],
            source_config["content_columns"],
        )
    else:
        raise ValueError(f"Unknown source_type: {source_type}")

    return await run_ingest_pipeline(
        job_id, collection_id, user_id, source, embedding_dim, async_session,
        commit_every=5,
    )


async def enqueue_ingest(
    job_id: str,
    collection_id: str,
    user_id: str,
    source_type: str,
    source_config: dict,
):
    """将摄入任务入队 ARQ。"""
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    arq_job = await redis.enqueue_job(
        "start_ingest_job",
        job_id, collection_id, user_id, source_type, source_config,
    )
    return arq_job.job_id
