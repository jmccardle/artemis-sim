import uuid

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from artemis.models.base import Base, TimestampMixin, new_uuid


class Facility(TimestampMixin, Base):
    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_occupancy: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capabilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
