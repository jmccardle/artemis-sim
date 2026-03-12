"""HTMX action endpoints — handle form submissions and return updated partials."""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.database import get_db_session
from artemis.events import Event, event_bus
from artemis.services import admin as admin_svc
from artemis.services import clock as clock_svc
from artemis.services import invoices as invoice_svc
from artemis.services import missions as mission_svc
from artemis.services import tasks as task_svc
from artemis.templating import templates
from artemis.views.helpers import get_session_user

router = APIRouter()


async def _get_kanban_response(
    request: Request, task, db: AsyncSession
) -> HTMLResponse:
    """After a task action, return the updated kanban board."""
    tasks = await mission_svc.get_mission_tasks(db, task.mission_id)
    return templates.TemplateResponse(
        "partials/kanban/board.html",
        {"request": request, "tasks": tasks, "mission_id": task.mission_id},
    )


@router.post("/tasks/{task_id}/complete", response_class=HTMLResponse)
async def complete_task_action(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    username = user.username if user else "anonymous"
    temporal_client = request.app.state.temporal_client
    task = await task_svc.complete_task(db, temporal_client, task_id, username)

    await event_bus.publish(Event(
        event_type="task-updated",
        data={"task_id": str(task_id), "status": task.status, "name": task.name},
    ))
    await event_bus.publish(Event(
        event_type="notification",
        data={"message": f"Task '{task.name}' completed", "type": "success"},
    ))

    return await _get_kanban_response(request, task, db)


@router.post("/tasks/{task_id}/fail", response_class=HTMLResponse)
async def fail_task_action(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    username = user.username if user else "anonymous"
    temporal_client = request.app.state.temporal_client
    task = await task_svc.fail_task(db, temporal_client, task_id, username)

    await event_bus.publish(Event(
        event_type="task-updated",
        data={"task_id": str(task_id), "status": task.status, "name": task.name},
    ))
    await event_bus.publish(Event(
        event_type="notification",
        data={"message": f"Task '{task.name}' failed", "type": "error"},
    ))

    return await _get_kanban_response(request, task, db)


@router.post("/tasks/{task_id}/advance", response_class=HTMLResponse)
async def advance_task_action(
    task_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    username = user.username if user else "anonymous"
    temporal_client = request.app.state.temporal_client
    task = await task_svc.advance_task(db, temporal_client, task_id, username)

    await event_bus.publish(Event(
        event_type="task-updated",
        data={"task_id": str(task_id), "status": task.status, "name": task.name},
    ))

    return await _get_kanban_response(request, task, db)


@router.post("/admin/reset", response_class=HTMLResponse)
async def reset_action(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    username = user.username if user else "admin"
    result = await admin_svc.reset_simulation(db, username, "Dashboard reset")

    await event_bus.publish(Event(
        event_type="notification",
        data={"message": "Simulation reset successfully", "type": "warning"},
    ))

    status = await admin_svc.get_status(db)
    return templates.TemplateResponse(
        "partials/admin/simulation_status.html",
        {"request": request, "status": status},
    )


@router.post("/admin/seed/{scenario_name}", response_class=HTMLResponse)
async def seed_action(
    scenario_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    user = get_session_user(request)
    username = user.username if user else "admin"
    await admin_svc.seed_scenario(db, scenario_name, username)

    status = await admin_svc.get_status(db)
    return templates.TemplateResponse(
        "partials/admin/simulation_status.html",
        {"request": request, "status": status},
    )


@router.post("/clock/advance", response_class=HTMLResponse)
async def advance_clock_action(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    form = await request.form()
    hours = int(form.get("hours", 1))
    reason = form.get("reason", "Manual advance")
    temporal_client = request.app.state.temporal_client

    clock_data = await clock_svc.advance_clock(temporal_client, db, hours * 3600, reason)

    await event_bus.publish(Event(
        event_type="clock-updated",
        data={"current_time": clock_data.current_time.isoformat()},
    ))

    return templates.TemplateResponse(
        "partials/shared/clock_display.html",
        {"request": request, "clock_time": clock_data.current_time},
    )


@router.post("/missions/create", response_class=HTMLResponse)
async def create_mission_action(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    form = await request.form()
    name = form.get("name", "New Mission")
    architecture = form.get("architecture_type", "estes")
    temporal_client = request.app.state.temporal_client

    mission = await mission_svc.create_mission(db, temporal_client, name, architecture)

    await event_bus.publish(Event(
        event_type="mission-updated",
        data={"mission_id": str(mission.id), "name": mission.name, "status": mission.status if isinstance(mission.status, str) else mission.status.value},
    ))
    await event_bus.publish(Event(
        event_type="notification",
        data={"message": f"Mission '{mission.name}' created", "type": "success"},
    ))

    # Return updated admin status
    status = await admin_svc.get_status(db)
    return templates.TemplateResponse(
        "partials/admin/simulation_status.html",
        {"request": request, "status": status},
    )


# ── Contractor Invoice Actions ───────────────────────────────────────

@router.post("/contractor/{slug}/invoices", response_class=HTMLResponse)
async def submit_invoice_action(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX: contractor submits an invoice."""
    form = await request.form()
    mission_id = uuid.UUID(form["mission_id"])
    amount = float(form["amount"])
    description = form.get("description", "")

    # Parse line items from text format ("desc | amount" per line)
    line_items = []
    raw = form.get("line_items_text", "")
    if raw:
        for line in raw.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) == 2:
                line_items.append({"description": parts[0], "amount": float(parts[1])})
            elif parts[0]:
                line_items.append({"description": parts[0], "amount": 0})

    invoice = await invoice_svc.create_invoice(
        db,
        contractor_slug=slug,
        mission_id=mission_id,
        amount=amount,
        description=description,
        line_items=line_items,
    )

    await event_bus.publish(Event(
        event_type="notification",
        data={"message": f"Invoice {invoice.invoice_number} submitted", "type": "success"},
    ))

    # Return updated invoice list
    invoices = await invoice_svc.list_invoices_for_contractor(db, slug)
    return templates.TemplateResponse(
        "partials/contractor/invoice_list.html",
        {"request": request, "invoices": invoices},
    )


# ── Contracts Officer Invoice Review Actions ─────────────────────────

@router.post("/invoices/{invoice_id}/review", response_class=HTMLResponse)
async def review_invoice_action(
    invoice_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """HTMX: contracts officer approves or rejects an invoice."""
    user = get_session_user(request)
    username = user.username if user else "contracts-officer"
    form = await request.form()
    action = form.get("action", "")  # "approve" or "reject"
    notes = form.get("notes", "")
    contractor_slug = form.get("contractor_slug", "")

    if action == "approve":
        new_status = "UNDER_REVIEW"
        # Two-step: SUBMITTED -> UNDER_REVIEW -> APPROVED
        # First move to UNDER_REVIEW, then to APPROVED
        inv = await invoice_svc.update_invoice_status(
            db, contractor_slug, invoice_id, "UNDER_REVIEW", username, notes
        )
        inv = await invoice_svc.update_invoice_status(
            db, contractor_slug, invoice_id, "APPROVED", username, notes
        )
        msg = f"Invoice {inv.invoice_number} approved"
        msg_type = "success"
    elif action == "reject":
        inv = await invoice_svc.update_invoice_status(
            db, contractor_slug, invoice_id, "UNDER_REVIEW", username, notes
        )
        inv = await invoice_svc.update_invoice_status(
            db, contractor_slug, invoice_id, "REJECTED", username, notes
        )
        msg = f"Invoice {inv.invoice_number} rejected"
        msg_type = "warning"
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown review action: {action}")

    await event_bus.publish(Event(
        event_type="notification",
        data={"message": msg, "type": msg_type},
    ))

    # Return updated pending invoices for contracts officer
    from artemis.services import contractors as contractor_svc
    pending = await invoice_svc.list_all_invoices(db, status="SUBMITTED")
    budget = await invoice_svc.get_budget_summary(db)
    contractors = await contractor_svc.list_contractors(db)
    return templates.TemplateResponse(
        "partials/contracts/invoice_review.html",
        {
            "request": request,
            "pending_invoices": pending,
            "budget": budget,
            "contractor_map": {str(c.id): c.slug for c in contractors},
            "contractor_name_map": {str(c.id): c.name for c in contractors},
        },
    )
