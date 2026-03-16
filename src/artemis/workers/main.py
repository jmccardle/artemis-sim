"""Temporal worker — registers all Phase 1 workflows and activities."""
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from artemis.activities.clock import persist_clock_state
from artemis.activities.facility import persist_facility_state
from artemis.activities.hello import say_hello
from artemis.activities.llm import (
    evaluate_proposal,
    generate_proposal,
    generate_rfp,
    generate_rubric,
    generate_test_report,
)
from artemis.activities.persistence import (
    complete_task_and_resolve,
    create_mission_tasks,
    create_rework_task,
    get_contractors_by_specialty,
    get_tasks_by_phase,
    save_artifact,
    send_escalation,
    update_mission_status,
    update_task_status,
)
from artemis.activities.external_systems import (
    check_certification,
    check_equipment_status,
    check_material_cert,
    check_pm_current,
    create_ncr,
    create_wad,
    record_inspection_qms,
    reserve_parts,
    run_preflight_check,
    sign_off_wad_step,
    verify_labor_auth,
)
from artemis.activities.simulation import run_inspection, simulate_task_duration
from artemis.config import get_settings
from artemis.workflows.clock import SimulatedClockWorkflow
from artemis.workflows.delivery import DeliveryWorkflow, TransportWorkflow
from artemis.workflows.facility_manager import FacilityManagerWorkflow
from artemis.workflows.hello import HelloWorkflow
from artemis.workflows.integration import IntegrationWorkflow
from artemis.workflows.launch_readiness import LaunchReadinessWorkflow
from artemis.workflows.mission import MissionWorkflow
from artemis.workflows.procurement import ProcurementWorkflow, RFPWorkflow

ALL_WORKFLOWS = [
    HelloWorkflow,
    SimulatedClockWorkflow,
    FacilityManagerWorkflow,
    MissionWorkflow,
    ProcurementWorkflow,
    RFPWorkflow,
    DeliveryWorkflow,
    TransportWorkflow,
    IntegrationWorkflow,
    LaunchReadinessWorkflow,
]

ALL_ACTIVITIES = [
    say_hello,
    # Clock
    persist_clock_state,
    # Facility
    persist_facility_state,
    # Persistence
    create_mission_tasks,
    update_mission_status,
    update_task_status,
    get_tasks_by_phase,
    # LLM
    generate_rfp,
    generate_rubric,
    generate_proposal,
    evaluate_proposal,
    generate_test_report,
    # Persistence (artifacts + contractors)
    save_artifact,
    get_contractors_by_specialty,
    # Simulation
    run_inspection,
    simulate_task_duration,
    # Prerequisite resolution + rework + escalation
    complete_task_and_resolve,
    create_rework_task,
    send_escalation,
    # External system adapters
    create_wad,
    sign_off_wad_step,
    check_equipment_status,
    check_pm_current,
    check_certification,
    verify_labor_auth,
    reserve_parts,
    check_material_cert,
    create_ncr,
    record_inspection_qms,
    run_preflight_check,
]


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    # Single worker on the orchestration queue for Phase 1
    # (Phase 2+ will split into dedicated workers per queue)
    worker = Worker(
        client,
        task_queue=settings.temporal_orchestration_queue,
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
    )

    print(f"Worker started on queue: {settings.temporal_orchestration_queue}")
    print(f"  Workflows: {len(ALL_WORKFLOWS)}")
    print(f"  Activities: {len(ALL_ACTIVITIES)}")
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
