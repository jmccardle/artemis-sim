import random
import uuid
from datetime import datetime, timedelta, timezone

from artemis.adapters.hr.base import (
    CertificationStatus,
    HRAdapter,
    LaborAuthResult,
    PersonnelRecord,
    TimecardResult,
)

# Valid certification types with their issuing authorities
_CERT_TYPES: dict[str, str] = {
    "crane_200ton": "KSC Rigging & Lifting Safety Office",
    "crane_325ton": "KSC Rigging & Lifting Safety Office",
    "crane_30ton": "KSC Rigging & Lifting Safety Office",
    "hydrazine_handling": "KSC Hypergolic Propellants Safety Office",
    "confined_space": "KSC Occupational Safety Branch",
    "NASA-STD-5009": "NASA NDE Certification Authority",
    "ordnance_handling": "KSC Range Safety / 45th SW",
    "eia_soldering": "KSC Quality Assurance Directorate",
    "fall_protection": "KSC Occupational Safety Branch",
    "respiratory_protection": "KSC Occupational Health Branch",
    "high_voltage": "KSC Electrical Engineering Division",
    "cryogenic_systems": "KSC Propellants & Life Support Branch",
}

# Pre-populated personnel registry: operator_id -> PersonnelRecord data
_PERSONNEL: dict[str, tuple[str, list[str], str]] = {
    # RPSF personnel
    "OP-RPSF-001": ("Marcus Webb", ["crane_200ton", "confined_space", "fall_protection"], "rpsf"),
    "OP-RPSF-002": ("Diana Reyes", ["crane_200ton", "hydrazine_handling", "respiratory_protection"], "rpsf"),
    "OP-RPSF-003": ("Terrence Okafor", ["crane_200ton", "fall_protection", "eia_soldering"], "rpsf"),
    "OP-RPSF-004": ("Sarah Lindqvist", ["NASA-STD-5009", "confined_space"], "rpsf"),
    "QA-RPSF-001": ("James Harwick", ["NASA-STD-5009", "crane_200ton", "fall_protection"], "rpsf"),
    # VAB personnel
    "OP-VAB-001": ("Chen Wei", ["crane_325ton", "crane_200ton", "fall_protection", "confined_space"], "vab-hb3"),
    "OP-VAB-002": ("Brenda Kowalski", ["crane_325ton", "fall_protection"], "vab-hb3"),
    "OP-VAB-003": ("Rashid Al-Farsi", ["crane_325ton", "high_voltage", "fall_protection"], "vab-hb3"),
    "QA-VAB-001": ("Linda Tomczak", ["NASA-STD-5009", "crane_325ton"], "vab-hb3"),
    "QA-VAB-002": ("Robert Espinoza", ["NASA-STD-5009", "confined_space"], "vab-hb3"),
    "QA-VAB-003": ("Anita Desai", ["NASA-STD-5009", "eia_soldering", "high_voltage"], "vab-hb3"),
    # MPPF personnel
    "OP-MPPF-001": ("Kyle Jennings", ["hydrazine_handling", "respiratory_protection", "confined_space"], "mppf"),
    "OP-MPPF-002": ("Fatima Novak", ["hydrazine_handling", "respiratory_protection", "ordnance_handling"], "mppf"),
    "QA-MPPF-001": ("Douglas Park", ["NASA-STD-5009", "hydrazine_handling"], "mppf"),
    # LC-39B personnel
    "OP-LC39B-001": ("Travis McClellan", ["cryogenic_systems", "fall_protection", "high_voltage"], "lc-39b"),
    "OP-LC39B-002": ("Grace Oduya", ["cryogenic_systems", "confined_space", "respiratory_protection"], "lc-39b"),
    "OP-LC39B-003": ("Martin Szabo", ["ordnance_handling", "fall_protection", "high_voltage"], "lc-39b"),
    "QA-LC39B-001": ("Evelyn Tran", ["NASA-STD-5009", "cryogenic_systems"], "lc-39b"),
}


