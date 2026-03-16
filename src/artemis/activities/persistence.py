"""Persistence activities — database reads/writes for workflows."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from temporalio import activity

from artemis.workflows.data_types import (
    CompleteTaskAndResolveInput,
    ContractorInfo,
    CreateReworkTaskInput,
    CreateReworkTaskResult,
    EscalationNotice,
    GetContractorsBySpecialtyInput,
    ResolveResult,
    SaveArtifactInput,
)


@dataclass
class CreateMissionTasksInput:
    mission_id: str
    architecture_name: str


@dataclass
class CreateMissionTasksResult:
    mission_name: str
    task_count: int


@dataclass
class UpdateMissionStatusInput:
    mission_id: str
    status: str


@dataclass
class UpdateTaskStatusInput:
    task_id: str
    status: str
    outputs: dict[str, str] = field(default_factory=dict)


@dataclass
class GetTasksByPhaseInput:
    mission_id: str
    phase: str


@dataclass
class TaskInfoResult:
    task_id: str
    name: str
    task_type: str
    status: str
    assigned_role: str
    nominal_duration_seconds: int = 0
    failure_probability: float = 0.0
    facility: str = ""
    prerequisites: list[str] = field(default_factory=list)


@activity.defn
async def create_mission_tasks(input: CreateMissionTasksInput) -> CreateMissionTasksResult:
    """Create all tasks for a mission based on its architecture."""
    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.mission import Mission

    mission_uuid = uuid.UUID(input.mission_id)

    async with async_session_factory() as session:
        # Get mission name
        result = await session.execute(
            select(Mission).where(Mission.id == mission_uuid)
        )
        mission = result.scalar_one()

        # Create tasks based on architecture
        if input.architecture_name == "estes":
            from artemis.seed.estes_mission import create_estes_tasks

            tasks = await create_estes_tasks(session, mission_uuid)
        else:
            raise ValueError(f"Unknown architecture: {input.architecture_name}")

        await session.commit()

        return CreateMissionTasksResult(
            mission_name=mission.name,
            task_count=len(tasks),
        )


@activity.defn
async def update_mission_status(input: UpdateMissionStatusInput) -> None:
    """Update a mission's status."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.mission import Mission

    async with async_session_factory() as session:
        result = await session.execute(
            select(Mission).where(Mission.id == uuid_mod.UUID(input.mission_id))
        )
        mission = result.scalar_one()
        mission.status = input.status
        await session.commit()


@activity.defn
async def update_task_status(input: UpdateTaskStatusInput) -> None:
    """Update a task's status and optional outputs."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.task import Task

    async with async_session_factory() as session:
        result = await session.execute(
            select(Task).where(Task.id == uuid_mod.UUID(input.task_id))
        )
        task = result.scalar_one()
        task.status = input.status
        if input.outputs:
            task.outputs = input.outputs
        await session.commit()


@activity.defn
async def get_tasks_by_phase(input: GetTasksByPhaseInput) -> list[TaskInfoResult]:
    """Get all tasks for a mission phase."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.task import Task

    async with async_session_factory() as session:
        result = await session.execute(
            select(Task).where(
                Task.mission_id == uuid_mod.UUID(input.mission_id),
                Task.phase == input.phase,
            )
        )
        tasks = result.scalars().all()

        return [
            TaskInfoResult(
                task_id=str(task.id),
                name=task.name,
                task_type=task.task_type,
                status=task.status,
                assigned_role=task.assigned_role,
                nominal_duration_seconds=task.nominal_duration_seconds,
                failure_probability=task.failure_probability,
                facility=task.facility or "",
                prerequisites=task.prerequisites if isinstance(task.prerequisites, list) else [],
            )
            for task in tasks
        ]


@activity.defn
async def save_artifact(input: SaveArtifactInput) -> str:
    """Save an LLM-generated artifact to the database. Returns artifact ID."""
    import uuid as uuid_mod

    from artemis.database import async_session_factory
    from artemis.models.artifact import TaskArtifact

    artifact = TaskArtifact(
        task_id=uuid_mod.UUID(input.task_id),
        artifact_type=input.artifact_type,
        content=input.content,
    )

    async with async_session_factory() as session:
        session.add(artifact)
        await session.commit()
        return str(artifact.id)


