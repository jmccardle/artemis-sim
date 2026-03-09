import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import ArtifactResponse, TaskResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models.artifact import TaskArtifact
from artemis.models.task import Task

router = APIRouter()


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    raise HTTPException(
        status_code=501,
        detail="Task completion requires Temporal workflow signaling (Phase 1)",
    )


@router.post("/{task_id}/fail", response_model=TaskResponse)
async def fail_task(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    raise HTTPException(
        status_code=501,
        detail="Task failure requires Temporal workflow signaling (Phase 1)",
    )


@router.post("/{task_id}/advance", response_model=TaskResponse)
async def advance_task(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    raise HTTPException(
        status_code=501,
        detail="Task advancement requires Temporal workflow signaling (Phase 1)",
    )


@router.get("/{task_id}/artifacts", response_model=list[ArtifactResponse])
async def list_task_artifacts(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(
        select(TaskArtifact)
        .where(TaskArtifact.task_id == task_id)
        .order_by(TaskArtifact.created_at.desc())
    )
    return result.scalars().all()