class MockHRAdapter(HRAdapter):
    """In-memory mock HR adapter with KSC-authentic personnel and certification data."""

    def __init__(self) -> None:
        self._timecard_sequence: int = 0

    async def check_certification(
        self, operator_id: str, cert_type: str
    ) -> CertificationStatus:
        if operator_id not in _PERSONNEL:
            raise ValueError(
                f"Unknown operator ID: '{operator_id}'. "
                "Verify the operator ID against the personnel directory."
            )
        if cert_type not in _CERT_TYPES:
            raise ValueError(
                f"Unknown certification type: '{cert_type}'. "
                f"Valid types: {', '.join(sorted(_CERT_TYPES.keys()))}"
            )

        _name, certs, _facility = _PERSONNEL[operator_id]
        holds_cert = cert_type in certs

        rng = random.Random(hash((operator_id, cert_type)))
        now = datetime.now(timezone.utc)

        if holds_cert:
            # 95% chance the cert is still valid (not expired)
            is_valid = rng.random() < 0.95
            if is_valid:
                expiry = now + timedelta(days=rng.randint(30, 730))
            else:
                expiry = now - timedelta(days=rng.randint(1, 90))

            cert_number = f"CERT-{cert_type.upper().replace('-', '').replace('_', '')}-{rng.randint(10000, 99999)}"
        else:
            is_valid = False
            expiry = now - timedelta(days=365)
            cert_number = ""

        return CertificationStatus(
            operator_id=operator_id,
            cert_type=cert_type,
            is_valid=is_valid,
            cert_number=cert_number,
            expiry_date=expiry.date().isoformat(),
            issuing_authority=_CERT_TYPES[cert_type],
        )

    async def verify_labor_auth(
        self, operator_id: str, wbs_element: str
    ) -> LaborAuthResult:
        if operator_id not in _PERSONNEL:
            raise ValueError(
                f"Unknown operator ID: '{operator_id}'. "
                "Verify the operator ID against the personnel directory."
            )

        rng = random.Random(hash((operator_id, wbs_element)))
        # 98% authorization rate
        authorized = rng.random() < 0.98

        if authorized:
            reason = f"Operator {operator_id} authorized for WBS {wbs_element}"
        else:
            reason = (
                f"Operator {operator_id} not authorized for WBS {wbs_element}: "
                "labor authorization expired or WBS element not assigned to operator's organization"
            )

        return LaborAuthResult(
            operator_id=operator_id,
            wbs_element=wbs_element,
            authorized=authorized,
            reason=reason,
        )

    async def submit_timecard(
        self, operator_id: str, wbs_element: str, hours: float, description: str
    ) -> TimecardResult:
        if operator_id not in _PERSONNEL:
            raise ValueError(
                f"Unknown operator ID: '{operator_id}'. "
                "Verify the operator ID against the personnel directory."
            )

        if hours <= 0 or hours > 24:
            raise ValueError(
                f"Invalid hours value: {hours}. Must be between 0 (exclusive) and 24 (inclusive)."
            )

        self._timecard_sequence += 1
        timecard_id = f"TC-2026-{self._timecard_sequence:06d}"

        return TimecardResult(
            success=True,
            timecard_id=timecard_id,
            message=f"Timecard {timecard_id}: {hours}h charged to {wbs_element} for {operator_id}",
        )

    async def get_qualified_personnel(
        self, cert_type: str, facility_slug: str
    ) -> list[PersonnelRecord]:
        if cert_type not in _CERT_TYPES:
            raise ValueError(
                f"Unknown certification type: '{cert_type}'. "
                f"Valid types: {', '.join(sorted(_CERT_TYPES.keys()))}"
            )

        results: list[PersonnelRecord] = []
        for op_id, (name, certs, fac) in _PERSONNEL.items():
            if fac == facility_slug and cert_type in certs:
                results.append(
                    PersonnelRecord(
                        operator_id=op_id,
                        name=name,
                        certifications=list(certs),
                        facility_slug=fac,
                    )
                )

        return results
