"""MissionWorkflow — top-level orchestration for a single mission.

Workflow ID: "mission-{mission_id}"
Task queue: artemis-orchestration
"""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from artemis.activities.persistence import (
        CreateMissionTasksInput,
        CreateMissionTasksResult,
        UpdateMissionStatusInput,
        create_mission_tasks,
        update_mission_status,
    )

from artemis.workflows.data_types import (
    ORCHESTRATION_QUEUE,
    IntegrationStepSpec,
    MissionPhase,
    MissionState,
    ProcurementResult,
    TaskCompletionInput,
    delivery_workflow_id,
    launch_readiness_workflow_id,
    mission_workflow_id,
    procurement_workflow_id,
)
from artemis.workflows.delivery import DeliveryComponentInfo, DeliveryInput, DeliveryWorkflow
from artemis.workflows.integration import IntegrationInput, IntegrationWorkflow
from artemis.workflows.launch_readiness import LaunchReadinessInput, LaunchReadinessWorkflow
from artemis.workflows.procurement import ComponentBid, ProcurementInput, ProcurementWorkflow

# ── Static architecture definitions (workflow-safe, no I/O) ──────────

# Component name→type map for known architectures
ESTES_COMPONENTS = [
    ComponentBid("B-class solid motor", "propulsion"),
    ComponentBid("Plastic parachute", "recovery-systems"),
    ComponentBid("Rocket body tube", "structures"),
    ComponentBid("Fin set (x3)", "structures"),
    ComponentBid("Bottle of glue", "materials"),
]

# Delivery component specs: name, type, contractor_slug (filled at runtime),
# transport_method, origin, destination, nominal_duration_seconds
ESTES_DELIVERY_COMPONENTS = [
    DeliveryComponentInfo("B-class solid motor", "propulsion", "", "truck", "Hobby Shop", "The Garage", 7200),
    DeliveryComponentInfo("Plastic parachute", "recovery-systems", "", "truck", "Hobby Shop", "The Garage", 3600),
    DeliveryComponentInfo("Rocket body tube", "structures", "", "truck", "Hobby Shop", "The Garage", 3600),
    DeliveryComponentInfo("Fin set (x3)", "structures", "", "truck", "Hobby Shop", "The Garage", 3600),
    DeliveryComponentInfo("Bottle of glue", "materials", "", "truck", "Hobby Shop", "The Garage", 1800),
]

ESTES_INTEGRATION_STEPS = [
    IntegrationStepSpec(
        name="Glue fins to body tube",
        components_required=["Rocket body tube", "Fin set (x3)", "Bottle of glue"],
        facility="The Garage",
        nominal_duration_seconds=7200,
        failure_probability=0.10,
        output_component="BodyAndFins",
    ),
    IntegrationStepSpec(
        name="Install solid motor",
        components_required=["B-class solid motor"],
        facility="The Garage",
        nominal_duration_seconds=3600,
        failure_probability=0.05,
        output_component="",
    ),
    IntegrationStepSpec(
        name="Install parachute",
        components_required=["Plastic parachute"],
        facility="The Garage",
        nominal_duration_seconds=1800,
        failure_probability=0.02,
        output_component="",
    ),
]


def _build_delivery_components(
    architecture: str, procurement_result: ProcurementResult
) -> list[DeliveryComponentInfo]:
    """Map procurement awards onto static delivery component defs."""
    if architecture != "estes":
        return []
    components = []
    for template in ESTES_DELIVERY_COMPONENTS:
        contractor_slug = procurement_result.awards.get(template.name, "")
        components.append(DeliveryComponentInfo(
            name=template.name,
            component_type=template.component_type,
            contractor_slug=contractor_slug,
            transport_method=template.transport_method,
            origin=template.origin,
            destination=template.destination,
            nominal_duration_seconds=template.nominal_duration_seconds,
        ))
    return components


