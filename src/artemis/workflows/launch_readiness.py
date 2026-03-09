"""LaunchReadinessWorkflow — final phase before launch.

Waits for:
1. Final inspection review (NASA Technical Authority)
2. Launch readiness review (NASA Program Manager)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from artemis.activities.persistence import (
        GetTasksByPhaseInput,
        UpdateTaskStatusInput,
        get_tasks_by_phase,
        update_task_status,
    )

from artemis.workflows.clock import AdvanceTimeInput, CLOCK_WORKFLOW_ID
from artemis.workflows.data_types import ReviewDecision


@dataclass
class LaunchReadinessInput:
    mission_id: str


@dataclass
class LaunchReadinessOutput:
    approved: bool
    rejection_reason: str = ""


@workflow.defn
class LaunchReadinessWorkflow:
    """Final phase: waits for two sequential human reviews.

    1. Final inspection review (Tech Authority) — must approve before #2
    2. Launch readiness review (Program Manager) — final go/no-go
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._inspection_decision: ReviewDecision | None = None
        self._readiness_decision: ReviewDecision | None = None

    @workflow.run
    async def run(self, input: LaunchReadinessInput) -> LaunchReadinessOutput:
        self._mission_id = input.mission_id

        # Get launch readiness tasks
        tasks = await workflow.execute_activity(
            get_tasks_by_phase,
            GetTasksByPhaseInput(
                mission_id=input.mission_id,
                phase="LAUNCH_READINESS",
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )
        task_map = {t.name: t for t in tasks}

        # Step 1: Final inspection review (Tech Authority)
        inspection_task = task_map.get("Final inspection review")
        if inspection_task:
            await workflow.execute_activity(
                update_task_status,
                UpdateTaskStatusInput(
                    task_id=inspection_task.task_id,
                    status="AVAILABLE",
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

        # Wait for inspection decision
        await workflow.wait_condition(lambda: self._inspection_decision is not None)

        if inspection_task:
            status = "COMPLETED" if self._inspection_decision.approved else "FAILED"
            await workflow.execute_activity(
                update_task_status,
                UpdateTaskStatusInput(
                    task_id=inspection_task.task_id,
                    status=status,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )
            # Advance clock
            clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
            await clock_handle.signal(
                "advance_time",
                AdvanceTimeInput(seconds=3600, reason="Final inspection review"),
            )

        if not self._inspection_decision.approved:
            return LaunchReadinessOutput(
                approved=False,
                rejection_reason=self._inspection_decision.notes,
            )

        # Step 2: Launch readiness review (Program Manager)
        readiness_task = task_map.get("Launch readiness review")
        if readiness_task:
            await workflow.execute_activity(
                update_task_status,
                UpdateTaskStatusInput(
                    task_id=readiness_task.task_id,
                    status="AVAILABLE",
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

        # Wait for readiness decision
        await workflow.wait_condition(lambda: self._readiness_decision is not None)

        if readiness_task:
            status = "COMPLETED" if self._readiness_decision.approved else "FAILED"
            await workflow.execute_activity(
                update_task_status,
                UpdateTaskStatusInput(
                    task_id=readiness_task.task_id,
                    status=status,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )
            clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
            await clock_handle.signal(
                "advance_time",
                AdvanceTimeInput(seconds=1800, reason="Launch readiness review"),
            )

        return LaunchReadinessOutput(
            approved=self._readiness_decision.approved,
            rejection_reason="" if self._readiness_decision.approved else self._readiness_decision.notes,
        )

    @workflow.signal
    async def final_inspection_complete(self, decision: ReviewDecision) -> None:
        """Signal: Tech Authority submits inspection decision."""
        self._inspection_decision = decision

    @workflow.signal
    async def launch_readiness_review(self, decision: ReviewDecision) -> None:
        """Signal: Program Manager submits launch readiness decision."""
        self._readiness_decision = decision

    @workflow.query
    def get_readiness_state(self) -> dict:
        return {
            "mission_id": self._mission_id,
            "inspection_complete": self._inspection_decision is not None,
            "inspection_approved": self._inspection_decision.approved if self._inspection_decision else None,
            "readiness_complete": self._readiness_decision is not None,
            "readiness_approved": self._readiness_decision.approved if self._readiness_decision else None,
        }
