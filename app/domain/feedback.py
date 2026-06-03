from sqlalchemy import String, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_status: Mapped[str] = mapped_column(String(16), default="pending")
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)