from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.collections import router as collections_router
from app.api.v1.documents import router as documents_router
from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.queries import router as queries_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.feedbacks import router as feedbacks_router
from app.api.v1.memories import router as memories_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(collections_router)
v1_router.include_router(documents_router)
v1_router.include_router(ingestion_router)
v1_router.include_router(queries_router)
v1_router.include_router(sessions_router)
v1_router.include_router(feedbacks_router)
v1_router.include_router(memories_router)
