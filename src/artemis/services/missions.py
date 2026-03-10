"""Mission service functions — shared by API routers and view routes."""

import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client

from artemis.models.mission import Mission, MissionStatus
from artemis.models.task import Task
from artemis.workflows.data_types import ORCHESTRATION_QUEUE, mission_workflow_id
from artemis.workflows.mission import MissionWorkflow


async def list_missions(db: AsyncSession) -> list[Mission]:
    result = await db.execute(select(Mission).order_by(Mission.created_at.desc()))
    return list(result.scalars().all())


async def get_mission(db: AsyncSession, mission_id: uuid.UUID) -> Mission:
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if mission is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return mission


async def get_mission_tasks(
    db: AsyncSession,
    mission_id: uuid.UUID,
    phase: Optional[str] = None,
    status: Optional[str] = None,
    assigned_role: Optional[str] = None,
) -> list[Task]:
    # Verify mission exists
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")

    stmt = select(Task).where(Task.mission_id == mission_id)
    if phase is not None:
        stmt = stmt.where(Task.phase == phase)
    if status is not None:
        stmt = stmt.where(Task.status == status)
    if assigned_role is not None:
        stmt = stmt.where(Task.assigned_role == assigned_role)

    stmt = stmt.order_by(Task.created_at.asc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_mission(
    db: AsyncSession,
    temporal_client: Client,
    name: str,
    architecture_type: str,
) -> Mission:
    mission = Mission(
        name=name,
        architecture_type=architecture_type,
        status=MissionStatus.CREATED,
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)

    wf_id = mission_workflow_id(str(mission.id))
    await temporal_client.start_workflow(
        MissionWorkflow.run,
        args=[str(mission.id), architecture_type],
        id=wf_id,
        task_queue=ORCHESTRATION_QUEUE,
    )
    mission.workflow_id = wf_id
    await db.commit()
    await db.refresh(mission)

    return mission
