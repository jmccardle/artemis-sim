"""External system activities — bridge adapter layer into Temporal workflows.

Each activity instantiates its adapter via factory at runtime,
following the same pattern as activities/llm.py.
"""
from __future__ import annotations

from temporalio import activity

from artemis.workflows.adapter_types import (
    CheckCertInput,
    CheckEquipmentInput,
    CheckMaterialCertInput,
    CheckPMInput,
    CreateNCRInput,
    CreateWADInput,
    PreflightCheckInput,
    PreflightCheckResult,
    PreflightItem,
    RecordInspectionInput,
    ReservePartsInput,
    SignOffStepInput,
    VerifyLaborAuthInput,
)


# ── MES Activities ─────────────────────────────────────────────────

@activity.defn
async def create_wad(input: CreateWADInput):
    """Create a Work Authorizing Document via MES adapter."""
    from artemis.adapters.mes.base import get_mes_adapter
    from artemis.config import get_settings

    adapter = get_mes_adapter(get_settings())
    return await adapter.create_wad(input.task_id, input.procedure_name, input.operator_id)


@activity.defn
async def sign_off_wad_step(input: SignOffStepInput):
    """Sign off a WAD procedure step via MES adapter."""
    from artemis.adapters.mes.base import get_mes_adapter
    from artemis.config import get_settings

    adapter = get_mes_adapter(get_settings())
    return await adapter.sign_off_step(input.wad_number, input.step_index, input.operator_id)


# ── CMMS Activities ────────────────────────────────────────────────

@activity.defn
async def check_equipment_status(input: CheckEquipmentInput):
    """Check equipment availability via CMMS adapter."""
    from artemis.adapters.cmms.base import get_cmms_adapter
    from artemis.config import get_settings

    adapter = get_cmms_adapter(get_settings())
    return await adapter.get_equipment_status(input.equipment_id)


@activity.defn
async def check_pm_current(input: CheckPMInput):
    """Verify equipment PM is current via CMMS adapter."""
    from artemis.adapters.cmms.base import get_cmms_adapter
    from artemis.config import get_settings

    adapter = get_cmms_adapter(get_settings())
    return await adapter.check_pm_current(input.equipment_id)


# ── HR Activities ──────────────────────────────────────────────────

@activity.defn
async def check_certification(input: CheckCertInput):
    """Verify operator certification via HR adapter."""
    from artemis.adapters.hr.base import get_hr_adapter
    from artemis.config import get_settings

    adapter = get_hr_adapter(get_settings())
    return await adapter.check_certification(input.operator_id, input.cert_type)


@activity.defn
async def verify_labor_auth(input: VerifyLaborAuthInput):
    """Check WBS charge authorization via HR adapter."""
    from artemis.adapters.hr.base import get_hr_adapter
    from artemis.config import get_settings

    adapter = get_hr_adapter(get_settings())
    return await adapter.verify_labor_auth(input.operator_id, input.wbs_element)


# ── Inventory Activities ───────────────────────────────────────────

@activity.defn
async def reserve_parts(input: ReservePartsInput):
    """Reserve parts from inventory via Inventory adapter."""
    from artemis.adapters.inventory.base import get_inventory_adapter
    from artemis.config import get_settings

    adapter = get_inventory_adapter(get_settings())
    return await adapter.reserve_parts(input.part_number, input.quantity, input.task_id)


@activity.defn
async def check_material_cert(input: CheckMaterialCertInput):
    """Verify material certification via Inventory adapter."""
    from artemis.adapters.inventory.base import get_inventory_adapter
    from artemis.config import get_settings

    adapter = get_inventory_adapter(get_settings())
    return await adapter.check_material_cert(input.part_number, input.lot_number)


# ── QMS Activities ─────────────────────────────────────────────────

@activity.defn
async def create_ncr(input: CreateNCRInput):
    """Create a Non-Conformance Report via QMS adapter."""
    from artemis.adapters.qms.base import get_qms_adapter
    from artemis.config import get_settings

    adapter = get_qms_adapter(get_settings())
    return await adapter.create_ncr(input.task_id, input.description, input.severity)


@activity.defn
async def record_inspection_qms(input: RecordInspectionInput):
    """Record a formal inspection via QMS adapter."""
    from artemis.adapters.qms.base import get_qms_adapter
    from artemis.config import get_settings

    adapter = get_qms_adapter(get_settings())
    return await adapter.record_inspection(
        input.task_id, input.inspector_id, input.criteria, input.results,
    )


