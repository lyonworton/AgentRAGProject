import structlog
from app.core.config import get_settings

logger = structlog.get_logger()


async def on_startup():
    logger.info("app starting", env=get_settings().app_env)


async def on_shutdown():
    logger.info("app shutting down")