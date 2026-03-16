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
        complete_task_and_resolve,
        get_contractors_by_specialty,
        get_tasks_by_phase,
        save_artifact,
    )
    from artemis.activities.llm import (
        generate_proposal,
        generate_rfp,
        generate_rubric,
        evaluate_proposal,
    )

from artemis.workflows.data_types import (
    ORCHESTRATION_QUEUE,
    LLM_QUEUE,
    AwardDecision,
    CompleteTaskAndResolveInput,
    ContractorInfo,
    EvaluateProposalInput,
    GenerateProposalInput,
    GenerateRFPInput,
    GenerateRubricInput,
    GetContractorsBySpecialtyInput,
    LLMResult,
    ProposalSubmission,
    ProcurementResult,
    SaveArtifactInput,
    rfp_workflow_id,
    procurement_workflow_id,
)


# ── ProcurementWorkflow ─────────────────────────────────────────────

@dataclass
class ComponentBid:
    """A component to procure: name (for tasks) + type (for LLM/NPR)."""
    component_name: str
    component_type: str


@dataclass
class ProcurementInput:
    mission_id: str
    components: list[ComponentBid] = field(default_factory=list)
    # Backward compat — ignored if components is provided
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

        # Build component list from either new format or legacy component_types
        components = input.components
        if not components and input.component_types:
            components = [ComponentBid(ct, ct) for ct in input.component_types]

        self._total = len(components)

        # Fetch eligible contractors per component type
        contractors_by_type: dict[str, list[ContractorInfo]] = {}
        seen_types: set[str] = set()
        for comp in components:
            if comp.component_type not in seen_types:
                seen_types.add(comp.component_type)
                contractors = await workflow.execute_activity(
                    get_contractors_by_specialty,
                    GetContractorsBySpecialtyInput(specialty=comp.component_type),
                    start_to_close_timeout=timedelta(seconds=10),
                )
                contractors_by_type[comp.component_type] = contractors

        # Start one RFP child workflow per component
        handles = []
        for comp in components:
            # Use component name slug for unique workflow ID
            comp_slug = comp.component_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
            handle = await workflow.start_child_workflow(
                RFPWorkflow.run,
                RFPInput(
                    mission_id=input.mission_id,
                    component_name=comp.component_name,
                    component_type=comp.component_type,
                    eligible_contractors=contractors_by_type.get(comp.component_type, []),
                ),
                id=rfp_workflow_id(input.mission_id, comp_slug),
                task_queue=ORCHESTRATION_QUEUE,
            )
            handles.append((comp.component_name, handle))

        # Wait for all RFPs to complete
        for comp_name, handle in handles:
            result: RFPResult = await handle
            self._awards[comp_name] = result.winning_contractor_slug
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
    component_name: str = ""  # human-readable name used in task matching
    eligible_contractors: list[ContractorInfo] = field(default_factory=list)


@dataclass
class RFPResult:
    component_type: str
    winning_contractor_slug: str


