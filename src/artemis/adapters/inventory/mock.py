import random
import uuid
from datetime import datetime, timedelta, timezone

from artemis.adapters.inventory.base import (
    ConsumptionResult,
    InventoryAdapter,
    InventoryLevel,
    MaterialCertResult,
    ReservationResult,
)

# KSC-authentic parts inventory: part_number -> (description, initial_on_hand)
_PARTS_CATALOG: dict[str, tuple[str, int]] = {
    # SLS SRB components
    "SLS-SRB-SEG-001": ("SRB Field Joint Seal Kit (Viton O-ring set)", 24),
    "SLS-SRB-SEG-002": ("SRB Factory Joint Shim Kit", 18),
    "SLS-SRB-IGN-001": ("SRB Igniter Booster Charge Assembly", 6),
    "SLS-SRB-NZL-001": ("SRB Nozzle Flex Bearing Seal", 8),
    "SLS-SRB-TVC-001": ("SRB TVC Actuator Hydraulic Seal Kit", 12),
    # SLS Core Stage
    "SLS-CS-RS25-001": ("RS-25 Main Combustion Chamber Seal", 8),
    "SLS-CS-RS25-002": ("RS-25 High-Pressure Fuel Turbopump Bearing", 6),
    "SLS-CS-RS25-003": ("RS-25 Low-Pressure Oxidizer Turbopump Inducer", 4),
    "SLS-CS-RS25-004": ("RS-25 Turbopump Seal (high-pressure LOX)", 10),
    "SLS-CS-AFT-001": ("Core Stage Aft Skirt Attach Bolt Kit (NAS1587-16)", 16),
    "SLS-CS-LH2-001": ("LH2 Tank Dome Closeout Fastener Kit", 20),
    "SLS-CS-LOX-001": ("LOX Tank Feedline Bellows Assembly", 4),
    # ICPS / Upper Stage
    "SLS-ICPS-RL10-001": ("RL-10 Engine Nozzle Extension Seal", 4),
    "SLS-ICPS-LH2-001": ("ICPS LH2 Feedline Flex Hose Assembly", 6),
    # Orion (Estes model rocket stand-in)
    "ESTES-STR-042": ("Model Rocket Body Tube BT-60 (18 in)", 50),
    "ESTES-NOS-007": ("Model Rocket Ogive Nose Cone PNC-60", 40),
    "ESTES-FIN-015": ("Laser-Cut Balsa Fin Set (3-fin)", 35),
    "ESTES-MTR-024": ("Motor Mount Tube MMT-24mm", 45),
    "ESTES-REC-003": ("Recovery Parachute 18-in Ripstop Nylon", 30),
    "ESTES-SHK-001": ("Elastic Shock Cord Kit 36-in", 60),
    # General / common hardware
    "KSC-HDW-001": ("AN960-816 Flat Washer (1-in, Grade 8)", 500),
    "KSC-HDW-002": ("MS21044N08 Self-Locking Nut (1/2-20)", 400),
    "KSC-HDW-003": ("NAS1587-8 Hex Head Bolt (1/2-20 x 2-in)", 300),
    "KSC-CLN-001": ("IPA Wipe (lint-free, 9x9 in, 150-ct box)", 100),
    "KSC-LUB-001": ("Braycote 601EF Vacuum Grease (2 oz tube)", 25),
}

# Material specifications per part category prefix
_MATERIAL_SPECS: dict[str, str] = {
    "SLS-SRB": "MSFC-SPEC-3679 Rev D",
    "SLS-CS": "MSFC-SPEC-3676 Rev C",
    "SLS-ICPS": "MSFC-SPEC-3682 Rev B",
    "ESTES": "NAR Safety Code / Estes Industries QC",
    "KSC-HDW": "AMS 5731 / ASTM A574",
    "KSC-CLN": "IEST-STD-CC1246E",
    "KSC-LUB": "MIL-PRF-27617 Type III",
}


def _get_material_spec(part_number: str) -> str:
    for prefix, spec in _MATERIAL_SPECS.items():
        if part_number.startswith(prefix):
            return spec
    return "MIL-STD-1916"


