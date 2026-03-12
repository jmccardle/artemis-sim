"""Pydantic request/response models for the REST API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# --- Health ---

class HealthResponse(BaseModel):
    status: str
    version: str
    simulated_time: datetime | None = None


# --- Mission ---

class MissionCreate(BaseModel):
    name: str
    architecture_type: str = "estes"


class MissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    architecture_type: str
    status: str
    workflow_id: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Task ---

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mission_id: uuid.UUID
    phase: str
    name: str
    task_type: str
    status: str
    assigned_role: str
    assigned_contractor: str | None = None
    facility: str | None = None
    prerequisites: list = []
    nominal_duration_seconds: int = 0
    failure_probability: float = 0.0
    simulated_start: datetime | None = None
    simulated_end: datetime | None = None
    inputs: dict = {}
    outputs: dict = {}
    rework_of: uuid.UUID | None = None
    workflow_id: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Contractor ---

class ContractorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    reliability: float
    cost_factor: float
    speed_factor: float
    specialties: list
    branding: dict
    created_at: datetime
    updated_at: datetime


# --- Facility ---

class FacilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    location: str
    capacity: int
    current_occupancy: int
    capabilities: list
    workflow_id: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Clock ---

class ClockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_time: datetime
    last_advance_reason: str | None = None


class ClockAdvanceRequest(BaseModel):
    duration_seconds: int
    reason: str


# --- Artifact ---

class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    artifact_type: str
    content: dict
    created_at: datetime


# --- Admin ---

class ResetRequest(BaseModel):
    confirm: bool
    reason: str = ""


class ResetResponse(BaseModel):
    status: str
    timestamp: datetime


class InjectAction(BaseModel):
    type: str
    task_id: uuid.UUID | None = None
    outcome: str | None = None
    advance_clock: bool = False
    failure_reason: str | None = None
    architecture: str | None = None
    name: str | None = None
    duration_hours: float | None = None
    contractor_slug: str | None = None
    reliability: float | None = None


class InjectRequest(BaseModel):
    actions: list[InjectAction]


class SimulationStatusResponse(BaseModel):
    simulated_time: datetime | None = None
    mission_count: int = 0
    task_count: int = 0
    facility_count: int = 0
    contractor_count: int = 0
    temporal_connected: bool = False


# --- Invoice ---

class InvoiceCreate(BaseModel):
    mission_id: uuid.UUID
    amount: float
    description: str
    line_items: list[dict] = []
    task_id: uuid.UUID | None = None


class InvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contractor_id: uuid.UUID
    mission_id: uuid.UUID
    task_id: uuid.UUID | None = None
    invoice_number: str
    amount: float
    status: str
    description: str
    line_items: list = []
    submitted_at: datetime
    reviewed_at: datetime | None = None
    reviewer_username: str | None = None
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class InvoiceStatusUpdate(BaseModel):
    status: str
    notes: str = ""


class BudgetSummary(BaseModel):
    total: float = 0.0
    by_mission: dict[str, float] = {}
    by_contractor: dict[str, float] = {}
    invoice_count: int = 0
