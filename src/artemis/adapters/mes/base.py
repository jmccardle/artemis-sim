from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from artemis.config import Settings


@dataclass
class ProcedureStep:
    index: int
    description: str
    signed_off: bool = False
    signed_by: str = ""
    signed_at: str = ""


@dataclass
class WADRecord:
    wad_number: str
    task_id: str
    procedure_name: str
    status: str
    steps: list[ProcedureStep] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""


@dataclass
class StepSignOffResult:
    success: bool
    wad_number: str
    step_index: int
    message: str = ""


class MESAdapter(ABC):
    @abstractmethod
    async def create_wad(
        self, task_id: str, procedure_name: str, operator_id: str
    ) -> WADRecord:
        """Create a Work Authorization Document for a task."""
        ...

    @abstractmethod
    async def sign_off_step(
        self, wad_number: str, step_index: int, operator_id: str
    ) -> StepSignOffResult:
        """Sign off a single procedure step in a WAD."""
        ...

    @abstractmethod
    async def get_wad_status(self, wad_number: str) -> WADRecord:
        """Retrieve the current status of a WAD."""
        ...

    @abstractmethod
    async def complete_wad(self, wad_number: str) -> WADRecord:
        """Mark a WAD as completed (all steps must be signed off)."""
        ...


def get_mes_adapter(settings: Settings) -> MESAdapter:
    """Factory: create the configured MES adapter. Raises ValueError for unknown providers."""
    from artemis.adapters.mes.mock import MockMESAdapter

    match settings.mes_provider:
        case "mock":
            return MockMESAdapter()
        case _:
            raise ValueError(
                f"Unknown MES provider: '{settings.mes_provider}'. "
                "Valid providers: mock, solumina"
            )
