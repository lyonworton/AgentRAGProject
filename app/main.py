from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.events import on_startup, on_shutdown
from app.api.v1.router import v1_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()

app = FastAPI(title="AgentRAG", version="0.1.0", lifespan=lifespan)
app.include_router(v1_router)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/api/v1/admin/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
