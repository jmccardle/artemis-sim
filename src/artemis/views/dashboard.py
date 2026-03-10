"""Dashboard dispatcher — routes users to role-appropriate dashboards."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.database import get_db_session
from artemis.services import admin as admin_svc
from artemis.services import clock as clock_svc
from artemis.services import contractors as contractor_svc
from artemis.services import facilities as facility_svc
from artemis.services import missions as mission_svc
from artemis.templating import templates
from artemis.views.helpers import ROLE_DISPLAY_NAMES, get_session_user

router = APIRouter()

ROLE_TEMPLATE_MAP = {
    "admin": "dashboard/admin.html",
    "nasa-program-manager": "dashboard/program_manager.html",
    "nasa-tech-authority": "dashboard/tech_authority.html",
    "nasa-contracts-officer": "dashboard/contracts_officer.html",
    "contractor-pm": "dashboard/contractor_pm.html",
    "contractor-engineer": "dashboard/contractor_engineer.html",
    "egs-ground-ops": "dashboard/ground_ops.html",
}


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    if user is None:
        return RedirectResponse(url="/login", status_code=302)

    role = user.roles[0] if user.roles else "admin"
    template_name = ROLE_TEMPLATE_MAP.get(role, "dashboard/admin.html")
    role_display = ROLE_DISPLAY_NAMES.get(role, role)

    # Get clock time (fail gracefully if not initialized)
    clock_time = None
    try:
        temporal_client = request.app.state.temporal_client
        clock_data = await clock_svc.get_clock(temporal_client, db)
        clock_time = clock_data.current_time
    except Exception:
        pass

    # Base context for all dashboards
    context = {
        "request": request,
        "user": user,
        "role": role,
        "role_display": role_display,
        "clock_time": clock_time,
    }

    # Role-specific data loading
    if role == "admin":
        context["status"] = await admin_svc.get_status(db)
        context["missions"] = await mission_svc.list_missions(db)

    elif role == "nasa-program-manager":
        missions = await mission_svc.list_missions(db)
        context["missions"] = missions
        mission_tasks = {}
        for mission in missions:
            tasks = await mission_svc.get_mission_tasks(db, mission.id)
            mission_tasks[mission.id] = tasks
        context["mission_tasks"] = mission_tasks

    elif role == "nasa-tech-authority":
        missions = await mission_svc.list_missions(db)
        context["missions"] = missions
        # Collect review tasks across all missions
        review_tasks = []
        for mission in missions:
            tasks = await mission_svc.get_mission_tasks(
                db, mission.id, assigned_role="nasa-tech-authority"
            )
            review_tasks.extend(tasks)
        context["review_tasks"] = review_tasks

    elif role == "nasa-contracts-officer":
        missions = await mission_svc.list_missions(db)
        context["missions"] = missions
        contract_tasks = []
        for mission in missions:
            tasks = await mission_svc.get_mission_tasks(
                db, mission.id, assigned_role="nasa-contracts-officer"
            )
            contract_tasks.extend(tasks)
        context["contract_tasks"] = contract_tasks
        context["contractors"] = await contractor_svc.list_contractors(db)

    elif role == "contractor-pm":
        missions = await mission_svc.list_missions(db)
        context["missions"] = missions
        pm_tasks = []
        for mission in missions:
            tasks = await mission_svc.get_mission_tasks(
                db, mission.id, assigned_role="contractor-pm"
            )
            pm_tasks.extend(tasks)
        context["pm_tasks"] = pm_tasks

    elif role == "contractor-engineer":
        missions = await mission_svc.list_missions(db)
        context["missions"] = missions
        eng_tasks = []
        for mission in missions:
            tasks = await mission_svc.get_mission_tasks(
                db, mission.id, assigned_role="contractor-engineer"
            )
            eng_tasks.extend(tasks)
        context["tasks"] = eng_tasks

    elif role == "egs-ground-ops":
        context["facilities"] = await facility_svc.list_facilities(db)
        missions = await mission_svc.list_missions(db)
        context["missions"] = missions
        delivery_tasks = []
        for mission in missions:
            tasks = await mission_svc.get_mission_tasks(
                db, mission.id, phase="DELIVERY"
            )
            delivery_tasks.extend(tasks)
        context["delivery_tasks"] = delivery_tasks

    return templates.TemplateResponse(template_name, context)
