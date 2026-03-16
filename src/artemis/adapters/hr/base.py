from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from artemis.config import Settings


@dataclass
class CertificationStatus:
    operator_id: str
    cert_type: str
    is_valid: bool
    cert_number: str
    expiry_date: str
    issuing_authority: str


@dataclass
class LaborAuthResult:
    operator_id: str
    wbs_element: str
    authorized: bool
    reason: str


@dataclass
class TimecardResult:
    success: bool
    timecard_id: str
    message: str


@dataclass
class PersonnelRecord:
    operator_id: str
    name: str
    certifications: list[str] = field(default_factory=list)
    facility_slug: str = ""


class HRAdapter(ABC):
    @abstractmethod
    async def check_certification(
        self, operator_id: str, cert_type: str
    ) -> CertificationStatus:
        """Check whether an operator holds a valid certification."""
        ...

    @abstractmethod
    async def verify_labor_auth(
        self, operator_id: str, wbs_element: str
    ) -> LaborAuthResult:
        """Verify that an operator is authorized to charge against a WBS element."""
        ...

    @abstractmethod
    async def submit_timecard(
        self, operator_id: str, wbs_element: str, hours: float, description: str
    ) -> TimecardResult:
        """Submit a timecard entry for an operator."""
        ...

    @abstractmethod
    async def get_qualified_personnel(
        self, cert_type: str, facility_slug: str
    ) -> list[PersonnelRecord]:
        """Find all personnel at a facility holding a given certification."""
        ...


def get_hr_adapter(settings: Settings) -> HRAdapter:
    """Factory: create the configured HR adapter. Raises ValueError for unknown providers."""
    from artemis.adapters.hr.mock import MockHRAdapter

    match settings.hr_provider:
        case "mock":
            return MockHRAdapter()
        case _:
            raise ValueError(
                f"Unknown HR provider: '{settings.hr_provider}'. "
                "Valid providers: mock, peoplesoft"
            )