# ── Preflight Check (composite) ───────────────────────────────────

@activity.defn
async def run_preflight_check(input: PreflightCheckInput) -> PreflightCheckResult:
    """Run pre-task readiness checks across multiple external systems.

    Calls HR (certs), CMMS (equipment PM), Inventory (material certs),
    HR (labor auth), and MES (WAD creation) in sequence. Returns a
    composite readiness assessment.
    """
    from artemis.adapters.cmms.base import get_cmms_adapter
    from artemis.adapters.hr.base import get_hr_adapter
    from artemis.adapters.inventory.base import get_inventory_adapter
    from artemis.adapters.mes.base import get_mes_adapter
    from artemis.config import get_settings

    settings = get_settings()
    checks: list[PreflightItem] = []
    blocking: list[str] = []

    # 1. Check operator certifications
    hr = get_hr_adapter(settings)
    for cert_type in input.required_certs:
        cert = await hr.check_certification(input.operator_id, cert_type)
        if cert.is_valid:
            checks.append(PreflightItem(
                check_type="certification", system="HR", status="PASS",
                detail=f"{cert_type}: valid until {cert.expiry_date}",
            ))
        else:
            checks.append(PreflightItem(
                check_type="certification", system="HR", status="FAIL",
                detail=f"{cert_type}: EXPIRED or not found",
            ))
            blocking.append(f"Certification '{cert_type}' not current for {input.operator_id}")

    # 2. Check equipment PM status
    cmms = get_cmms_adapter(settings)
    for equip_id in input.equipment_ids:
        pm = await cmms.check_pm_current(equip_id)
        if pm.is_current:
            checks.append(PreflightItem(
                check_type="equipment_pm", system="CMMS", status="PASS",
                detail=f"{equip_id}: PM current, {pm.days_until_due}d until next due",
            ))
        else:
            checks.append(PreflightItem(
                check_type="equipment_pm", system="CMMS", status="FAIL",
                detail=f"{equip_id}: PM OVERDUE — {', '.join(pm.deficiencies) or 'maintenance required'}",
            ))
            blocking.append(f"Equipment '{equip_id}' PM not current")

    # 3. Check material certifications
    inventory = get_inventory_adapter(settings)
    for part in input.part_numbers:
        # Use a default lot number for the check
        mat = await inventory.check_material_cert(part, "LOT-CURRENT")
        if mat.certified:
            checks.append(PreflightItem(
                check_type="material_cert", system="Inventory", status="PASS",
                detail=f"{part}: certified per {mat.material_spec}",
            ))
        else:
            checks.append(PreflightItem(
                check_type="material_cert", system="Inventory", status="FAIL",
                detail=f"{part}: material cert EXPIRED or invalid",
            ))
            blocking.append(f"Material cert for '{part}' not valid")

    # 4. Check labor authorization
    if input.wbs_element:
        labor = await hr.verify_labor_auth(input.operator_id, input.wbs_element)
        if labor.authorized:
            checks.append(PreflightItem(
                check_type="labor_auth", system="HR", status="PASS",
                detail=f"WBS {input.wbs_element}: authorized",
            ))
        else:
            checks.append(PreflightItem(
                check_type="labor_auth", system="HR", status="FAIL",
                detail=f"WBS {input.wbs_element}: {labor.reason}",
            ))
            blocking.append(f"Labor not authorized for WBS {input.wbs_element}")

    # 5. Create WAD (only if all other checks pass)
    wad_number = ""
    if not blocking:
        mes = get_mes_adapter(settings)
        wad = await mes.create_wad(input.task_id, input.task_name, input.operator_id)
        wad_number = wad.wad_number
        checks.append(PreflightItem(
            check_type="wad", system="MES", status="PASS",
            detail=f"WAD {wad.wad_number} created with {len(wad.steps)} steps",
        ))
    else:
        checks.append(PreflightItem(
            check_type="wad", system="MES", status="FAIL",
            detail="WAD not created — blocking issues must be resolved first",
        ))

    return PreflightCheckResult(
        ready=len(blocking) == 0,
        checks=checks,
        blocking_reasons=blocking,
        wad_number=wad_number,
    )
