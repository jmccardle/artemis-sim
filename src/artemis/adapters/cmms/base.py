from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from artemis.config import Settings


@dataclass
class EquipmentStatus:
    equipment_id: str
    name: str
    facility_slug: str
    status: str
    condition_rating: float
    last_pm_date: str
    next_pm_date: str
    is_available: bool


@dataclass
class PMCheckResult:
    equipment_id: str
    is_current: bool
    days_until_due: int
    last_pm_date: str
    deficiencies: list[str] = field(default_factory=list)


@dataclass
class WorkOrder:
    wo_number: str
    equipment_id: str
    description: str
    priority: str
    status: str
    created_at: str


class CMMSAdapter(ABC):
    @abstractmethod
    async def get_equipment_status(self, equipment_id: str) -> EquipmentStatus:
        """Get the current status of a piece of equipment."""
        ...

    @abstractmethod
    async def check_pm_current(self, equipment_id: str) -> PMCheckResult:
        """Check whether preventive maintenance is current for equipment."""
        ...

    @abstractmethod
    async def create_work_order(
        self, equipment_id: str, description: str, priority: str
    ) -> WorkOrder:
        """Create a maintenance work order."""
        ...

    @abstractmethod
    async def get_facility_equipment(
        self, facility_slug: str
    ) -> list[EquipmentStatus]:
        """List all equipment assigned to a facility."""
        ...


def get_cmms_adapter(settings: Settings) -> CMMSAdapter:
    """Factory: create the configured CMMS adapter. Raises ValueError for unknown providers."""
    from artemis.adapters.cmms.mock import MockCMMSAdapter

    match settings.cmms_provider:
        case "mock":
            return MockCMMSAdapter()
        case _:
            raise ValueError(
                f"Unknown CMMS provider: '{settings.cmms_provider}'. "
                "Valid providers: mock, maximo"
            )
