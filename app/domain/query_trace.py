from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, new_uuid

class QueryTrace(Base):
    __tablename__ = "query_traces"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    collection_ids: Mapped[dict] = mapped_column(JSONB, default=dict)
    query: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    citations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agent_graph: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now(timezone.utc))