"""Contractor portal views — branded per-contractor dashboards."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.database import get_db_session
from artemis.services import contractors as contractor_svc
from artemis.services import missions as mission_svc
from artemis.templating import templates
from artemis.views.helpers import ROLE_DISPLAY_NAMES, get_session_user

router = APIRouter()


@router.get("/contractor/{slug}", response_class=HTMLResponse)
async def contractor_portal(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    contractor = await contractor_svc.get_contractor(db, slug)
    role = user.roles[0] if user.roles else "contractor-pm"
    role_display = ROLE_DISPLAY_NAMES.get(role, role)

    # Get tasks assigned to this contractor
    missions = await mission_svc.list_missions(db)
    contractor_tasks = []
    for mission in missions:
        tasks = await mission_svc.get_mission_tasks(db, mission.id)
        contractor_tasks.extend(
            t for t in tasks if t.assigned_contractor == contractor.slug
        )

    return templates.TemplateResponse(
        "contractor_portal/dashboard.html",
        {
            "request": request,
            "user": user,
            "role": role,
            "role_display": role_display,
            "contractor": contractor,
            "tasks": contractor_tasks,
            "clock_time": None,
        },
    )
