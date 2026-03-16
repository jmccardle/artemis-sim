"""DeliveryWorkflow + TransportWorkflow — handles mission delivery phase.

DeliveryWorkflow: child of MissionWorkflow, one per mission.
TransportWorkflow: child of DeliveryWorkflow, one per component.
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
        get_tasks_by_phase,
        update_task_status,
    )
    from artemis.activities.simulation import (
        RunInspectionInput,
        RunInspectionResult,
        run_inspection,
    )

from artemis.workflows.data_types import (
    ORCHESTRATION_QUEUE,
    CompleteTaskAndResolveInput,
    ComponentDeliveryUpdate,
    DeliveryResult,
    delivery_workflow_id,
    transport_workflow_id,
)
from artemis.workflows.clock import AdvanceTimeInput, CLOCK_WORKFLOW_ID


# ── DeliveryWorkflow ─────────────────────────────────────────────────

@dataclass
class DeliveryInput:
    mission_id: str
    components: list[DeliveryComponentInfo] = field(default_factory=list)


@dataclass
class DeliveryComponentInfo:
    name: str
    component_type: str
    contractor_slug: str
    transport_method: str
    origin: str
    destination: str
    nominal_duration_seconds: int = 7200


@workflow.defn
class DeliveryWorkflow:
    """Orchestrates delivery of all components for a mission.

    Starts one TransportWorkflow per component, waits for all to complete.
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._completed: int = 0
        self._total: int = 0
        self._results: dict[str, bool] = {}

    @workflow.run
    async def run(self, input: DeliveryInput) -> DeliveryResult:
        self._mission_id = input.mission_id
        self._total = len(input.components)

        # Start transport workflows for all components
        handles = []
        for comp in input.components:
            handle = await workflow.start_child_workflow(
                TransportWorkflow.run,
                TransportInput(
                    mission_id=input.mission_id,
                    component_name=comp.name,
                    contractor_slug=comp.contractor_slug,
                    nominal_duration_seconds=comp.nominal_duration_seconds,
                ),
                id=transport_workflow_id(input.mission_id, comp.name),
                task_queue=ORCHESTRATION_QUEUE,
            )
            handles.append((comp.name, handle))

        # Wait for all transports to complete
        for comp_name, handle in handles:
            result: TransportResult = await handle
            self._results[comp_name] = result.inspection_passed
            self._completed += 1

        return DeliveryResult(delivered=self._results)

    @workflow.query
    def get_progress(self) -> str:
        return f"{self._completed}/{self._total} components delivered"


# ── TransportWorkflow ────────────────────────────────────────────────

@dataclass
class TransportInput:
    mission_id: str
    component_name: str
    contractor_slug: str
    nominal_duration_seconds: int = 7200


@dataclass
class TransportResult:
    component_name: str
    received: bool = False
    inspection_passed: bool = False


@workflow.defn
class TransportWorkflow:
    """Handles delivery of a single component.

    1. Mark as shipped (simulated)
    2. Wait for component_received signal (from EGS ground ops)
    3. Run receiving inspection (automated)
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._component_name: str = ""
        self._shipped: bool = False
        self._received: bool = False
        self._inspected: bool = False
        self._inspection_passed: bool = False

    @workflow.run
    async def run(self, input: TransportInput) -> TransportResult:
        self._mission_id = input.mission_id
        self._component_name = input.component_name

        # Step 1: Ship component (simulated — auto-complete)
        self._shipped = True

        # Find and update the "Ship" task
        tasks = await workflow.execute_activity(
            get_tasks_by_phase,
            GetTasksByPhaseInput(mission_id=input.mission_id, phase="DELIVERY"),
            start_to_close_timeout=timedelta(seconds=10),
        )
        for task in tasks:
            if task.name == f"Ship {input.component_name}":
                await workflow.execute_activity(
                    complete_task_and_resolve,
                    CompleteTaskAndResolveInput(
                        task_id=task.task_id, mission_id=input.mission_id,
                    ),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                # Advance clock for shipping duration
                clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
                await clock_handle.signal(
                    "advance_time",
                    AdvanceTimeInput(
                        seconds=input.nominal_duration_seconds,
                        reason=f"Shipped {input.component_name}",
                    ),
                )
                break

        # Step 2: Wait for component received signal
        await workflow.wait_condition(lambda: self._received)

        # Update receive task
        for task in tasks:
            if task.name == f"Receive {input.component_name} at The Garage":
                await workflow.execute_activity(
                    complete_task_and_resolve,
                    CompleteTaskAndResolveInput(
                        task_id=task.task_id, mission_id=input.mission_id,
                    ),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
                await clock_handle.signal(
                    "advance_time",
                    AdvanceTimeInput(seconds=1800, reason=f"Received {input.component_name}"),
                )
                break

        # Step 3: Run receiving inspection (automated)
        for task in tasks:
            if task.name == f"Inspect {input.component_name}":
                inspection = await workflow.execute_activity(
                    run_inspection,
                    RunInspectionInput(
                        task_id=task.task_id,
                        task_name=task.name,
                        failure_probability=task.failure_probability,
                    ),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                self._inspection_passed = inspection.passed

                if inspection.passed:
                    await workflow.execute_activity(
                        complete_task_and_resolve,
                        CompleteTaskAndResolveInput(
                            task_id=task.task_id, mission_id=input.mission_id,
                        ),
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                else:
                    await workflow.execute_activity(
                        update_task_status,
                        UpdateTaskStatusInput(task_id=task.task_id, status="FAILED"),
                        start_to_close_timeout=timedelta(seconds=10),
                    )

                clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
                await clock_handle.signal(
                    "advance_time",
                    AdvanceTimeInput(seconds=3600, reason=f"Inspected {input.component_name}"),
                )
                break

        self._inspected = True

        return TransportResult(
            component_name=input.component_name,
            received=self._received,
            inspection_passed=self._inspection_passed,
        )

    @workflow.signal
    async def component_received(self, update: ComponentDeliveryUpdate) -> None:
        """Signal: EGS ground ops confirms component received."""
        self._received = True

    @workflow.query
    def get_status(self) -> dict:
        return {
            "component": self._component_name,
            "shipped": self._shipped,
            "received": self._received,
            "inspected": self._inspected,
            "inspection_passed": self._inspection_passed,
        }