@activity.defn
async def get_contractors_by_specialty(
    input: GetContractorsBySpecialtyInput,
) -> list[ContractorInfo]:
    """Get contractors whose specialties include the given specialty."""
    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.contractor import Contractor

    async with async_session_factory() as session:
        result = await session.execute(select(Contractor))
        all_contractors = result.scalars().all()

        return [
            ContractorInfo(
                slug=c.slug,
                name=c.name,
                profile=c.llm_profile,
                reliability=c.reliability,
                cost_factor=c.cost_factor,
                specialties=c.specialties if isinstance(c.specialties, list) else [],
            )
            for c in all_contractors
            if isinstance(c.specialties, list) and input.specialty in c.specialties
        ]


@activity.defn
async def complete_task_and_resolve(
    input: CompleteTaskAndResolveInput,
) -> ResolveResult:
    """Mark a task COMPLETED and resolve downstream prerequisites.

    Combines update_task_status(COMPLETED) + resolve_prerequisites in a single
    activity and DB session, ensuring prerequisite resolution is never skipped.
    """
    import uuid as uuid_mod

    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.task import Task, TaskStatus
    from artemis.services.scheduling import resolve_prerequisites_for_task

    async with async_session_factory() as session:
        # Mark the task as COMPLETED
        result = await session.execute(
            select(Task).where(Task.id == uuid_mod.UUID(input.task_id))
        )
        task = result.scalar_one()
        task.status = TaskStatus.COMPLETED
        if input.outputs:
            task.outputs = input.outputs
        await session.flush()

        # Resolve downstream prerequisites
        newly_available = await resolve_prerequisites_for_task(
            session, input.task_id, input.mission_id
        )

        await session.commit()

        return ResolveResult(
            newly_available_task_ids=[str(t.id) for t in newly_available],
            newly_available_task_names=[t.name for t in newly_available],
        )


@activity.defn
async def create_rework_task(input: CreateReworkTaskInput) -> CreateReworkTaskResult:
    """Create a rework task from a failed task.

    Sets the original task status to REWORK and creates a new Task with
    rework_of pointing back. The new task is immediately AVAILABLE.
    """
    import uuid as uuid_mod

    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.task import Task, TaskStatus

    async with async_session_factory() as session:
        # Get original task
        result = await session.execute(
            select(Task).where(Task.id == uuid_mod.UUID(input.original_task_id))
        )
        original = result.scalar_one()

        # Count existing rework generations
        rework_count = 1
        check_id = original.rework_of
        while check_id is not None:
            res = await session.execute(select(Task).where(Task.id == check_id))
            parent = res.scalar_one_or_none()
            if parent is None:
                break
            rework_count += 1
            check_id = parent.rework_of

        # Set original to REWORK
        original.status = TaskStatus.REWORK

        # Create new rework task
        rework_name = f"{original.name} (rework {rework_count})"
        rework_task = Task(
            mission_id=original.mission_id,
            phase=original.phase,
            name=rework_name,
            task_type=original.task_type,
            status=TaskStatus.AVAILABLE,
            assigned_role=original.assigned_role,
            assigned_contractor=original.assigned_contractor,
            facility=original.facility,
            prerequisites=[],  # Rework tasks are immediately actionable
            nominal_duration_seconds=original.nominal_duration_seconds,
            failure_probability=original.failure_probability,
            rework_of=original.id,
            inputs={"rework_reason": input.reason},
        )
        session.add(rework_task)
        await session.flush()

        new_task_id = str(rework_task.id)
        await session.commit()

        return CreateReworkTaskResult(
            new_task_id=new_task_id,
            original_task_id=input.original_task_id,
            new_task_name=rework_name,
        )


@activity.defn
async def send_escalation(input: EscalationNotice) -> None:
    """Record an escalation in the task outputs and create an artifact."""
    import uuid as uuid_mod

    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.artifact import TaskArtifact
    from artemis.models.task import Task

    async with async_session_factory() as session:
        # Update task outputs with escalation info
        result = await session.execute(
            select(Task).where(Task.id == uuid_mod.UUID(input.task_id))
        )
        task = result.scalar_one()
        outputs = dict(task.outputs) if task.outputs else {}
        outputs["escalation_level"] = input.escalation_level
        outputs["escalation_message"] = input.message
        task.outputs = outputs

        # Create escalation artifact
        artifact = TaskArtifact(
            task_id=task.id,
            artifact_type="ESCALATION_NOTICE",
            content={
                "level": input.escalation_level,
                "message": input.message,
                "expected_seconds": input.expected_seconds,
                "actual_seconds": input.actual_seconds,
            },
        )
        session.add(artifact)
        await session.commit()
