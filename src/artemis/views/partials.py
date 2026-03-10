"""HTMX partial endpoints — return HTML fragments for dynamic updates."""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.database import get_db_session
from artemis.services import clock as clock_svc
from artemis.services import contractors as contractor_svc
from artemis.services import facilities as facility_svc
from artemis.services import missions as mission_svc
from artemis.services import tasks as task_svc
from artemis.templating import templates
from artemis.views.helpers import get_session_user

router = APIRouter()


@router.get("/missions", response_class=HTMLResponse)
async def missions_partial(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    missions = await mission_svc.list_missions(db)

    # Get tasks per mission for progress bars
    mission_tasks = {}
    for mission in missions:
        tasks = await mission_svc.get_mission_tasks(db, mission.id)
        mission_tasks[mission.id] = tasks

    return templates.TemplateResponse(
        "partials/mission/progress_bars.html",
        {"request": request, "missions": missions, "mission_tasks": mission_tasks},
    )


@router.get("/missions/{mission_id}/kanban", response_class=HTMLResponse)
async def mission_kanban(
    mission_id: uuid.UUID,
    request: Request,
    phase: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    tasks = await mission_svc.get_mission_tasks(db, mission_id, phase=phase)
    return templates.TemplateResponse(
        "partials/kanban/board.html",
        {"request": request, "tasks": tasks, "mission_id": mission_id},
    )


@router.get("/tasks/{task_id}/detail", response_class=HTMLResponse)
async def task_detail(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    task = await task_svc.get_task(db, task_id)
    artifacts = await task_svc.get_task_artifacts(db, task_id)
    return templates.TemplateResponse(
        "partials/task/detail.html",
        {"request": request, "task": task, "artifacts": artifacts},
    )


@router.get("/admin/status", response_class=HTMLResponse)
async def admin_status_partial(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    from artemis.services import admin as admin_svc

    status = await admin_svc.get_status(db)
    return templates.TemplateResponse(
        "partials/admin/simulation_status.html",
        {"request": request, "status": status},
    )


@router.get("/facilities/board", response_class=HTMLResponse)
async def facilities_board(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    facilities = await facility_svc.list_facilities(db)
    return templates.TemplateResponse(
        "partials/facility/status_board.html",
        {"request": request, "facilities": facilities},
    )
