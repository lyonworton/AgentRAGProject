from arq import create_pool
from arq.connections import RedisSettings
from app.core.config import get_settings
from app.core.di import async_session
from app.ingestion.pipeline import run_ingest_pipeline

settings = get_settings()

async def start_ingest_job(ctx, job_id, collection_id, user_id, file_paths, embedding_dim=1536):
    return await run_ingest_pipeline(job_id, collection_id, user_id, file_paths, embedding_dim, async_session)

async def enqueue_ingest(job_id, collection_id, user_id, file_paths):
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    arq_job = await redis.enqueue_job("start_ingest_job", job_id, collection_id, user_id, file_paths)
    return arq_job.job_id
