from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.di import get_db
from app.api.deps import get_current_user
from app.domain.user import User
from app.services import feedback_service

router = APIRouter(prefix="/feedback", tags=["feedback"])


class CreateFeedbackRequest(BaseModel):
    trace_id: str
    rating: int | None = None
    feedback_type: str | None = None
    comment: str | None = None
    correction: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    trace_id: str
    user_id: str
    rating: int | None
    feedback_type: str | None
    comment: str | None
    correction: str | None
    resolved_status: str
    created_at: str | None

    model_config = {"from_attributes": True}


class FeedbackStatsResponse(BaseModel):
    total: int
    avg_rating: float
    by_type: dict[str, int]


@router.post("", response_model=FeedbackResponse, status_code=201)
async def create_feedback(
    req: CreateFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await feedback_service.create_feedback(
        db, user.id, req.trace_id, req.rating,
        req.feedback_type, req.comment, req.correction,
    )


@router.get("", response_model=FeedbackResponse | None)
async def get_feedback(
    trace_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await feedback_service.get_feedback_by_trace(db, trace_id, user.id)


@router.get("/stats", response_model=FeedbackStatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await feedback_service.get_feedback_stats(db, user.id)