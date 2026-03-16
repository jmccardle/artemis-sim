import uuid
from datetime import datetime, timezone

from artemis.adapters.qms.base import (
    CAPARecord,
    InspectionRecord,
    NCRRecord,
    QMSAdapter,
)

_VALID_SEVERITIES = ("minor", "major", "critical")


class MockQMSAdapter(QMSAdapter):
    """In-memory mock QMS adapter with auto-incrementing NCR/CAPA numbers."""

    def __init__(self) -> None:
        self._ncr_sequence: int = 0
        self._capa_sequence: int = 0
        self._inspection_sequence: int = 0
        self._ncrs: dict[str, NCRRecord] = {}
        self._capas: dict[str, CAPARecord] = {}
        # mission_id -> list of NCR numbers for fast lookup
        self._mission_ncrs: dict[str, list[str]] = {}

    async def create_ncr(
        self, task_id: str, description: str, severity: str
    ) -> NCRRecord:
        if severity not in _VALID_SEVERITIES:
            raise ValueError(
                f"Invalid NCR severity: '{severity}'. "
                f"Must be one of: {', '.join(_VALID_SEVERITIES)}"
            )

        self._ncr_sequence += 1
        ncr_number = f"NCR-2026-{self._ncr_sequence:04d}"
        now = datetime.now(timezone.utc).isoformat()

        record = NCRRecord(
            ncr_number=ncr_number,
            task_id=task_id,
            description=description,
            severity=severity,
            status="open",
            created_at=now,
        )
        self._ncrs[ncr_number] = record

        # Extract mission_id from task_id (convention: task_id starts with mission_id prefix)
        # Also store under the raw task_id so get_open_ncrs can work with either
        mission_id = task_id.split("-")[0] if "-" in task_id else task_id
        self._mission_ncrs.setdefault(mission_id, []).append(ncr_number)
        if mission_id != task_id:
            self._mission_ncrs.setdefault(task_id, []).append(ncr_number)

        return record

    async def create_capa(
        self, ncr_number: str, corrective_action: str, due_date: str
    ) -> CAPARecord:
        if ncr_number not in self._ncrs:
            raise ValueError(
                f"Unknown NCR number: '{ncr_number}'. "
                "Verify the NCR number and try again."
            )

        self._capa_sequence += 1
        capa_number = f"CAPA-2026-{self._capa_sequence:04d}"
        now = datetime.now(timezone.utc).isoformat()

        record = CAPARecord(
            capa_number=capa_number,
            ncr_number=ncr_number,
            corrective_action=corrective_action,
            due_date=due_date,
            status="open",
            created_at=now,
        )
        self._capas[capa_number] = record

        # Update the NCR status to indicate CAPA is in progress
        self._ncrs[ncr_number].status = "capa_in_progress"

        return record

    async def record_inspection(
        self,
        task_id: str,
        inspector_id: str,
        criteria: list[str],
        results: dict[str, bool],
    ) -> InspectionRecord:
        # Validate that results keys match criteria
        missing_criteria = set(criteria) - set(results.keys())
        if missing_criteria:
            raise ValueError(
                f"Results missing for criteria: {', '.join(sorted(missing_criteria))}. "
                "All criteria must have a corresponding result."
            )

        extra_results = set(results.keys()) - set(criteria)
        if extra_results:
            raise ValueError(
                f"Results provided for unknown criteria: {', '.join(sorted(extra_results))}. "
                "Results keys must match the criteria list."
            )

        self._inspection_sequence += 1
        inspection_id = f"INSP-2026-{self._inspection_sequence:05d}"
        now = datetime.now(timezone.utc).isoformat()

        overall_pass = all(results.values())

        record = InspectionRecord(
            inspection_id=inspection_id,
            task_id=task_id,
            inspector_id=inspector_id,
            criteria_results=dict(results),
            overall_pass=overall_pass,
            recorded_at=now,
        )
        return record

    async def get_open_ncrs(self, mission_id: str) -> list[NCRRecord]:
        ncr_numbers = self._mission_ncrs.get(mission_id, [])
        return [
            self._ncrs[n]
            for n in ncr_numbers
            if n in self._ncrs and self._ncrs[n].status != "closed"
        ]
