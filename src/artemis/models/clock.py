import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from artemis.models.base import Base, new_uuid


class SimulatedClock(Base):
    """Singleton row tracking the system-wide simulated time."""

    __tablename__ = "simulated_clock"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    current_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_advance_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
