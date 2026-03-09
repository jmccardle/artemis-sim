"""ProcurementWorkflow + RFPWorkflow — handles mission procurement phase.

ProcurementWorkflow: child of MissionWorkflow, one per mission.
RFPWorkflow: child of ProcurementWorkflow, one per component.
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
    from artemis.activities.llm import (
        GenerateRFPInput,
        GenerateProposalInput,
        EvaluateProposalInput,
        LLMActivityResult,
        generate_rfp,
        generate_proposal,
        evaluate_proposal,
    )

from artemis.workflows.data_types import (
    ORCHESTRATION_QUEUE,
    LLM_QUEUE,
    AwardDecision,
    ProposalSubmission,
    ProcurementResult,
    rfp_workflow_id,
    procurement_workflow_id,
)


# ── ProcurementWorkflow ─────────────────────────────────────────────

@dataclass
class ProcurementInput:
    mission_id: str
    component_types: list[str] = field(default_factory=list)


@workflow.defn
class ProcurementWorkflow:
    """Orchestrates procurement for all components in a mission.

    Starts one RFPWorkflow per component type, waits for all to complete.
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._awards: dict[str, str] = {}
        self._completed: int = 0
        self._total: int = 0

    @workflow.run
    async def run(self, input: ProcurementInput) -> ProcurementResult:
        self._mission_id = input.mission_id
        self._total = len(input.component_types)

        # Start one RFP child workflow per component type
        handles = []
        for comp_type in input.component_types:
            handle = await workflow.start_child_workflow(
                RFPWorkflow.run,
                RFPInput(
                    mission_id=input.mission_id,
                    component_type=comp_type,
                ),
                id=rfp_workflow_id(input.mission_id, comp_type),
                task_queue=ORCHESTRATION_QUEUE,
            )
            handles.append((comp_type, handle))

        # Wait for all RFPs to complete
        for comp_type, handle in handles:
            result: RFPResult = await handle
            self._awards[comp_type] = result.winning_contractor_slug
            self._completed += 1

        return ProcurementResult(awards=self._awards)

    @workflow.query
    def get_progress(self) -> str:
        return f"{self._completed}/{self._total} components awarded"


# ── RFPWorkflow ──────────────────────────────────────────────────────

@dataclass
class RFPInput:
    mission_id: str
    component_type: str


@dataclass
class RFPResult:
    component_type: str
    winning_contractor_slug: str


@workflow.defn
class RFPWorkflow:
    """Handles the RFP cycle for a single component type.

    1. Generate RFP text (LLM activity)
    2. Generate contractor proposal (LLM activity, simulating contractor)
    3. Evaluate proposal (LLM activity, simulating NASA review)
    4. Wait for award decision (signal from user)
    5. Return winning contractor
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._component_type: str = ""
        self._rfp_text: str = ""
        self._proposal_text: str = ""
        self._evaluation_text: str = ""
        self._award: AwardDecision | None = None
        self._proposal: ProposalSubmission | None = None

    @workflow.run
    async def run(self, input: RFPInput) -> RFPResult:
        self._mission_id = input.mission_id
        self._component_type = input.component_type

        # Step 1: Generate RFP (LLM or stub)
        rfp_result = await workflow.execute_activity(
            generate_rfp,
            GenerateRFPInput(
                mission_id=input.mission_id,
                component_name=input.component_type,
                component_type=input.component_type,
            ),
            start_to_close_timeout=timedelta(seconds=60),
            task_queue=LLM_QUEUE,
        )
        self._rfp_text = rfp_result.content

        # Update task status: RFP issued
        tasks = await workflow.execute_activity(
            get_tasks_by_phase,
            GetTasksByPhaseInput(
                mission_id=input.mission_id,
                phase="PROCUREMENT",
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )
        for task in tasks:
            if task.name.startswith("Issue RFP") and input.component_type in task.name.lower():
                await workflow.execute_activity(
                    update_task_status,
                    UpdateTaskStatusInput(task_id=task.task_id, status="COMPLETED"),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                break

        # Step 2: Wait for proposal (signal or auto-generate)
        # Auto-generate a proposal via LLM to simulate contractor
        proposal_result = await workflow.execute_activity(
            generate_proposal,
            GenerateProposalInput(
                rfp_text=self._rfp_text,
                contractor_slug="auto",
                contractor_name="Auto-assigned",
                contractor_profile="Generic contractor",
                contractor_reliability=0.85,
                contractor_cost_factor=1.0,
            ),
            start_to_close_timeout=timedelta(seconds=60),
            task_queue=LLM_QUEUE,
        )
        self._proposal_text = proposal_result.content

        # Update task status: proposal submitted
        for task in tasks:
            if task.name.startswith("Submit proposal") and input.component_type in task.name.lower():
                await workflow.execute_activity(
                    update_task_status,
                    UpdateTaskStatusInput(task_id=task.task_id, status="COMPLETED"),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                break

        # Step 3: Evaluate proposal (LLM)
        eval_result = await workflow.execute_activity(
            evaluate_proposal,
            EvaluateProposalInput(
                rfp_text=self._rfp_text,
                proposal_text=self._proposal_text,
                contractor_name="Auto-assigned",
            ),
            start_to_close_timeout=timedelta(seconds=60),
            task_queue=LLM_QUEUE,
        )
        self._evaluation_text = eval_result.content

        # Update task status: evaluation complete
        for task in tasks:
            if task.name.startswith("Evaluate") and input.component_type in task.name.lower():
                await workflow.execute_activity(
                    update_task_status,
                    UpdateTaskStatusInput(task_id=task.task_id, status="COMPLETED"),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                break

        # Step 4: Wait for award decision (signal from user)
        await workflow.wait_condition(lambda: self._award is not None)

        # Update task status: contract awarded
        for task in tasks:
            if task.name.startswith("Award contract") and input.component_type in task.name.lower():
                await workflow.execute_activity(
                    update_task_status,
                    UpdateTaskStatusInput(task_id=task.task_id, status="COMPLETED"),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                break

        return RFPResult(
            component_type=input.component_type,
            winning_contractor_slug=self._award.winning_contractor_slug,
        )

    @workflow.signal
    async def submit_proposal(self, proposal: ProposalSubmission) -> None:
        """Signal: contractor submits a proposal (alternative to auto-generation)."""
        self._proposal = proposal

    @workflow.signal
    async def award_contract(self, decision: AwardDecision) -> None:
        """Signal: NASA awards the contract to a contractor."""
        self._award = decision

    @workflow.query
    def get_rfp_state(self) -> dict:
        return {
            "component_type": self._component_type,
            "has_rfp": bool(self._rfp_text),
            "has_proposal": bool(self._proposal_text),
            "has_evaluation": bool(self._evaluation_text),
            "awarded": self._award is not None,
        }
