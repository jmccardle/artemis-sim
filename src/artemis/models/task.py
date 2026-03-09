import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from artemis.models.base import Base, TimestampMixin, new_uuid


class TaskType(str, enum.Enum):
    AUTOMATED = "AUTOMATED"
    SIMULATED = "SIMULATED"
    USER = "USER"
    AGENT = "AGENT"


class TaskStatus(str, enum.Enum):
    NOT_READY = "NOT_READY"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REWORK = "REWORK"


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    mission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("missions.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=TaskStatus.NOT_READY)
    assigned_role: Mapped[str] = mapped_column(String(100), nullable=False)
    assigned_contractor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facility: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prerequisites: Mapped[dict | list] = mapped_column(JSON, nullable=False, default=list)
    nominal_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    simulated_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    simulated_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rework_of: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
