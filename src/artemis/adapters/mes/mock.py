import random
from datetime import datetime, timezone

from artemis.adapters.mes.base import (
    MESAdapter,
    ProcedureStep,
    StepSignOffResult,
    WADRecord,
)

# KSC-authentic procedure step descriptions organized by category
_PROCEDURE_STEPS: dict[str, list[str]] = {
    "mechanical": [
        "Verify torque specification per NAS1587",
        "Install alignment pins and verify concentricity within 0.002 in",
        "Apply anti-seize compound per MIL-PRF-907",
        "Torque fasteners to spec and safety-wire per MS33540",
        "Perform leak check at 150% MEOP per KSC-GP-1224",
    ],
    "electrical": [
        "Perform electrical continuity check per MSFC-STD-3012",
        "Verify insulation resistance > 50 MΩ at 500 VDC",
        "Perform hi-pot test at 1500 VAC for 60 seconds",
        "Verify connector pin assignments per ICD drawing",
        "Mate connector and verify positive latch engagement",
    ],
    "inspection": [
        "Perform visual inspection per NASA-STD-5009 Level II",
        "Apply torque seal and photograph per QA-001",
        "Verify serial number and lot traceability per AS9102",
        "Perform dimensional inspection per drawing tolerance callouts",
        "Record as-built measurements on inspection traveler",
    ],
    "ordnance": [
        "Verify ESD grounding straps on all personnel",
        "Confirm ordnance safe/arm device in SAFE position",
        "Install initiator per ICD-200 with witnessed torque",
        "Perform resistance check on bridgewire circuit",
        "Apply tamper-evident seal and log serial number",
    ],
    "fluid": [
        "Evacuate system to < 500 microns per KSC-GP-1224",
        "Perform helium leak check per sensitivity level II",
        "Verify GN2 purge flow rate at 50 SCFM minimum",
        "Sample propellant per MIL-PRF-26536 and log lot number",
        "Flush system with IPA per contamination control plan",
    ],
}


class MockMESAdapter(MESAdapter):
    """In-memory mock MES adapter with KSC-authentic WAD generation."""

    def __init__(self) -> None:
        self._wads: dict[str, WADRecord] = {}
        self._sequence: int = 0

    def _next_wad_number(self) -> str:
        self._sequence += 1
        return f"WAD-2026-{self._sequence:04d}"

    def _generate_steps(self, procedure_name: str) -> list[ProcedureStep]:
        """Generate 3-5 realistic procedure steps based on procedure name."""
        num_steps = random.randint(3, 5)

        # Select a category based on procedure name keywords
        name_lower = procedure_name.lower()
        if any(kw in name_lower for kw in ("torque", "bolt", "mount", "attach", "mate")):
            category = "mechanical"
        elif any(kw in name_lower for kw in ("wire", "cable", "connector", "power")):
            category = "electrical"
        elif any(kw in name_lower for kw in ("inspect", "check", "verify", "nde")):
            category = "inspection"
        elif any(kw in name_lower for kw in ("ordnance", "pyro", "initiator", "detonator")):
            category = "ordnance"
        elif any(kw in name_lower for kw in ("fluid", "propellant", "purge", "leak")):
            category = "fluid"
        else:
            category = random.choice(list(_PROCEDURE_STEPS.keys()))

        pool = list(_PROCEDURE_STEPS[category])
        random.shuffle(pool)
        selected = pool[:num_steps]

        return [
            ProcedureStep(index=i, description=desc)
            for i, desc in enumerate(selected)
        ]

    async def create_wad(
        self, task_id: str, procedure_name: str, operator_id: str
    ) -> WADRecord:
        wad_number = self._next_wad_number()
        now = datetime.now(timezone.utc).isoformat()

        record = WADRecord(
            wad_number=wad_number,
            task_id=task_id,
            procedure_name=procedure_name,
            status="open",
            steps=self._generate_steps(procedure_name),
            created_at=now,
        )
        self._wads[wad_number] = record
        return record

    async def sign_off_step(
        self, wad_number: str, step_index: int, operator_id: str
    ) -> StepSignOffResult:
        if wad_number not in self._wads:
            raise ValueError(
                f"WAD not found: '{wad_number}'. "
                "Verify the WAD number and try again."
            )

        record = self._wads[wad_number]

        if record.status == "completed":
            return StepSignOffResult(
                success=False,
                wad_number=wad_number,
                step_index=step_index,
                message=f"WAD {wad_number} is already completed",
            )

        if step_index < 0 or step_index >= len(record.steps):
            raise ValueError(
                f"Step index {step_index} out of range for WAD {wad_number} "
                f"(has {len(record.steps)} steps, indices 0-{len(record.steps) - 1})"
            )

        step = record.steps[step_index]
        if step.signed_off:
            return StepSignOffResult(
                success=False,
                wad_number=wad_number,
                step_index=step_index,
                message=f"Step {step_index} already signed off by {step.signed_by}",
            )

        now = datetime.now(timezone.utc).isoformat()
        step.signed_off = True
        step.signed_by = operator_id
        step.signed_at = now

        return StepSignOffResult(
            success=True,
            wad_number=wad_number,
            step_index=step_index,
            message=f"Step {step_index} signed off by {operator_id}",
        )

    async def get_wad_status(self, wad_number: str) -> WADRecord:
        if wad_number not in self._wads:
            raise ValueError(
                f"WAD not found: '{wad_number}'. "
                "Verify the WAD number and try again."
            )
        return self._wads[wad_number]

    async def complete_wad(self, wad_number: str) -> WADRecord:
        if wad_number not in self._wads:
            raise ValueError(
                f"WAD not found: '{wad_number}'. "
                "Verify the WAD number and try again."
            )

        record = self._wads[wad_number]

        unsigned = [s for s in record.steps if not s.signed_off]
        if unsigned:
            indices = ", ".join(str(s.index) for s in unsigned)
            raise ValueError(
                f"Cannot complete WAD {wad_number}: "
                f"steps [{indices}] have not been signed off"
            )

        now = datetime.now(timezone.utc).isoformat()
        record.status = "completed"
        record.completed_at = now
        return record