class MockInventoryAdapter(InventoryAdapter):
    """In-memory mock inventory adapter with KSC-authentic part numbers."""

    def __init__(self) -> None:
        # Mutable copy of inventory levels
        self._inventory: dict[str, dict] = {}
        for pn, (desc, on_hand) in _PARTS_CATALOG.items():
            self._inventory[pn] = {
                "description": desc,
                "on_hand": on_hand,
                "reserved": 0,
            }

        self._reservations: dict[str, dict] = {}

    async def reserve_parts(
        self, part_number: str, quantity: int, task_id: str
    ) -> ReservationResult:
        if part_number not in self._inventory:
            raise ValueError(
                f"Unknown part number: '{part_number}'. "
                "Verify the part number against the parts catalog."
            )

        if quantity <= 0:
            raise ValueError(
                f"Invalid reservation quantity: {quantity}. Must be a positive integer."
            )

        inv = self._inventory[part_number]
        available = inv["on_hand"] - inv["reserved"]

        if quantity > available:
            return ReservationResult(
                reservation_id="",
                part_number=part_number,
                quantity_reserved=0,
                status=f"insufficient_stock: requested {quantity}, available {available}",
            )

        reservation_id = f"RSV-{uuid.uuid4().hex[:8].upper()}"
        inv["reserved"] += quantity

        self._reservations[reservation_id] = {
            "part_number": part_number,
            "quantity": quantity,
            "task_id": task_id,
            "consumed": False,
        }

        return ReservationResult(
            reservation_id=reservation_id,
            part_number=part_number,
            quantity_reserved=quantity,
            status="reserved",
        )

    async def consume_parts(self, reservation_id: str) -> ConsumptionResult:
        if reservation_id not in self._reservations:
            raise ValueError(
                f"Unknown reservation ID: '{reservation_id}'. "
                "Verify the reservation ID and try again."
            )

        rsv = self._reservations[reservation_id]

        if rsv["consumed"]:
            return ConsumptionResult(
                success=False,
                reservation_id=reservation_id,
                message=f"Reservation {reservation_id} has already been consumed",
            )

        inv = self._inventory[rsv["part_number"]]
        inv["on_hand"] -= rsv["quantity"]
        inv["reserved"] -= rsv["quantity"]
        rsv["consumed"] = True

        return ConsumptionResult(
            success=True,
            reservation_id=reservation_id,
            message=f"Consumed {rsv['quantity']}x {rsv['part_number']} for task {rsv['task_id']}",
        )

    async def check_material_cert(
        self, part_number: str, lot_number: str
    ) -> MaterialCertResult:
        if part_number not in self._inventory:
            raise ValueError(
                f"Unknown part number: '{part_number}'. "
                "Verify the part number against the parts catalog."
            )

        rng = random.Random(hash((part_number, lot_number)))
        now = datetime.now(timezone.utc)

        # 97% of material certs are valid
        certified = rng.random() < 0.97
        if certified:
            expiry = now + timedelta(days=rng.randint(90, 1095))
        else:
            expiry = now - timedelta(days=rng.randint(1, 180))

        cert_number = f"MCERT-{rng.randint(100000, 999999)}"
        material_spec = _get_material_spec(part_number)

        return MaterialCertResult(
            part_number=part_number,
            lot_number=lot_number,
            certified=certified,
            cert_number=cert_number,
            material_spec=material_spec,
            expiry_date=expiry.date().isoformat(),
        )

    async def get_inventory_level(self, part_number: str) -> InventoryLevel:
        if part_number not in self._inventory:
            raise ValueError(
                f"Unknown part number: '{part_number}'. "
                "Verify the part number against the parts catalog."
            )

        inv = self._inventory[part_number]
        return InventoryLevel(
            part_number=part_number,
            description=inv["description"],
            on_hand=inv["on_hand"],
            reserved=inv["reserved"],
            available=inv["on_hand"] - inv["reserved"],
        )
