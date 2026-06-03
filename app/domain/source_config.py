from datetime import datetime
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class SourceConfig(Base, TimestampMixin):
    __tablename__ = "source_configs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(256))
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)