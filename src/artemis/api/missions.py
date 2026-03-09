import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import MissionCreate, MissionResponse, TaskResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models.mission import Mission, MissionStatus
from artemis.models.task import Task
from artemis.workflows.data_types import ORCHESTRATION_QUEUE, mission_workflow_id
from artemis.workflows.mission import MissionWorkflow

router = APIRouter()


@router.get("", response_model=list[MissionResponse])
async def list_missions(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Mission).order_by(Mission.created_at.desc()))
    return result.scalars().all()


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if mission is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return mission


@router.post("", response_model=MissionResponse, status_code=201)
async def create_mission(
    body: MissionCreate,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    mission = Mission(
        name=body.name,
        architecture_type=body.architecture_type,
        status=MissionStatus.CREATED,
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)

    # Start the MissionWorkflow
    client = request.app.state.temporal_client
    wf_id = mission_workflow_id(str(mission.id))
    await client.start_workflow(
        MissionWorkflow.run,
        args=[str(mission.id), body.architecture_type],
        id=wf_id,
        task_queue=ORCHESTRATION_QUEUE,
    )
    mission.workflow_id = wf_id
    await db.commit()
    await db.refresh(mission)

    return mission


@router.get("/{mission_id}/tasks", response_model=list[TaskResponse])
async def list_mission_tasks(
    mission_id: uuid.UUID,
    phase: Optional[str] = Query(None, description="Filter by phase"),
    status: Optional[str] = Query(None, description="Filter by task status"),
    assigned_role: Optional[str] = Query(None, description="Filter by assigned role"),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
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
    return result.scalars().all()
