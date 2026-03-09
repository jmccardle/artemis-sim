"""Persistence activities — database reads/writes for workflows."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from temporalio import activity


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
