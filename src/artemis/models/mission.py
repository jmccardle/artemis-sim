import enum
import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from artemis.models.base import Base, TimestampMixin, new_uuid


class MissionStatus(str, enum.Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Mission(TimestampMixin, Base):
    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    architecture_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "estes", "artemis"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=MissionStatus.CREATED)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
