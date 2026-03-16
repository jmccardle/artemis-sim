import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from artemis.models.base import Base, new_uuid


class ArtifactType(str, enum.Enum):
    RFP = "RFP"
    PROPOSAL = "PROPOSAL"
    RUBRIC = "RUBRIC"
    SCORECARD = "SCORECARD"
    TEST_REPORT = "TEST_REPORT"
    FAILURE_REPORT = "FAILURE_REPORT"
    INVOICE = "INVOICE"
    WORK_REPORT = "WORK_REPORT"
    PREFLIGHT_REPORT = "PREFLIGHT_REPORT"
    ESCALATION_NOTICE = "ESCALATION_NOTICE"
    NCR = "NCR"
    WAD = "WAD"


class TaskArtifact(Base):
    __tablename__ = "task_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
