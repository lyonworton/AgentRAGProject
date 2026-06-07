from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.events import on_startup, on_shutdown
from app.core.middleware import RequestIDMiddleware, TimingMiddleware
from app.api.v1.router import v1_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()

app = FastAPI(title="AgentRAG", version="0.1.0", lifespan=lifespan)
app.include_router(v1_router)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TimingMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/v1/admin/health")
async def health():
    status = {"status": "ok", "version": "0.1.0"}
    checks = {}

    # PostgreSQL
    try:
        from sqlalchemy import text
        from app.core.di import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
        checks["postgresql"] = "ok"
    except Exception as e:
        checks["postgresql"] = f"error: {e}"
        status["status"] = "degraded"

    # Redis
    try:
        from app.core.di import get_redis
        r = await get_redis()
        await r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        status["status"] = "degraded"

    # Milvus
    try:
        from pymilvus import connections, utility
        settings = get_settings()
        connections.connect(alias="health_check", host=settings.milvus_host, port=settings.milvus_port)
        ok = utility.get_server_version(using="health_check")
        checks["milvus"] = f"ok (v{ok})"
        connections.disconnect(alias="health_check")
    except Exception as e:
        checks["milvus"] = f"error: {e}"
        status["status"] = "degraded"

    status["checks"] = checks
    return status
