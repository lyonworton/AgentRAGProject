from sqlalchemy import String, Boolean, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from app.domain.base import Base, TimestampMixin, new_uuid

class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "provider_configs"
    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(16), index=True)
    provider_type: Mapped[str] = mapped_column(String(16))
    provider_name: Mapped[str] = mapped_column(String(32))
    config_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)