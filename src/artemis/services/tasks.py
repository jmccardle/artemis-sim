"""Task service functions — shared by API routers and view routes."""

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode

from artemis.models.artifact import TaskArtifact
from artemis.models.task import Task, TaskStatus
from artemis.workflows.data_types import TaskCompletionInput, mission_workflow_id


async def get_task(db: AsyncSession, task_id: uuid.UUID) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


async def _signal_task(
    db: AsyncSession,
    temporal_client: Client,
    task_id: uuid.UUID,
    outcome: str,
    username: str,
) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if outcome == "advance" and task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Task is already completed")

    wf_id = mission_workflow_id(str(task.mission_id))
    try:
        handle = temporal_client.get_workflow_handle(wf_id)
        signal_outcome = "success" if outcome == "advance" else outcome
        details_verb = {"success": "Completed", "failure": "Failed", "advance": "Advanced"}
        await handle.signal(
            "task_completion",
            TaskCompletionInput(
                task_name=task.name,
                outcome=signal_outcome,
                details=f"{details_verb.get(outcome, outcome)} by {username}",
            ),
        )
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=409,
                detail=f"Mission workflow {wf_id} not found or not running",
            )
        raise

    await db.refresh(task)
    return task


async def complete_task(
    db: AsyncSession, temporal_client: Client, task_id: uuid.UUID, username: str
) -> Task:
    return await _signal_task(db, temporal_client, task_id, "success", username)


async def fail_task(
    db: AsyncSession, temporal_client: Client, task_id: uuid.UUID, username: str
) -> Task:
    return await _signal_task(db, temporal_client, task_id, "failure", username)


async def advance_task(
    db: AsyncSession, temporal_client: Client, task_id: uuid.UUID, username: str
) -> Task:
    return await _signal_task(db, temporal_client, task_id, "advance", username)


async def get_task_artifacts(db: AsyncSession, task_id: uuid.UUID) -> list[TaskArtifact]:
    result = await db.execute(
        select(TaskArtifact)
        .where(TaskArtifact.task_id == task_id)
        .order_by(TaskArtifact.created_at.desc())
    )
    return list(result.scalars().all())
