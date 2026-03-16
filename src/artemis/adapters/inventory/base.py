from abc import ABC, abstractmethod
from dataclasses import dataclass

from artemis.config import Settings


@dataclass
class ReservationResult:
    reservation_id: str
    part_number: str
    quantity_reserved: int
    status: str


@dataclass
class ConsumptionResult:
    success: bool
    reservation_id: str
    message: str = ""


@dataclass
class MaterialCertResult:
    part_number: str
    lot_number: str
    certified: bool
    cert_number: str
    material_spec: str
    expiry_date: str


@dataclass
class InventoryLevel:
    part_number: str
    description: str
    on_hand: int
    reserved: int
    available: int


class InventoryAdapter(ABC):
    @abstractmethod
    async def reserve_parts(
        self, part_number: str, quantity: int, task_id: str
    ) -> ReservationResult:
        """Reserve parts from inventory for a task."""
        ...

    @abstractmethod
    async def consume_parts(self, reservation_id: str) -> ConsumptionResult:
        """Consume previously reserved parts (mark as used)."""
        ...

    @abstractmethod
    async def check_material_cert(
        self, part_number: str, lot_number: str
    ) -> MaterialCertResult:
        """Verify material certification for a part lot."""
        ...

    @abstractmethod
    async def get_inventory_level(self, part_number: str) -> InventoryLevel:
        """Get current inventory levels for a part number."""
        ...


def get_inventory_adapter(settings: Settings) -> InventoryAdapter:
    """Factory: create the configured inventory adapter. Raises ValueError for unknown providers."""
    from artemis.adapters.inventory.mock import MockInventoryAdapter

    match settings.inventory_provider:
        case "mock":
            return MockInventoryAdapter()
        case _:
            raise ValueError(
                f"Unknown inventory provider: '{settings.inventory_provider}'. "
                "Valid providers: mock, sap"
            )
