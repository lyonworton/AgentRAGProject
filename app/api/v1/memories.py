from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.di import get_db
from app.api.deps import get_current_user
from app.domain.user import User
from app.services import memory_service

router = APIRouter(prefix="/memories", tags=["memories"])


class CreateMemoryRequest(BaseModel):
    type: str
    content: dict
    confidence: float = 1.0
    source_trace_id: str | None = None
    entity: str | None = None


class MemoryResponse(BaseModel):
    id: str
    user_id: str
    type: str
    entity: str | None
    content: dict
    confidence: float
    source_trace_id: str | None
    status: str
    created_at: str | None

    model_config = {"from_attributes": True}


class SearchMemoryRequest(BaseModel):
    query: str
    type: str | None = None
    top_k: int = 10


@router.get("", response_model=list[MemoryResponse])
async def list_memories(
    type: str | None = Query(None),
    limit: int = Query(50, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await memory_service.list_memories(db, user.id, type=type, limit=limit)


@router.post("/search", response_model=list[MemoryResponse])
async def search_memories(
    req: SearchMemoryRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await memory_service.search_memories(db, user.id, req.query, req.top_k)


@router.post("", response_model=MemoryResponse, status_code=201)
async def create_memory(
    req: CreateMemoryRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await memory_service.create_memory(
        db, user.id, req.type, req.content,
        req.confidence, req.source_trace_id, req.entity,
    )


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mem = await memory_service.get_memory(db, memory_id)
    if not mem or mem.user_id != user.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    await memory_service.delete_memory(db, memory_id)