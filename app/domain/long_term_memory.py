from sqlalchemy import String, Float, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.domain.base import Base, TimestampMixin, new_uuid

class LongTermMemory(Base, TimestampMixin):
    __tablename__ = "long_term_memories"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    type: Mapped[str] = mapped_column(String(16))
    entity: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    source_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    corrected_by: Mapped[str | None] = mapped_column(String(16), nullable=True)