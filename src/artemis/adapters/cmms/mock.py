import random
from datetime import datetime, timedelta, timezone

from artemis.adapters.cmms.base import (
    CMMSAdapter,
    EquipmentStatus,
    PMCheckResult,
    WorkOrder,
)

# KSC-authentic equipment registry: facility_slug -> list of (equipment_id, name, description)
_EQUIPMENT_REGISTRY: dict[str, list[tuple[str, str]]] = {
    "rpsf": [
        ("RPSF-OHC-1", "RPSF 200-Ton Overhead Crane #1"),
        ("RPSF-OHC-2", "RPSF 200-Ton Overhead Crane #2"),
        ("RPSF-ROT-1", "RPSF SRB Rotation Fixture"),
        ("RPSF-HYD-1", "RPSF Hydraulic Stacking System"),
        ("RPSF-XFER-1", "RPSF Segment Transporter"),
    ],
    "vab-hb3": [
        ("VAB-HB3-CRANE-325T", "VAB High Bay 3 325-Ton Bridge Crane"),
        ("VAB-HB3-CRANE-325T-2", "VAB High Bay 3 325-Ton Bridge Crane #2"),
        ("VAB-HB3-PLAT-1", "VAB High Bay 3 Work Platform A"),
        ("VAB-HB3-PLAT-2", "VAB High Bay 3 Work Platform B"),
        ("VAB-HB3-PLAT-3", "VAB High Bay 3 Work Platform C"),
        ("VAB-HB3-ENV-1", "VAB High Bay 3 Environmental Control Unit"),
    ],
    "mppf": [
        ("MPPF-CRANE-10T", "MPPF 10-Ton Overhead Crane"),
        ("MPPF-CLN-1", "MPPF Clean Room HEPA System"),
        ("MPPF-FUEL-1", "MPPF Hypergolic Fueling Cart"),
        ("MPPF-SCALE-1", "MPPF Precision Weighing System"),
    ],
    "lc-39b": [
        ("LC39B-FSS-CRANE", "LC-39B Fixed Service Structure Crane"),
        ("LC39B-MLP-1", "Mobile Launcher Platform #1"),
        ("LC39B-SWG-1", "LC-39B Tail Service Mast Swing Arm"),
        ("LC39B-TSM-1", "LC-39B Tail Service Mast"),
        ("LC39B-SOUND-1", "LC-39B Sound Suppression Water System"),
    ],
    "osb-2": [
        ("OSB2-CRANE-30T", "Orbiter Processing Bay 2 30-Ton Crane"),
        ("OSB2-PLAT-1", "OSB-2 Access Platform Set"),
        ("OSB2-DESICC-1", "OSB-2 Desiccant Dehumidifier"),
    ],
    "sspf": [
        ("SSPF-CRANE-25T", "SSPF 25-Ton Overhead Crane"),
        ("SSPF-CLN-1", "SSPF Class 10K Clean Room System"),
        ("SSPF-FITCHK-1", "SSPF Payload Fit Check Fixture"),
    ],
}

# Build a flat lookup: equipment_id -> (name, facility_slug)
_EQUIPMENT_LOOKUP: dict[str, tuple[str, str]] = {}
for _facility, _items in _EQUIPMENT_REGISTRY.items():
    for _eid, _ename in _items:
        _EQUIPMENT_LOOKUP[_eid] = (_ename, _facility)


