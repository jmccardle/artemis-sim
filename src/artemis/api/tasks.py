import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import ArtifactResponse, TaskResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.services import tasks as task_svc

router = APIRouter()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await task_svc.get_task(db, task_id)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    client = request.app.state.temporal_client
    return await task_svc.complete_task(db, client, task_id, user.username)


@router.post("/{task_id}/fail", response_model=TaskResponse)
async def fail_task(
    task_id: uuid.UUID,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    client = request.app.state.temporal_client
    return await task_svc.fail_task(db, client, task_id, user.username)


@router.post("/{task_id}/advance", response_model=TaskResponse)
async def advance_task(
    task_id: uuid.UUID,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    client = request.app.state.temporal_client
    return await task_svc.advance_task(db, client, task_id, user.username)


@router.get("/{task_id}/artifacts", response_model=list[ArtifactResponse])
async def list_task_artifacts(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await task_svc.get_task_artifacts(db, task_id)
