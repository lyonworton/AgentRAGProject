from arq.connections import RedisSettings
from app.core.config import get_settings
from app.workers.ingest import start_ingest_job

settings = get_settings()

class WorkerSettings:
    functions = [start_ingest_job]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 10
    job_timeout = 3600