class MockCMMSAdapter(CMMSAdapter):
    """In-memory mock CMMS adapter with KSC-authentic equipment data."""

    def __init__(self) -> None:
        self._wo_sequence: int = 0
        self._work_orders: dict[str, WorkOrder] = {}

    def _make_equipment_status(
        self, equipment_id: str, name: str, facility_slug: str
    ) -> EquipmentStatus:
        """Generate a realistic equipment status record."""
        rng = random.Random(hash(equipment_id))
        now = datetime.now(timezone.utc)

        # 95% chance equipment is in good shape
        is_good = rng.random() < 0.95
        condition = round(rng.uniform(0.85, 1.0) if is_good else rng.uniform(0.50, 0.84), 2)
        status = "operational" if is_good else rng.choice(["degraded", "maintenance"])

        last_pm = now - timedelta(days=rng.randint(5, 85))
        next_pm = last_pm + timedelta(days=90)
        is_available = status == "operational" and next_pm > now

        return EquipmentStatus(
            equipment_id=equipment_id,
            name=name,
            facility_slug=facility_slug,
            status=status,
            condition_rating=condition,
            last_pm_date=last_pm.date().isoformat(),
            next_pm_date=next_pm.date().isoformat(),
            is_available=is_available,
        )

    async def get_equipment_status(self, equipment_id: str) -> EquipmentStatus:
        if equipment_id not in _EQUIPMENT_LOOKUP:
            raise ValueError(
                f"Unknown equipment ID: '{equipment_id}'. "
                "Verify the equipment ID against the facility equipment registry."
            )
        name, facility_slug = _EQUIPMENT_LOOKUP[equipment_id]
        return self._make_equipment_status(equipment_id, name, facility_slug)

    async def check_pm_current(self, equipment_id: str) -> PMCheckResult:
        if equipment_id not in _EQUIPMENT_LOOKUP:
            raise ValueError(
                f"Unknown equipment ID: '{equipment_id}'. "
                "Verify the equipment ID against the facility equipment registry."
            )

        rng = random.Random(hash(equipment_id))
        now = datetime.now(timezone.utc)

        last_pm = now - timedelta(days=rng.randint(5, 85))
        next_pm = last_pm + timedelta(days=90)
        days_until_due = (next_pm.date() - now.date()).days
        is_current = days_until_due > 0

        deficiencies: list[str] = []
        if not is_current:
            deficiencies.append("Preventive maintenance overdue")
        elif days_until_due < 14:
            # ~5% chance of a minor deficiency noted during last PM
            if rng.random() < 0.30:
                deficiency_pool = [
                    "Minor hydraulic fluid seepage noted at cylinder 2 gland",
                    "Wire rope showing early signs of wear at sheave contact point",
                    "Limit switch LS-04 response time marginally above spec",
                    "Anti-two-block sensor calibration drift noted — recal recommended",
                    "Brake pad wear approaching 60% service limit",
                ]
                deficiencies.append(rng.choice(deficiency_pool))

        return PMCheckResult(
            equipment_id=equipment_id,
            is_current=is_current,
            days_until_due=days_until_due,
            last_pm_date=last_pm.date().isoformat(),
            deficiencies=deficiencies,
        )

    async def create_work_order(
        self, equipment_id: str, description: str, priority: str
    ) -> WorkOrder:
        if equipment_id not in _EQUIPMENT_LOOKUP:
            raise ValueError(
                f"Unknown equipment ID: '{equipment_id}'. "
                "Verify the equipment ID against the facility equipment registry."
            )

        valid_priorities = ("low", "medium", "high", "critical")
        if priority not in valid_priorities:
            raise ValueError(
                f"Invalid work order priority: '{priority}'. "
                f"Must be one of: {', '.join(valid_priorities)}"
            )

        self._wo_sequence += 1
        now = datetime.now(timezone.utc).isoformat()
        wo_number = f"WO-2026-{self._wo_sequence:05d}"

        wo = WorkOrder(
            wo_number=wo_number,
            equipment_id=equipment_id,
            description=description,
            priority=priority,
            status="open",
            created_at=now,
        )
        self._work_orders[wo_number] = wo
        return wo

    async def get_facility_equipment(
        self, facility_slug: str
    ) -> list[EquipmentStatus]:
        if facility_slug not in _EQUIPMENT_REGISTRY:
            raise ValueError(
                f"Unknown facility: '{facility_slug}'. "
                f"Known facilities: {', '.join(sorted(_EQUIPMENT_REGISTRY.keys()))}"
            )

        results: list[EquipmentStatus] = []
        for equipment_id, name in _EQUIPMENT_REGISTRY[facility_slug]:
            results.append(
                self._make_equipment_status(equipment_id, name, facility_slug)
            )
        return results
