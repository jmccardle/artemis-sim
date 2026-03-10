import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import MissionCreate, MissionResponse, TaskResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.services import missions as mission_svc

router = APIRouter()


@router.get("", response_model=list[MissionResponse])
async def list_missions(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await mission_svc.list_missions(db)


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await mission_svc.get_mission(db, mission_id)


@router.post("", response_model=MissionResponse, status_code=201)
async def create_mission(
    body: MissionCreate,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    client = request.app.state.temporal_client
    return await mission_svc.create_mission(db, client, body.name, body.architecture_type)


@router.get("/{mission_id}/tasks", response_model=list[TaskResponse])
async def list_mission_tasks(
    mission_id: uuid.UUID,
    phase: Optional[str] = Query(None, description="Filter by phase"),
    status: Optional[str] = Query(None, description="Filter by task status"),
    assigned_role: Optional[str] = Query(None, description="Filter by assigned role"),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await mission_svc.get_mission_tasks(db, mission_id, phase, status, assigned_role)
