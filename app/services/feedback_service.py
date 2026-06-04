from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.feedback import Feedback


async def create_feedback(
    db: AsyncSession,
    user_id: str,
    trace_id: str,
    rating: int | None = None,
    feedback_type: str | None = None,
    comment: str | None = None,
    correction: str | None = None,
) -> Feedback:
    fb = Feedback(
        user_id=user_id,
        trace_id=trace_id,
        rating=rating,
        feedback_type=feedback_type,
        comment=comment,
        correction=correction,
    )
    db.add(fb)
    await db.flush()
    return fb


async def get_feedback_by_trace(
    db: AsyncSession, trace_id: str, user_id: str
) -> Feedback | None:
    result = await db.execute(
        select(Feedback).where(
            Feedback.trace_id == trace_id, Feedback.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def get_feedback_stats(db: AsyncSession, user_id: str) -> dict:
    result = await db.execute(
        select(Feedback).where(Feedback.user_id == user_id)
    )
    rows = result.scalars().all()
    total = len(rows)
    ratings = [r.rating for r in rows if r.rating is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0
    by_type: dict[str, int] = {}
    for r in rows:
        if r.feedback_type:
            by_type[r.feedback_type] = by_type.get(r.feedback_type, 0) + 1
    return {"total": total, "avg_rating": round(avg_rating, 2), "by_type": by_type}