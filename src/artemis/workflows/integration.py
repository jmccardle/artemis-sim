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
        complete_task_and_resolve,
        create_rework_task,
        get_tasks_by_phase,
        save_artifact,
        send_escalation,
        update_task_status,
    )
    from artemis.activities.simulation import (
        RunInspectionInput,
        RunInspectionResult,
        run_inspection,
    )
    from artemis.activities.llm import generate_test_report
    from artemis.activities.external_systems import (
        create_ncr,
        run_preflight_check,
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
    LLM_QUEUE,
    SIMULATION_QUEUE,
    CompleteTaskAndResolveInput,
    CreateReworkTaskInput,
    EscalationNotice,
    GenerateTestReportInput,
    IntegrationStepSpec,
    LLMResult,
    SaveArtifactInput,
    facility_workflow_id,
    integration_workflow_id,
)
from artemis.workflows.adapter_types import (
    CreateNCRInput,
    PreflightCheckInput,
)


@dataclass
class IntegrationInput:
    mission_id: str
    facility_name: str = ""   # deprecated — use per-step facility instead
    facility_slug: str = ""   # deprecated — use per-step facility instead
    steps: list[IntegrationStepSpec] = field(default_factory=list)
    max_rework_attempts: int = 2


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
        self._current_step: str = ""
        self._completed_steps: list[str] = []
        self._step_completion_signals: dict[str, bool] = {}
        self._failed: bool = False
        self._failure_reason: str = ""
        # Per-step facility tracking: facility_slug → granted flag
        self._facility_grants: dict[str, bool] = {}
        self._current_facility: str = ""
        # Rework tracking: rework_task_id → completed flag
        self._completed_rework: dict[str, bool] = {}

    @workflow.run
    async def run(self, input: IntegrationInput) -> IntegrationOutput:
        self._mission_id = input.mission_id
        wf_id = workflow.info().workflow_id

        # Get integration tasks from DB
        tasks = await workflow.execute_activity(
            get_tasks_by_phase,
            GetTasksByPhaseInput(mission_id=input.mission_id, phase="INTEGRATION"),
            start_to_close_timeout=timedelta(seconds=10),
        )
        task_map = {t.name: t for t in tasks}

        # Determine the facility slug for each step.
        # Steps use their own IntegrationStepSpec.facility field.
        # Fall back to input.facility_slug for backwards compat (Estes).
        def _step_facility_slug(step: IntegrationStepSpec) -> str:
            if step.facility:
                return step.facility.lower().replace(" ", "-").replace("(", "").replace(")", "")
            return input.facility_slug

        # Track which facility is currently held so we can release-then-acquire
        # when consecutive steps use different facilities.
        held_facility_slug: str = ""

        for step in input.steps:
            self._current_step = step.name
            step_slug = _step_facility_slug(step)

            # ── Facility transition: release old, acquire new ──────────
            if step_slug and step_slug != held_facility_slug:
                # Release previous facility if we're holding one
                if held_facility_slug:
                    prev_handle = workflow.get_external_workflow_handle(
                        facility_workflow_id(held_facility_slug)
                    )
                    await prev_handle.signal(
                        RELEASE_FACILITY_SIGNAL,
                        FacilityReleaseInput(workflow_id=wf_id),
                    )
                    held_facility_slug = ""
                    self._current_facility = ""

                # Reserve the new facility
                new_handle = workflow.get_external_workflow_handle(
                    facility_workflow_id(step_slug)
                )
                self._facility_grants[step_slug] = False
                await new_handle.signal(
                    RESERVE_FACILITY_SIGNAL,
                    FacilityReservationRequest(
                        requesting_workflow_id=wf_id,
                        mission_id=input.mission_id,
                        purpose=step.name,
                    ),
                )
                await workflow.wait_condition(
                    lambda slug=step_slug: self._facility_grants.get(slug, False)
                )
                held_facility_slug = step_slug
                self._current_facility = step_slug

            # ── Preflight check (if step has requirements) ─────────────
            has_preflight = (
                step.required_certs or step.equipment_ids or step.part_numbers
            )
            if has_preflight:
                preflight = await workflow.execute_activity(
                    run_preflight_check,
                    PreflightCheckInput(
                        task_id=task_map[step.name].task_id if step.name in task_map else "",
                        task_name=step.name,
                        operator_id=f"OP-{step_slug.upper().split('-')[0]}-001" if step_slug else "OP-001",
                        facility_slug=step_slug,
                        equipment_ids=step.equipment_ids,
                        part_numbers=step.part_numbers,
                        required_certs=step.required_certs,
                        wbs_element=step.wbs_element,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    task_queue=SIMULATION_QUEUE,
                )
                # Save preflight report as artifact
                if step.name in task_map:
                    await workflow.execute_activity(
                        save_artifact,
                        SaveArtifactInput(
                            task_id=task_map[step.name].task_id,
                            artifact_type="PREFLIGHT_REPORT",
                            content={
                                "ready": preflight.ready,
                                "checks": [
                                    {"type": c.check_type, "system": c.system,
                                     "status": c.status, "detail": c.detail}
                                    for c in preflight.checks
                                ],
                                "blocking_reasons": preflight.blocking_reasons,
                                "wad_number": preflight.wad_number,
                            },
                        ),
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                if not preflight.ready:
                    # Escalate and continue (preflight failures are informational
                    # in the demo — the step proceeds but with a warning artifact)
                    await workflow.execute_activity(
                        send_escalation,
                        EscalationNotice(
                            task_id=task_map[step.name].task_id if step.name in task_map else "",
                            task_name=step.name,
                            mission_id=input.mission_id,
                            expected_seconds=0,
                            actual_seconds=0,
                            escalation_level="warning",
                            message=f"Preflight failed: {'; '.join(preflight.blocking_reasons)}",
                        ),
                        start_to_close_timeout=timedelta(seconds=10),
                    )

            # ── Execute the step ───────────────────────────────────────
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

                # Mark task complete and resolve downstream prerequisites
                await workflow.execute_activity(
                    complete_task_and_resolve,
                    CompleteTaskAndResolveInput(
                        task_id=task.task_id, mission_id=input.mission_id,
                    ),
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

            # ── Run associated automated inspections (with rework loop) ─
            for t in tasks:
                if (t.task_type == "AUTOMATED"
                    and t.name not in self._completed_steps
                    and step.name in task_map
                    and str(task_map[step.name].task_id) in t.prerequisites):

                    inspection_passed = False

                    for attempt in range(input.max_rework_attempts + 1):
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

                        # Generate LLM test report
                        report_result: LLMResult = await workflow.execute_activity(
                            generate_test_report,
                            GenerateTestReportInput(
                                test_name=t.name,
                                passed=result.passed,
                                component_name=step.name,
                                details=result.details,
                                component_type="structures",
                            ),
                            start_to_close_timeout=timedelta(seconds=600),
                            task_queue=LLM_QUEUE,
                        )

                        # Save test report artifact
                        report_artifact_type = "TEST_REPORT" if result.passed else "FAILURE_REPORT"
                        await workflow.execute_activity(
                            save_artifact,
                            SaveArtifactInput(
                                task_id=t.task_id,
                                artifact_type=report_artifact_type,
                                content={"text": report_result.content},
                            ),
                            start_to_close_timeout=timedelta(seconds=10),
                        )

                        if result.passed:
                            await workflow.execute_activity(
                                complete_task_and_resolve,
                                CompleteTaskAndResolveInput(
                                    task_id=t.task_id, mission_id=input.mission_id,
                                ),
                                start_to_close_timeout=timedelta(seconds=10),
                            )
                            self._completed_steps.append(t.name)
                            inspection_passed = True
                            break

                        # ── Inspection failed — attempt rework ─────────
                        await workflow.execute_activity(
                            update_task_status,
                            UpdateTaskStatusInput(task_id=t.task_id, status="FAILED"),
                            start_to_close_timeout=timedelta(seconds=10),
                        )

                        # Create NCR via QMS
                        await workflow.execute_activity(
                            create_ncr,
                            CreateNCRInput(
                                task_id=t.task_id,
                                description=result.details,
                                severity="major",
                            ),
                            start_to_close_timeout=timedelta(seconds=10),
                            task_queue=SIMULATION_QUEUE,
                        )

                        if attempt < input.max_rework_attempts:
                            # Create rework task and wait for completion
                            rework_result = await workflow.execute_activity(
                                create_rework_task,
                                CreateReworkTaskInput(
                                    original_task_id=t.task_id,
                                    mission_id=input.mission_id,
                                    reason=result.details,
                                ),
                                start_to_close_timeout=timedelta(seconds=10),
                            )

                            # Wait for rework completion signal
                            rework_id = rework_result.new_task_id
                            self._completed_rework[rework_id] = False
                            await workflow.wait_condition(
                                lambda rid=rework_id: self._completed_rework.get(rid, False)
                            )

                            # Advance clock for rework duration
                            clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
                            await clock_handle.signal(
                                "advance_time",
                                AdvanceTimeInput(
                                    seconds=t.nominal_duration_seconds,
                                    reason=f"Rework completed: {rework_result.new_task_name}",
                                ),
                            )

                    if not inspection_passed:
                        # All rework attempts exhausted
                        self._failed = True
                        self._failure_reason = f"{t.name} failed after {input.max_rework_attempts} rework attempts"

                        # Release held facility and return failure
                        if held_facility_slug:
                            fail_handle = workflow.get_external_workflow_handle(
                                facility_workflow_id(held_facility_slug)
                            )
                            await fail_handle.signal(
                                RELEASE_FACILITY_SIGNAL,
                                FacilityReleaseInput(workflow_id=wf_id),
                            )
                        return IntegrationOutput(
                            success=False,
                            completed_steps=self._completed_steps,
                            failed_step=t.name,
                            failure_reason=self._failure_reason,
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

        # Release final facility
        if held_facility_slug:
            final_handle = workflow.get_external_workflow_handle(
                facility_workflow_id(held_facility_slug)
            )
            await final_handle.signal(
                RELEASE_FACILITY_SIGNAL,
                FacilityReleaseInput(workflow_id=wf_id),
            )

        return IntegrationOutput(
            success=True,
            completed_steps=self._completed_steps,
        )

    @workflow.signal(name=FACILITY_RESERVED_SIGNAL)
    async def facility_reserved(self, response: FacilityReservationResponse) -> None:
        """Signal: facility reservation granted (keyed by slug)."""
        if response.granted:
            self._facility_grants[response.facility_slug] = True

    @workflow.signal
    async def complete_step(self, step_name: str) -> None:
        """Signal: user completed an integration step."""
        self._step_completion_signals[step_name] = True

    @workflow.signal
    async def complete_rework(self, rework_task_id: str) -> None:
        """Signal: rework task has been completed."""
        self._completed_rework[rework_task_id] = True

    @workflow.query
    def get_integration_state(self) -> dict:
        return {
            "mission_id": self._mission_id,
            "current_step": self._current_step,
            "completed_steps": self._completed_steps,
            "current_facility": self._current_facility,
            "failed": self._failed,
        }
