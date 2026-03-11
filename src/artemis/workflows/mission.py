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
    MissionPhase,
    MissionState,
    TaskCompletionInput,
    mission_workflow_id,
    procurement_workflow_id,
)
from artemis.workflows.procurement import ComponentBid, ProcurementInput, ProcurementWorkflow

# Component name→type map for known architectures (workflow-safe, no DB)
ESTES_COMPONENTS = [
    ComponentBid("B-class solid motor", "propulsion"),
    ComponentBid("Plastic parachute", "recovery-systems"),
    ComponentBid("Rocket body tube", "structures"),
    ComponentBid("Fin set (x3)", "structures"),
    ComponentBid("Bottle of glue", "materials"),
]


@workflow.defn
class MissionWorkflow:
    """Top-level workflow orchestrating a single mission through all phases.

    Phases run sequentially: PROCUREMENT -> DELIVERY -> INTEGRATION -> LAUNCH_READINESS.
    Each phase is (will be) a child workflow. For now, phases advance via signals.
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

        # Run phases sequentially
        phases = [
            MissionPhase.PROCUREMENT,
            MissionPhase.DELIVERY,
            MissionPhase.INTEGRATION,
            MissionPhase.LAUNCH_READINESS,
        ]

        for phase in phases:
            self._phase = phase
            self._phase_complete = False

            if phase == MissionPhase.PROCUREMENT:
                # Launch ProcurementWorkflow as child
                components = ESTES_COMPONENTS if architecture_name == "estes" else []
                await workflow.execute_child_workflow(
                    ProcurementWorkflow.run,
                    ProcurementInput(
                        mission_id=mission_id,
                        components=components,
                    ),
                    id=procurement_workflow_id(mission_id),
                    task_queue=ORCHESTRATION_QUEUE,
                )
                self._phase_complete = True
            else:
                # Other phases: wait for manual signal
                await workflow.wait_condition(lambda: self._phase_complete)

            # Update progress
            phase_idx = phases.index(phase)
            self._progress_pct = ((phase_idx + 1) / len(phases)) * 100.0

        # Mission complete
        self._status = "COMPLETED"
        self._phase = MissionPhase.COMPLETED
        self._progress_pct = 100.0

        await workflow.execute_activity(
            update_mission_status,
            UpdateMissionStatusInput(mission_id=mission_id, status="COMPLETED"),
            start_to_close_timeout=timedelta(seconds=10),
        )

        return f"Mission {self._name} completed"

    @workflow.signal
    async def advance_phase(self) -> None:
        """Signal that the current phase is complete. Move to next."""
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