@workflow.defn
class MissionWorkflow:
    """Top-level workflow orchestrating a single mission through all phases.

    Phases run sequentially: PROCUREMENT -> DELIVERY -> INTEGRATION -> LAUNCH_READINESS.
    Each phase runs as a child workflow.
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._name: str = ""
        self._architecture: str = ""
        self._phase: MissionPhase = MissionPhase.PROCUREMENT
        self._status: str = "IN_PROGRESS"
        self._phase_complete: bool = False
        self._progress_pct: float = 0.0

    @workflow.run
    async def run(self, mission_id: str, architecture_name: str) -> str:
        self._mission_id = mission_id
        self._architecture = architecture_name

        # Create all tasks in DB
        result = await workflow.execute_activity(
            create_mission_tasks,
            CreateMissionTasksInput(
                mission_id=mission_id,
                architecture_name=architecture_name,
            ),
            start_to_close_timeout=timedelta(seconds=30),
        )
        self._name = result.mission_name

        # Update mission status to IN_PROGRESS
        await workflow.execute_activity(
            update_mission_status,
            UpdateMissionStatusInput(mission_id=mission_id, status="IN_PROGRESS"),
            start_to_close_timeout=timedelta(seconds=10),
        )

        phases = [
            MissionPhase.PROCUREMENT,
            MissionPhase.DELIVERY,
            MissionPhase.INTEGRATION,
            MissionPhase.LAUNCH_READINESS,
        ]

        # ── PROCUREMENT ──────────────────────────────────────────────
        self._phase = MissionPhase.PROCUREMENT
        self._phase_complete = False

        components = ESTES_COMPONENTS if architecture_name == "estes" else []
        procurement_result: ProcurementResult = await workflow.execute_child_workflow(
            ProcurementWorkflow.run,
            ProcurementInput(
                mission_id=mission_id,
                components=components,
            ),
            id=procurement_workflow_id(mission_id),
            task_queue=ORCHESTRATION_QUEUE,
        )
        self._phase_complete = True
        self._progress_pct = 25.0

        # ── DELIVERY ─────────────────────────────────────────────────
        self._phase = MissionPhase.DELIVERY
        self._phase_complete = False

        delivery_components = _build_delivery_components(architecture_name, procurement_result)
        await workflow.execute_child_workflow(
            DeliveryWorkflow.run,
            DeliveryInput(
                mission_id=mission_id,
                components=delivery_components,
            ),
            id=delivery_workflow_id(mission_id),
            task_queue=ORCHESTRATION_QUEUE,
        )
        self._phase_complete = True
        self._progress_pct = 50.0

        # ── INTEGRATION ──────────────────────────────────────────────
        self._phase = MissionPhase.INTEGRATION
        self._phase_complete = False

        integration_steps = ESTES_INTEGRATION_STEPS if architecture_name == "estes" else []
        # Workflow ID for integration uses mission_id (single integration per mission)
        integration_wf_id = f"integration-{mission_id}"
        await workflow.execute_child_workflow(
            IntegrationWorkflow.run,
            IntegrationInput(
                mission_id=mission_id,
                facility_name="The Garage",
                facility_slug="the-garage",
                steps=integration_steps,
            ),
            id=integration_wf_id,
            task_queue=ORCHESTRATION_QUEUE,
        )
        self._phase_complete = True
        self._progress_pct = 75.0

        # ── LAUNCH READINESS ─────────────────────────────────────────
        self._phase = MissionPhase.LAUNCH_READINESS
        self._phase_complete = False

        await workflow.execute_child_workflow(
            LaunchReadinessWorkflow.run,
            LaunchReadinessInput(mission_id=mission_id),
            id=launch_readiness_workflow_id(mission_id),
            task_queue=ORCHESTRATION_QUEUE,
        )
        self._phase_complete = True
        self._progress_pct = 100.0

        # Mission complete
        self._status = "COMPLETED"
        self._phase = MissionPhase.COMPLETED

        await workflow.execute_activity(
            update_mission_status,
            UpdateMissionStatusInput(mission_id=mission_id, status="COMPLETED"),
            start_to_close_timeout=timedelta(seconds=10),
        )

        return f"Mission {self._name} completed"

    @workflow.signal
    async def advance_phase(self) -> None:
        """Signal that the current phase is complete. Move to next (admin/debug override)."""
        self._phase_complete = True

    @workflow.query
    def get_state(self) -> MissionState:
        """Query: current mission state."""
        return MissionState(
            mission_id=self._mission_id,
            name=self._name,
            phase=self._phase.value if isinstance(self._phase, MissionPhase) else self._phase,
            status=self._status,
            progress_pct=self._progress_pct,
        )
