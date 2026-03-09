import uuid

from sqlalchemy import Float, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from artemis.models.base import Base, TimestampMixin, new_uuid


class Contractor(TimestampMixin, Base):
    __tablename__ = "contractors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    reliability: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    cost_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    speed_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    specialties: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    llm_profile: Mapped[str] = mapped_column(Text, nullable=False, default="")
    branding: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
