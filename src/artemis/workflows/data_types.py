"""Shared data types for Temporal workflow communication.

All types are serializable dataclasses — safe to import in workflow code.
No database or I/O imports allowed.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field


# ── Task Queue Constants ────────────────────────────────────────────

ORCHESTRATION_QUEUE = "artemis-orchestration"
LLM_QUEUE = "artemis-llm"
SIMULATION_QUEUE = "artemis-simulation"
NOTIFICATION_QUEUE = "artemis-notifications"


# ── Workflow ID Helpers ─────────────────────────────────────────────

CLOCK_WORKFLOW_ID = "clock-global"


def mission_workflow_id(mission_id: str) -> str:
    return f"mission-{mission_id}"


def facility_workflow_id(facility_slug: str) -> str:
    return f"facility-{facility_slug}"


def procurement_workflow_id(mission_id: str) -> str:
    return f"procurement-{mission_id}"


def rfp_workflow_id(mission_id: str, component_type: str) -> str:
    return f"rfp-{mission_id}-{component_type}"


def delivery_workflow_id(mission_id: str) -> str:
    return f"delivery-{mission_id}"


def transport_workflow_id(mission_id: str, component_name: str) -> str:
    slug = component_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
    return f"transport-{mission_id}-{slug}"


def integration_workflow_id(mission_id: str, step_name: str) -> str:
    slug = step_name.lower().replace(" ", "-")
    return f"integration-{mission_id}-{slug}"


def launch_readiness_workflow_id(mission_id: str) -> str:
    return f"launch-readiness-{mission_id}"


# ── Enums (workflow-safe, no DB dependency) ─────────────────────────

class MissionPhase(str, enum.Enum):
    PROCUREMENT = "PROCUREMENT"
    DELIVERY = "DELIVERY"
    INTEGRATION = "INTEGRATION"
    LAUNCH_READINESS = "LAUNCH_READINESS"
    COMPLETED = "COMPLETED"


class TaskStatusW(str, enum.Enum):
    """Workflow-safe copy of TaskStatus (avoids importing DB models)."""
    NOT_READY = "NOT_READY"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REWORK = "REWORK"


class TaskTypeW(str, enum.Enum):
    """Workflow-safe copy of TaskType."""
    AUTOMATED = "AUTOMATED"
    SIMULATED = "SIMULATED"
    USER = "USER"
    AGENT = "AGENT"


# ── Component / Architecture ────────────────────────────────────────

@dataclass
class ComponentSpec:
    """Definition of a mission component."""
    name: str
    component_type: str  # bidding category: "propulsion", "structures", etc.
    transport_method: str
    transport_origin: str
    transport_destination: str
    nominal_delivery_seconds: int = 7200


@dataclass
class IntegrationStepSpec:
    """Definition of an integration step."""
    name: str
    components_required: list[str] = field(default_factory=list)
    facility: str = ""
    nominal_duration_seconds: int = 0
    failure_probability: float = 0.0
    output_component: str = ""
    # Preflight check requirements (optional — empty = no preflight)
    required_certs: list[str] = field(default_factory=list)
    equipment_ids: list[str] = field(default_factory=list)
    part_numbers: list[str] = field(default_factory=list)
    wbs_element: str = ""


@dataclass
class MissionArchitecture:
    """Complete mission architecture definition."""
    name: str
    display_name: str = ""
    components: list[ComponentSpec] = field(default_factory=list)
    integration_steps: list[IntegrationStepSpec] = field(default_factory=list)
    primary_facility: str = "The Garage"


# ── Clock ───────────────────────────────────────────────────────────

@dataclass
class AdvanceTimeInput:
    """Signal payload for advancing the simulated clock."""
    seconds: int
    reason: str


@dataclass
class ClockState:
    """Query response for current clock state."""
    current_time_iso: str


# ── Facility ────────────────────────────────────────────────────────

@dataclass
class FacilityReservationRequest:
    """Signal payload requesting a facility reservation."""
    requesting_workflow_id: str
    mission_id: str
    purpose: str


@dataclass
class FacilityReservationResponse:
    """Signal payload granting/denying a facility reservation."""
    granted: bool
    facility_slug: str
    message: str = ""


@dataclass
class FacilityReleaseInput:
    """Signal payload releasing a facility reservation."""
    workflow_id: str


@dataclass
class FacilityStatus:
    """Query response for facility state."""
    slug: str
    name: str
    capacity: int
    current_occupancy: int
    queue_depth: int
    occupants: list[str] = field(default_factory=list)


# ── Task Signals ────────────────────────────────────────────────────

@dataclass
class TaskCompletionInput:
    """Signal payload for completing or failing a task."""
    task_name: str
    outcome: str  # "success" or "failure"
    details: str = ""


# ── Procurement ─────────────────────────────────────────────────────

@dataclass
class ProposalSubmission:
    """Signal payload: contractor submitting a proposal."""
    contractor_slug: str
    proposal_content: str


@dataclass
class AwardDecision:
    """Signal payload: NASA awarding a contract."""
    component_type: str
    winning_contractor_slug: str
    reason: str = ""


@dataclass
class ProcurementResult:
    """Result of procurement phase: component→contractor mapping."""
    awards: dict[str, str] = field(default_factory=dict)


# ── Delivery ────────────────────────────────────────────────────────

@dataclass
class ComponentDeliveryUpdate:
    """Signal payload for delivery status updates."""
    component_name: str
    shipped: bool = False
    received: bool = False
    inspection_passed: bool = False


@dataclass
class DeliveryResult:
    """Result of delivery phase: component→received mapping."""
    delivered: dict[str, bool] = field(default_factory=dict)


# ── Integration ─────────────────────────────────────────────────────

@dataclass
class IntegrationInput:
    """Input for an integration step."""
    mission_id: str
    step_name: str
    components_required: list[str] = field(default_factory=list)
    facility: str = ""
    nominal_duration_seconds: int = 0
    failure_probability: float = 0.0
    output_component: str = ""


@dataclass
class IntegrationResult:
    """Result of an integration step."""
    step_name: str
    success: bool
    output_component: str = ""
    failure_reason: str = ""


# ── Launch Readiness ────────────────────────────────────────────────

@dataclass
class ReviewDecision:
    """Signal payload for inspection/launch readiness review."""
    reviewer_role: str
    approved: bool
    notes: str = ""


# ── Mission State (query response) ─────────────────────────────────

@dataclass
class MissionState:
    """Query response for overall mission state."""
    mission_id: str
    name: str
    phase: str
    status: str
    progress_pct: float = 0.0


# ── Persistence Activity Types ──────────────────────────────────────

@dataclass
class CreateMissionTasksInput:
    mission_id: str
    architecture_name: str


@dataclass
class UpdateTaskStatusInput:
    task_id: str
    status: str
    outputs: dict[str, str] = field(default_factory=dict)


@dataclass
class UpdateMissionStatusInput:
    mission_id: str
    status: str


@dataclass
class TaskInfo:
    """Lightweight task representation returned by persistence activities."""
    task_id: str
    mission_id: str
    phase: str
    name: str
    task_type: str
    status: str
    assigned_role: str
    assigned_contractor: str = ""
    facility: str = ""
    nominal_duration_seconds: int = 0
    failure_probability: float = 0.0


# ── LLM Activity Types ─────────────────────────────────────────────

@dataclass
class GenerateRFPInput:
    mission_id: str
    component_name: str
    component_type: str


@dataclass
class GenerateProposalInput:
    rfp_text: str
    contractor_slug: str
    contractor_name: str
    contractor_profile: str
    contractor_reliability: float
    contractor_cost_factor: float


@dataclass
class EvaluateProposalInput:
    rfp_text: str
    proposal_text: str
    contractor_name: str
    rubric_json: str = ""
    component_type: str = ""


@dataclass
class GenerateTestReportInput:
    test_name: str
    passed: bool
    component_name: str
    details: str = ""
    component_type: str = ""


@dataclass
class GenerateRubricInput:
    rfp_text: str
    component_type: str


@dataclass
class ContractorInfo:
    """Lightweight contractor data safe for workflow serialization."""
    slug: str
    name: str
    profile: str
    reliability: float
    cost_factor: float
    specialties: list[str] = field(default_factory=list)


@dataclass
class SaveArtifactInput:
    task_id: str
    artifact_type: str
    content: dict[str, str] = field(default_factory=dict)


@dataclass
class GetContractorsBySpecialtyInput:
    specialty: str


@dataclass
class LLMResult:
    """Generic LLM activity result."""
    content: str
    artifact_type: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


# ── Prerequisite Resolution ─────────────────────────────────────────

@dataclass
class CompleteTaskAndResolveInput:
    """Input for the combined complete + resolve-prerequisites activity."""
    task_id: str
    mission_id: str
    outputs: dict[str, str] = field(default_factory=dict)


@dataclass
class ResolveResult:
    """Result of prerequisite resolution after a task completes."""
    newly_available_task_ids: list[str] = field(default_factory=list)
    newly_available_task_names: list[str] = field(default_factory=list)


# ── Rework ──────────────────────────────────────────────────────────

@dataclass
class CreateReworkTaskInput:
    """Input for creating a rework task from a failed task."""
    original_task_id: str
    mission_id: str
    reason: str


@dataclass
class CreateReworkTaskResult:
    new_task_id: str
    original_task_id: str
    new_task_name: str


# ── Escalation ──────────────────────────────────────────────────────

@dataclass
class EscalationNotice:
    """Notification when a task exceeds expected duration or needs attention."""
    task_id: str
    task_name: str
    mission_id: str
    expected_seconds: int
    actual_seconds: int
    escalation_level: str  # "warning" (1.5x), "critical" (2x), "halt" (3x)
    message: str


# ── Simulation Activity Types ───────────────────────────────────────

@dataclass
class SimulateTaskInput:
    task_id: str
    task_name: str
    failure_probability: float
    nominal_duration_seconds: int


@dataclass
class SimulateTaskResult:
    task_id: str
    passed: bool
    duration_seconds: int
    details: str = ""
    escalated: bool = False
