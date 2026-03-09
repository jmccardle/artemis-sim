"""IntegrationWorkflow — handles assembly and integration phase.

Child of MissionWorkflow. Requests facility, runs integration steps,
handles pass/fail on automated tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from artemis.activities.persistence import (
        GetTasksByPhaseInput,
        UpdateTaskStatusInput,
        get_tasks_by_phase,
        update_task_status,
    )
    from artemis.activities.simulation import (
        RunInspectionInput,
        RunInspectionResult,
        run_inspection,
    )

from artemis.workflows.clock import AdvanceTimeInput, CLOCK_WORKFLOW_ID
from artemis.workflows.facility_manager import (
    FACILITY_RESERVED_SIGNAL,
    RELEASE_FACILITY_SIGNAL,
    RESERVE_FACILITY_SIGNAL,
    FacilityReservationRequest,
    FacilityReservationResponse,
    FacilityReleaseInput,
)
from artemis.workflows.data_types import (
    ORCHESTRATION_QUEUE,
    IntegrationStepSpec,
    facility_workflow_id,
    integration_workflow_id,
)


@dataclass
class IntegrationInput:
    mission_id: str
    facility_name: str  # e.g., "The Garage"
    facility_slug: str  # e.g., "the-garage"
    steps: list[IntegrationStepSpec] = field(default_factory=list)


@dataclass
class IntegrationOutput:
    success: bool
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str = ""
    failure_reason: str = ""


@workflow.defn
class IntegrationWorkflow:
    """Handles the integration phase for a mission.

    1. Request facility reservation
    2. Wait for facility granted signal
    3. Run integration steps (user tasks + automated inspections)
    4. Release facility
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._facility_slug: str = ""
        self._facility_granted: bool = False
        self._current_step: str = ""
        self._completed_steps: list[str] = []
        self._step_completion_signals: dict[str, bool] = {}
        self._failed: bool = False
        self._failure_reason: str = ""

    @workflow.run
    async def run(self, input: IntegrationInput) -> IntegrationOutput:
        self._mission_id = input.mission_id
        self._facility_slug = input.facility_slug
        wf_id = workflow.info().workflow_id

        # Step 1: Request facility reservation
        facility_handle = workflow.get_external_workflow_handle(
            facility_workflow_id(input.facility_slug)
        )
        await facility_handle.signal(
            RESERVE_FACILITY_SIGNAL,
            FacilityReservationRequest(
                requesting_workflow_id=wf_id,
                mission_id=input.mission_id,
                purpose="Integration",
            ),
        )

        # Step 2: Wait for facility granted
        await workflow.wait_condition(lambda: self._facility_granted)

        # Get integration tasks from DB
        tasks = await workflow.execute_activity(
            get_tasks_by_phase,
            GetTasksByPhaseInput(mission_id=input.mission_id, phase="INTEGRATION"),
            start_to_close_timeout=timedelta(seconds=10),
        )
        task_map = {t.name: t for t in tasks}

        # Step 3: Run each integration step
        for step in input.steps:
            self._current_step = step.name

            # Find the USER task for this step (e.g., "Glue fins to body tube")
            # The step name should match a task name
            if step.name in task_map:
                task = task_map[step.name]

                # Mark task as in-progress
                await workflow.execute_activity(
                    update_task_status,
                    UpdateTaskStatusInput(task_id=task.task_id, status="IN_PROGRESS"),
                    start_to_close_timeout=timedelta(seconds=10),
                )

                # For USER tasks, wait for completion signal
                if task.task_type == "USER":
                    self._step_completion_signals[step.name] = False
                    await workflow.wait_condition(
                        lambda step_name=step.name: self._step_completion_signals.get(step_name, False)
                    )

                # Mark task complete
                await workflow.execute_activity(
                    update_task_status,
                    UpdateTaskStatusInput(task_id=task.task_id, status="COMPLETED"),
                    start_to_close_timeout=timedelta(seconds=10),
                )

                # Advance clock
                clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
                await clock_handle.signal(
                    "advance_time",
                    AdvanceTimeInput(
                        seconds=step.nominal_duration_seconds,
                        reason=f"Completed: {step.name}",
                    ),
                )

            # Check for associated automated inspection task
            # Convention: inspection tasks follow the step they inspect
            inspection_names = [
                t.name for t in tasks
                if t.task_type == "AUTOMATED" and t.name not in self._completed_steps
                and any(p_name in [step.name, f"Inspect {step.name}"]
                       for p_name in [])  # Will be matched below
            ]

            # Find inspection tasks whose prerequisites include this step
            for t in tasks:
                if (t.task_type == "AUTOMATED"
                    and t.name not in self._completed_steps
                    and step.name in task_map
                    and str(task_map[step.name].task_id) in t.prerequisites):

                    # Run automated inspection
                    await workflow.execute_activity(
                        update_task_status,
                        UpdateTaskStatusInput(task_id=t.task_id, status="IN_PROGRESS"),
                        start_to_close_timeout=timedelta(seconds=10),
                    )

                    result = await workflow.execute_activity(
                        run_inspection,
                        RunInspectionInput(
                            task_id=t.task_id,
                            task_name=t.name,
                            failure_probability=t.failure_probability,
                        ),
                        start_to_close_timeout=timedelta(seconds=10),
                    )

                    if result.passed:
                        await workflow.execute_activity(
                            update_task_status,
                            UpdateTaskStatusInput(task_id=t.task_id, status="COMPLETED"),
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        self._completed_steps.append(t.name)
                    else:
                        await workflow.execute_activity(
                            update_task_status,
                            UpdateTaskStatusInput(task_id=t.task_id, status="FAILED"),
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        self._failed = True
                        self._failure_reason = result.details

                        # Release facility and return failure
                        await facility_handle.signal(
                            RELEASE_FACILITY_SIGNAL,
                            FacilityReleaseInput(workflow_id=wf_id),
                        )
                        return IntegrationOutput(
                            success=False,
                            completed_steps=self._completed_steps,
                            failed_step=t.name,
                            failure_reason=result.details,
                        )

                    # Advance clock for inspection
                    clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
                    await clock_handle.signal(
                        "advance_time",
                        AdvanceTimeInput(
                            seconds=t.nominal_duration_seconds,
                            reason=f"Completed: {t.name}",
                        ),
                    )

            self._completed_steps.append(step.name)

        # Step 4: Release facility
        await facility_handle.signal(
            RELEASE_FACILITY_SIGNAL,
            FacilityReleaseInput(workflow_id=wf_id),
        )

        return IntegrationOutput(
            success=True,
            completed_steps=self._completed_steps,
        )

    @workflow.signal(name=FACILITY_RESERVED_SIGNAL)
    async def facility_reserved(self, response: FacilityReservationResponse) -> None:
        """Signal: facility reservation granted."""
        if response.granted:
            self._facility_granted = True

    @workflow.signal
    async def complete_step(self, step_name: str) -> None:
        """Signal: user completed an integration step."""
        self._step_completion_signals[step_name] = True

    @workflow.query
    def get_integration_state(self) -> dict:
        return {
            "mission_id": self._mission_id,
            "current_step": self._current_step,
            "completed_steps": self._completed_steps,
            "facility_granted": self._facility_granted,
            "failed": self._failed,
        }