@workflow.defn
class RFPWorkflow:
    """Handles the RFP cycle for a single component type.

    1. Generate RFP text (LLM activity)
    2. Generate evaluation rubric (LLM activity)
    3. Generate contractor proposal (LLM activity, simulating contractor)
    4. Evaluate proposal with rubric (LLM activity, simulating NASA review)
    5. Wait for award decision (signal from user)
    6. Return winning contractor
    """

    def __init__(self) -> None:
        self._mission_id: str = ""
        self._component_type: str = ""
        self._rfp_text: str = ""
        self._rubric_json: str = ""
        self._proposal_text: str = ""
        self._evaluation_text: str = ""
        self._award: AwardDecision | None = None
        self._proposal: ProposalSubmission | None = None

    @workflow.run
    async def run(self, input: RFPInput) -> RFPResult:
        self._mission_id = input.mission_id
        self._component_type = input.component_type
        comp_name = input.component_name or input.component_type

        # Get procurement tasks for this mission
        tasks = await workflow.execute_activity(
            get_tasks_by_phase,
            GetTasksByPhaseInput(
                mission_id=input.mission_id,
                phase="PROCUREMENT",
            ),
            start_to_close_timeout=timedelta(seconds=10),
        )

        def _find_task(prefix: str) -> object | None:
            for t in tasks:
                if t.name.startswith(prefix) and comp_name.lower() in t.name.lower():
                    return t
            return None

        # ── Step 1: Generate RFP (LLM) ──
        rfp_result: LLMResult = await workflow.execute_activity(
            generate_rfp,
            GenerateRFPInput(
                mission_id=input.mission_id,
                component_name=comp_name,
                component_type=input.component_type,
            ),
            start_to_close_timeout=timedelta(seconds=600),
            task_queue=LLM_QUEUE,
        )
        self._rfp_text = rfp_result.content

        # Save RFP artifact
        rfp_task = _find_task("Issue RFP")
        if rfp_task:
            await workflow.execute_activity(
                save_artifact,
                SaveArtifactInput(
                    task_id=rfp_task.task_id,
                    artifact_type="RFP",
                    content={"text": rfp_result.content},
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                complete_task_and_resolve,
                CompleteTaskAndResolveInput(
                    task_id=rfp_task.task_id, mission_id=input.mission_id,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

        # ── Step 2: Generate evaluation rubric (LLM) ──
        rubric_result: LLMResult = await workflow.execute_activity(
            generate_rubric,
            GenerateRubricInput(
                rfp_text=self._rfp_text,
                component_type=input.component_type,
            ),
            start_to_close_timeout=timedelta(seconds=600),
            task_queue=LLM_QUEUE,
        )
        self._rubric_json = rubric_result.content

        # Save rubric artifact on the RFP task (it's a sub-product of RFP issuance)
        if rfp_task:
            await workflow.execute_activity(
                save_artifact,
                SaveArtifactInput(
                    task_id=rfp_task.task_id,
                    artifact_type="RUBRIC",
                    content={"rubric": rubric_result.content, "format": "json"},
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

        # ── Step 3: Generate contractor proposal (LLM, simulating contractor) ──
        # Pick the first eligible contractor, or use a default
        if input.eligible_contractors:
            contractor = input.eligible_contractors[0]
        else:
            contractor = ContractorInfo(
                slug="auto",
                name="Auto-assigned",
                profile="Generic contractor",
                reliability=0.85,
                cost_factor=1.0,
            )

        proposal_result: LLMResult = await workflow.execute_activity(
            generate_proposal,
            GenerateProposalInput(
                rfp_text=self._rfp_text,
                contractor_slug=contractor.slug,
                contractor_name=contractor.name,
                contractor_profile=contractor.profile,
                contractor_reliability=contractor.reliability,
                contractor_cost_factor=contractor.cost_factor,
            ),
            start_to_close_timeout=timedelta(seconds=600),
            task_queue=LLM_QUEUE,
        )
        self._proposal_text = proposal_result.content

        # Save proposal artifact and update task status
        proposal_task = _find_task("Submit proposal")
        if proposal_task:
            await workflow.execute_activity(
                save_artifact,
                SaveArtifactInput(
                    task_id=proposal_task.task_id,
                    artifact_type="PROPOSAL",
                    content={
                        "text": proposal_result.content,
                        "contractor_slug": contractor.slug,
                        "contractor_name": contractor.name,
                    },
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                complete_task_and_resolve,
                CompleteTaskAndResolveInput(
                    task_id=proposal_task.task_id, mission_id=input.mission_id,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

        # ── Step 4: Evaluate proposal with rubric (LLM) ──
        eval_result: LLMResult = await workflow.execute_activity(
            evaluate_proposal,
            EvaluateProposalInput(
                rfp_text=self._rfp_text,
                proposal_text=self._proposal_text,
                contractor_name=contractor.name,
                rubric_json=self._rubric_json,
                component_type=input.component_type,
            ),
            start_to_close_timeout=timedelta(seconds=600),
            task_queue=LLM_QUEUE,
        )
        self._evaluation_text = eval_result.content

        # Save scorecard artifact and update task status
        eval_task = _find_task("Evaluate")
        if eval_task:
            await workflow.execute_activity(
                save_artifact,
                SaveArtifactInput(
                    task_id=eval_task.task_id,
                    artifact_type="SCORECARD",
                    content={"scorecard": eval_result.content, "format": "json"},
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                complete_task_and_resolve,
                CompleteTaskAndResolveInput(
                    task_id=eval_task.task_id, mission_id=input.mission_id,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

        # ── Step 5: Wait for award decision (signal from user) ──
        await workflow.wait_condition(lambda: self._award is not None)

        # Update task status: contract awarded
        award_task = _find_task("Award contract")
        if award_task:
            await workflow.execute_activity(
                complete_task_and_resolve,
                CompleteTaskAndResolveInput(
                    task_id=award_task.task_id, mission_id=input.mission_id,
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

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
            "has_rubric": bool(self._rubric_json),
            "has_proposal": bool(self._proposal_text),
            "has_evaluation": bool(self._evaluation_text),
            "awarded": self._award is not None,
        }
