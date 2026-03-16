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


# ── Scheduling partials ──────────────────────────────────────────


@router.get("/missions/{mission_id}/available-work", response_class=HTMLResponse)
async def available_work_partial(
    mission_id: uuid.UUID,
    request: Request,
    role: str | None = None,
    contractor: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    from artemis.services.scheduling import get_available_work

    work = await get_available_work(
        db, mission_id=mission_id, role=role, contractor=contractor,
    )
    return templates.TemplateResponse(
        "partials/scheduling/available_work.html",
        {"request": request, "available_work": work, "mission_id": str(mission_id)},
    )


@router.get("/tasks/{task_id}/blocking", response_class=HTMLResponse)
async def task_blocking_partial(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    from artemis.services.scheduling import get_blocking_analysis

    analysis = await get_blocking_analysis(db, task_id)
    return templates.TemplateResponse(
        "partials/scheduling/blocking_detail.html",
        {"request": request, "analysis": analysis},
    )


@router.get("/missions/{mission_id}/critical-path", response_class=HTMLResponse)
async def critical_path_partial(
    mission_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    from artemis.services.scheduling import compute_critical_path

    cp = await compute_critical_path(db, mission_id)
    return templates.TemplateResponse(
        "partials/scheduling/critical_path.html",
        {"request": request, "critical_path": cp, "mission_id": str(mission_id)},
    )


@router.get("/tasks/{task_id}/suggestions", response_class=HTMLResponse)
async def work_suggestions_partial(
    task_id: uuid.UUID,
    request: Request,
    role: str | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    from artemis.services.scheduling import get_work_suggestions

    task = await task_svc.get_task(db, task_id)
    suggestions = await get_work_suggestions(
        db, task.mission_id, role=role or "", blocked_task_id=task_id,
    )
    return templates.TemplateResponse(
        "partials/scheduling/work_suggestions.html",
        {"request": request, "suggestions": suggestions, "blocked_task_name": task.name},
    )
