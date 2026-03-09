"""Estes Model Rocket — MVP mission architecture seed data.

A minimal 5-component rocket assembly that exercises the full workflow pipeline:
procurement → delivery → integration (gluing + assembly) → launch readiness.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models.task import Task, TaskStatus, TaskType


# ── Local data structures ───────────────────────────────────────────

@dataclass
class ComponentDef:
    """Component definition for the Estes architecture."""
    name: str
    component_type: str  # contractor bidding specialty
    transport_method: str
    transport_origin: str
    transport_destination: str


@dataclass
class TaskDef:
    """Task template definition."""
    name: str
    phase: str
    task_type: str
    assigned_role: str
    nominal_duration_seconds: int = 0
    failure_probability: float = 0.0
    facility: str | None = None
    prerequisite_names: list[str] = field(default_factory=list)


# ── Components ──────────────────────────────────────────────────────

ESTES_COMPONENTS = [
    ComponentDef("B-class solid motor", "propulsion", "truck", "Hobby Shop", "The Garage"),
    ComponentDef("Plastic parachute", "recovery-systems", "truck", "Hobby Shop", "The Garage"),
    ComponentDef("Rocket body tube", "structures", "truck", "Hobby Shop", "The Garage"),
    ComponentDef("Fin set (x3)", "structures", "truck", "Hobby Shop", "The Garage"),
    ComponentDef("Bottle of glue", "materials", "truck", "Hobby Shop", "The Garage"),
]


# ── Task generation per phase ───────────────────────────────────────

def _procurement_tasks() -> list[TaskDef]:
    """Generate procurement task templates for each component."""
    tasks: list[TaskDef] = []
    for comp in ESTES_COMPONENTS:
        tasks.extend([
            TaskDef(
                name=f"Issue RFP for {comp.name}",
                phase="PROCUREMENT",
                task_type=TaskType.AUTOMATED,
                assigned_role="nasa-contracts-officer",
                nominal_duration_seconds=3600,
            ),
            TaskDef(
                name=f"Submit proposal for {comp.name}",
                phase="PROCUREMENT",
                task_type=TaskType.AGENT,
                assigned_role="contractor-engineer",
                nominal_duration_seconds=14400,
                prerequisite_names=[f"Issue RFP for {comp.name}"],
            ),
            TaskDef(
                name=f"Evaluate proposals for {comp.name}",
                phase="PROCUREMENT",
                task_type=TaskType.AGENT,
                assigned_role="nasa-tech-authority",
                nominal_duration_seconds=7200,
                prerequisite_names=[f"Submit proposal for {comp.name}"],
            ),
            TaskDef(
                name=f"Award contract for {comp.name}",
                phase="PROCUREMENT",
                task_type=TaskType.USER,
                assigned_role="nasa-contracts-officer",
                nominal_duration_seconds=1800,
                prerequisite_names=[f"Evaluate proposals for {comp.name}"],
            ),
        ])
    return tasks


def _delivery_tasks() -> list[TaskDef]:
    """Generate delivery task templates for each component."""
    tasks: list[TaskDef] = []
    for comp in ESTES_COMPONENTS:
        tasks.extend([
            TaskDef(
                name=f"Ship {comp.name}",
                phase="DELIVERY",
                task_type=TaskType.SIMULATED,
                assigned_role="contractor-engineer",
                nominal_duration_seconds=7200,
                prerequisite_names=[f"Award contract for {comp.name}"],
            ),
            TaskDef(
                name=f"Receive {comp.name} at The Garage",
                phase="DELIVERY",
                task_type=TaskType.USER,
                assigned_role="egs-ground-ops",
                nominal_duration_seconds=1800,
                prerequisite_names=[f"Ship {comp.name}"],
            ),
            TaskDef(
                name=f"Inspect {comp.name}",
                phase="DELIVERY",
                task_type=TaskType.AUTOMATED,
                assigned_role="egs-ground-ops",
                nominal_duration_seconds=3600,
                failure_probability=0.05,
                prerequisite_names=[f"Receive {comp.name} at The Garage"],
            ),
        ])
    return tasks


def _integration_tasks() -> list[TaskDef]:
    """Generate integration task templates (gluing + final assembly)."""
    return [
        # ── Gluing sub-phase ──
        TaskDef(
            name="Glue fins to body tube",
            phase="INTEGRATION",
            task_type=TaskType.USER,
            assigned_role="contractor-engineer",
            nominal_duration_seconds=7200,
            facility="The Garage",
            prerequisite_names=[
                "Inspect Rocket body tube",
                "Inspect Fin set (x3)",
                "Inspect Bottle of glue",
            ],
        ),
        TaskDef(
            name="Structural inspection of fin attachment",
            phase="INTEGRATION",
            task_type=TaskType.AUTOMATED,
            assigned_role="egs-ground-ops",
            nominal_duration_seconds=3600,
            failure_probability=0.10,
            prerequisite_names=["Glue fins to body tube"],
        ),
        # ── Final assembly sub-phase ──
        TaskDef(
            name="Install solid motor",
            phase="INTEGRATION",
            task_type=TaskType.USER,
            assigned_role="contractor-engineer",
            nominal_duration_seconds=3600,
            facility="The Garage",
            prerequisite_names=[
                "Structural inspection of fin attachment",
                "Inspect B-class solid motor",
            ],
        ),
        TaskDef(
            name="Install parachute",
            phase="INTEGRATION",
            task_type=TaskType.USER,
            assigned_role="contractor-engineer",
            nominal_duration_seconds=1800,
            facility="The Garage",
            prerequisite_names=[
                "Structural inspection of fin attachment",
                "Inspect Plastic parachute",
            ],
        ),
        TaskDef(
            name="Final integration test",
            phase="INTEGRATION",
            task_type=TaskType.AUTOMATED,
            assigned_role="egs-ground-ops",
            nominal_duration_seconds=3600,
            failure_probability=0.08,
            prerequisite_names=["Install solid motor", "Install parachute"],
        ),
    ]


def _launch_readiness_tasks() -> list[TaskDef]:
    """Generate launch readiness task templates."""
    return [
        TaskDef(
            name="Final inspection review",
            phase="LAUNCH_READINESS",
            task_type=TaskType.USER,
            assigned_role="nasa-tech-authority",
            nominal_duration_seconds=3600,
            prerequisite_names=["Final integration test"],
        ),
        TaskDef(
            name="Launch readiness review",
            phase="LAUNCH_READINESS",
            task_type=TaskType.USER,
            assigned_role="nasa-program-manager",
            nominal_duration_seconds=1800,
            prerequisite_names=["Final inspection review"],
        ),
    ]


def get_estes_task_definitions() -> list[TaskDef]:
    """Return all task definitions for the Estes mission architecture."""
    return (
        _procurement_tasks()
        + _delivery_tasks()
        + _integration_tasks()
        + _launch_readiness_tasks()
    )


async def create_estes_tasks(db: AsyncSession, mission_id: uuid.UUID) -> list[Task]:
    """Create all Task rows for an Estes mission.

    Resolves prerequisite task names to UUID strings.
    Tasks with no prerequisites start as AVAILABLE; others as NOT_READY.
    Callers must commit the session.
    """
    task_defs = get_estes_task_definitions()

    # First pass: create Task objects and track name→UUID
    name_to_id: dict[str, uuid.UUID] = {}
    tasks: list[Task] = []

    for td in task_defs:
        task = Task(
            mission_id=mission_id,
            phase=td.phase,
            name=td.name,
            task_type=td.task_type,
            status=TaskStatus.NOT_READY if td.prerequisite_names else TaskStatus.AVAILABLE,
            assigned_role=td.assigned_role,
            nominal_duration_seconds=td.nominal_duration_seconds,
            failure_probability=td.failure_probability,
            facility=td.facility,
            prerequisites=[],
        )
        db.add(task)
        tasks.append(task)

    # Flush to materialise auto-generated UUIDs
    await db.flush()

    # Build name→id map
    for task, td in zip(tasks, task_defs):
        name_to_id[td.name] = task.id

    # Second pass: resolve prerequisite names to UUID strings
    for task, td in zip(tasks, task_defs):
        if td.prerequisite_names:
            task.prerequisites = [str(name_to_id[name]) for name in td.prerequisite_names]

    await db.flush()
    return tasks
