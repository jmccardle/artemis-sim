import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import (
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


@router.post("/reset", response_model=ResetResponse)
async def reset_simulation(
    body: ResetRequest,
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Must confirm reset with confirm=true")

    # Terminate running system workflows before DB reset
    from artemis.main import _ensure_system_workflows
    from artemis.workflows.data_types import CLOCK_WORKFLOW_ID, facility_workflow_id
    from temporalio.client import WorkflowExecutionStatus
    from temporalio.service import RPCError

    client = request.app.state.temporal_client
    for wf_id in [CLOCK_WORKFLOW_ID, facility_workflow_id("the-garage")]:
        try:
            handle = client.get_workflow_handle(wf_id)
            desc = await handle.describe()
            if desc.status == WorkflowExecutionStatus.RUNNING:
                await handle.terminate(reason="Simulation reset")
        except RPCError:
            pass

    result = await admin_svc.reset_simulation(db, user.username, body.reason)

    # Restart system workflows with fresh state
    await _ensure_system_workflows(client, request.app.state.settings)

    return ResetResponse(status=result.status, timestamp=result.timestamp)


@router.post("/seed/{scenario_name}", response_model=ResetResponse)
async def seed_scenario(
    scenario_name: str,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    result = await admin_svc.seed_scenario(db, scenario_name, user.username)
    return ResetResponse(status=result.status, timestamp=result.timestamp)


@router.post("/inject")
async def inject_actions(
    body: InjectRequest,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    raise HTTPException(
        status_code=501,
        detail="Data injection requires Temporal workflow signaling (Phase 1)",
    )


@router.get("/status", response_model=SimulationStatusResponse)
async def simulation_status(
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    result = await admin_svc.get_status(db)
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
