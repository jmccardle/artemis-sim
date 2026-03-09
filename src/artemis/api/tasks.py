import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import WorkflowNotFoundError

from artemis.api.schemas import ArtifactResponse, TaskResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models.artifact import TaskArtifact
from artemis.models.task import Task, TaskStatus
from artemis.workflows.data_types import TaskCompletionInput, mission_workflow_id

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
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Signal the mission workflow with task completion
    client = request.app.state.temporal_client
    wf_id = mission_workflow_id(str(task.mission_id))
    try:
        handle = client.get_workflow_handle(wf_id)
        await handle.signal(
            "task_completion",
            TaskCompletionInput(
                task_name=task.name,
                outcome="success",
                details=f"Completed by {user.username}",
            ),
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=409,
            detail=f"Mission workflow {wf_id} not found or not running",
        )

    # Refresh task from DB (workflow activity may have updated it)
    await db.refresh(task)
    return task


@router.post("/{task_id}/fail", response_model=TaskResponse)
async def fail_task(
    task_id: uuid.UUID,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    # Signal the mission workflow with task failure
    client = request.app.state.temporal_client
    wf_id = mission_workflow_id(str(task.mission_id))
    try:
        handle = client.get_workflow_handle(wf_id)
        await handle.signal(
            "task_completion",
            TaskCompletionInput(
                task_name=task.name,
                outcome="failure",
                details=f"Failed by {user.username}",
            ),
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=409,
            detail=f"Mission workflow {wf_id} not found or not running",
        )

    # Refresh task from DB (workflow activity may have updated it)
    await db.refresh(task)
    return task


@router.post("/{task_id}/advance", response_model=TaskResponse)
async def advance_task(
    task_id: uuid.UUID,
    request: Request,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Task is already completed")

    # Signal the mission workflow to advance/complete this task
    client = request.app.state.temporal_client
    wf_id = mission_workflow_id(str(task.mission_id))
    try:
        handle = client.get_workflow_handle(wf_id)
        await handle.signal(
            "task_completion",
            TaskCompletionInput(
                task_name=task.name,
                outcome="success",
                details=f"Advanced by {user.username}",
            ),
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=409,
            detail=f"Mission workflow {wf_id} not found or not running",
        )

    # Refresh task from DB (workflow activity may have updated it)
    await db.refresh(task)
    return task


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
