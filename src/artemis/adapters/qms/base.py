from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from artemis.config import Settings


@dataclass
class NCRRecord:
    ncr_number: str
    task_id: str
    description: str
    severity: str
    status: str
    created_at: str
    dispositioned_at: str = ""


@dataclass
class CAPARecord:
    capa_number: str
    ncr_number: str
    corrective_action: str
    due_date: str
    status: str
    created_at: str


@dataclass
class InspectionRecord:
    inspection_id: str
    task_id: str
    inspector_id: str
    criteria_results: dict[str, bool] = field(default_factory=dict)
    overall_pass: bool = False
    recorded_at: str = ""


class QMSAdapter(ABC):
    @abstractmethod
    async def create_ncr(
        self, task_id: str, description: str, severity: str
    ) -> NCRRecord:
        """Create a Non-Conformance Report."""
        ...

    @abstractmethod
    async def create_capa(
        self, ncr_number: str, corrective_action: str, due_date: str
    ) -> CAPARecord:
        """Create a Corrective and Preventive Action for an NCR."""
        ...

    @abstractmethod
    async def record_inspection(
        self,
        task_id: str,
        inspector_id: str,
        criteria: list[str],
        results: dict[str, bool],
    ) -> InspectionRecord:
        """Record an inspection result against a task."""
        ...

    @abstractmethod
    async def get_open_ncrs(self, mission_id: str) -> list[NCRRecord]:
        """Get all open NCRs for a mission."""
        ...


def get_qms_adapter(settings: Settings) -> QMSAdapter:
    """Factory: create the configured QMS adapter. Raises ValueError for unknown providers."""
    from artemis.adapters.qms.mock import MockQMSAdapter

    match settings.qms_provider:
        case "mock":
            return MockQMSAdapter()
        case _:
            raise ValueError(
                f"Unknown QMS provider: '{settings.qms_provider}'. "
                "Valid providers: mock, etq"
            )
