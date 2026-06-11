from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from pydantic import BaseModel, field_validator
from app.core.di import get_db
from app.api.deps import get_current_user
from app.domain.user import User
from app.services import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    collection_id: str | None = None
    title: str | None = None


class SessionResponse(BaseModel):
    id: str
    user_id: str
    collection_id: str | None
    title: str | None
    message_count: int
    is_active: bool
    last_activity_at: str | None

    @field_validator("last_activity_at", mode="before")
    @classmethod
    def _dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    trace_id: str | None
    citations: list[dict] | dict | None
    token_count: int | None
    created_at: str | None

    @field_validator("created_at", mode="before")
    @classmethod
    def _dt_to_str(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    messages: list[MessageResponse]


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await session_service.create_session(db, user.id, req.collection_id, req.title)


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await session_service.list_sessions(db, user.id)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = await session_service.get_session(db, session_id, user.id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = await session_service.delete_session(db, session_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/{session_id}/history", response_model=HistoryResponse)
async def get_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = await session_service.get_session(db, session_id, user.id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    msgs = await session_service.get_history(db, session_id, user.id)
    return HistoryResponse(messages=msgs)