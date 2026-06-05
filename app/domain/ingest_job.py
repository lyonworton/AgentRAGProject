from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, new_uuid

class IngestJob(Base):
    __tablename__ = "ingest_jobs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    collection_id: Mapped[str] = mapped_column(String(16), index=True)
    user_id: Mapped[str] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(16))
    config_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    total_docs: Mapped[int] = mapped_column(Integer, default=0)
    completed_docs: Mapped[int] = mapped_column(Integer, default=0)
    failed_docs: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
