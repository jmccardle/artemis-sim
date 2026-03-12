import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import (
    InjectAction,
    InjectRequest,
    ResetRequest,
    ResetResponse,
    SimulationStatusResponse,
)
from artemis.auth.dependencies import require_role
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.services import admin as admin_svc

router = APIRouter()


async def _terminate_all_workflows(client) -> int:
    """Terminate all running workflows via list_workflows query."""
    from temporalio.client import WorkflowExecutionStatus

    terminated = 0
    async for wf in client.list_workflows('ExecutionStatus="Running"'):
        try:
            handle = client.get_workflow_handle(wf.id, run_id=wf.run_id)
            await handle.terminate(reason="Simulation reset")
            terminated += 1
        except Exception:
            pass
    return terminated


@router.post("/reset", response_model=ResetResponse)
async def reset_simulation(
    body: ResetRequest,
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Must confirm reset with confirm=true")

    from artemis.main import _ensure_system_workflows

    client = request.app.state.temporal_client

    # Terminate ALL running workflows (query-based, future-proof)
    await _terminate_all_workflows(client)

    result = await admin_svc.reset_simulation(db, user.username, body.reason)

    # Restart system workflows with fresh state
    await _ensure_system_workflows(client, request.app.state.settings)

    return ResetResponse(status=result.status, timestamp=result.timestamp)


@router.post("/seed/{scenario_name}", response_model=ResetResponse)
async def seed_scenario(
    scenario_name: str,
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    # For estes-mid-delivery, terminate workflows first
    if scenario_name == "estes-mid-delivery":
        from artemis.main import _ensure_system_workflows
        client = request.app.state.temporal_client
        await _terminate_all_workflows(client)
        result = await admin_svc.seed_scenario(db, scenario_name, user.username)
        await _ensure_system_workflows(client, request.app.state.settings)
        return ResetResponse(status=result.status, timestamp=result.timestamp)

    result = await admin_svc.seed_scenario(db, scenario_name, user.username)
    return ResetResponse(status=result.status, timestamp=result.timestamp)


@router.post("/inject")
async def inject_actions(
    body: InjectRequest,
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    """Execute admin data injection actions.

    Each action fails immediately on error (no partial execution, per "Fail Early").
    """
    from artemis.models.contractor import Contractor
    from artemis.services import clock as clock_svc
    from artemis.services import missions as mission_svc
    from artemis.services import tasks as task_svc
    from sqlalchemy import select

    client = request.app.state.temporal_client
    results = []

    for action in body.actions:
        if action.type == "complete_task":
            if action.task_id is None:
                raise HTTPException(status_code=400, detail="complete_task requires task_id")
            task = await task_svc.complete_task(db, client, action.task_id, user.username)
            results.append({"type": "complete_task", "task_id": str(task.id), "status": task.status})

            if action.advance_clock and action.duration_hours:
                await clock_svc.advance_clock(
                    client, db,
                    int(action.duration_hours * 3600),
                    f"Admin inject: complete_task {task.id}",
                )

        elif action.type == "fail_task":
            if action.task_id is None:
                raise HTTPException(status_code=400, detail="fail_task requires task_id")
            task = await task_svc.fail_task(db, client, action.task_id, user.username)
            results.append({"type": "fail_task", "task_id": str(task.id), "status": task.status})

        elif action.type == "advance_clock":
            if action.duration_hours is None:
                raise HTTPException(status_code=400, detail="advance_clock requires duration_hours")
            clock_data = await clock_svc.advance_clock(
                client, db,
                int(action.duration_hours * 3600),
                action.failure_reason or "Admin inject",
            )
            results.append({"type": "advance_clock", "current_time": clock_data.current_time.isoformat()})

        elif action.type == "create_mission":
            name = action.name or "Injected Mission"
            arch = action.architecture or "estes"
            mission = await mission_svc.create_mission(db, client, name, arch)
            results.append({"type": "create_mission", "mission_id": str(mission.id)})

        elif action.type == "set_contractor_reliability":
            if action.contractor_slug is None or action.reliability is None:
                raise HTTPException(
                    status_code=400,
                    detail="set_contractor_reliability requires contractor_slug and reliability",
                )
            result = await db.execute(
                select(Contractor).where(Contractor.slug == action.contractor_slug)
            )
            contractor = result.scalar_one_or_none()
            if contractor is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Contractor '{action.contractor_slug}' not found",
                )
            contractor.reliability = action.reliability
            await db.commit()
            results.append({
                "type": "set_contractor_reliability",
                "contractor": action.contractor_slug,
                "reliability": action.reliability,
            })

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown inject action type: {action.type}",
            )

    return {"status": "ok", "results": results}


@router.get("/status", response_model=SimulationStatusResponse)
async def simulation_status(
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    client = request.app.state.temporal_client
    result = await admin_svc.get_status(db, temporal_client=client)
    return SimulationStatusResponse(
        simulated_time=result.simulated_time,
        mission_count=result.mission_count,
        task_count=result.task_count,
        facility_count=result.facility_count,
        contractor_count=result.contractor_count,
        temporal_connected=result.temporal_connected,
    )


@router.post("/test-workflow")
async def test_workflow(
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
):
    """Run the hello-world workflow to verify Temporal connectivity."""
    from artemis.workflows.hello import HelloWorkflow

    client = request.app.state.temporal_client
    handle = await client.start_workflow(
        HelloWorkflow.run,
        "Artemis",
        id=f"hello-{uuid.uuid4()}",
        task_queue=request.app.state.settings.temporal_task_queue,
    )
    result = await handle.result()
    return {"workflow_id": handle.id, "result": result}
