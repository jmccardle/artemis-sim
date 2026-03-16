"""Workflow-safe data types for external system adapter activities.

All types are serializable dataclasses — safe to import in workflow code.
No database or I/O imports allowed.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── MES (Manufacturing Execution System) ───────────────────────────

@dataclass
class CreateWADInput:
    task_id: str
    procedure_name: str
    operator_id: str


@dataclass
class SignOffStepInput:
    wad_number: str
    step_index: int
    operator_id: str


# ── CMMS (Computerized Maintenance Management System) ──────────────

@dataclass
class CheckEquipmentInput:
    equipment_id: str
    facility_slug: str = ""


@dataclass
class CheckPMInput:
    equipment_id: str


# ── HR / Training ──────────────────────────────────────────────────

@dataclass
class CheckCertInput:
    operator_id: str
    cert_type: str


@dataclass
class VerifyLaborAuthInput:
    operator_id: str
    wbs_element: str


# ── Inventory / MRP ───────────────────────────────────────────────

@dataclass
class ReservePartsInput:
    part_number: str
    quantity: int
    task_id: str


@dataclass
class CheckMaterialCertInput:
    part_number: str
    lot_number: str


# ── QMS (Quality Management System) ───────────────────────────────

@dataclass
class CreateNCRInput:
    task_id: str
    description: str
    severity: str  # "minor", "major", "critical"


@dataclass
class RecordInspectionInput:
    task_id: str
    inspector_id: str
    criteria: list[str] = field(default_factory=list)
    results: dict[str, bool] = field(default_factory=dict)


# ── Preflight Check (composite) ───────────────────────────────────

@dataclass
class PreflightCheckInput:
    task_id: str
    task_name: str
    operator_id: str
    facility_slug: str
    equipment_ids: list[str] = field(default_factory=list)
    part_numbers: list[str] = field(default_factory=list)
    required_certs: list[str] = field(default_factory=list)
    wbs_element: str = ""


@dataclass
class PreflightItem:
    check_type: str  # "certification", "equipment_pm", "material_cert", "labor_auth", "wad"
    system: str      # "HR", "CMMS", "Inventory", "MES"
    status: str      # "PASS", "FAIL", "WARN"
    detail: str


@dataclass
class PreflightCheckResult:
    ready: bool
    checks: list[PreflightItem] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    wad_number: str = ""
