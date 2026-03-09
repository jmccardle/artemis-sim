from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import WorkflowNotFoundError

from artemis.api.schemas import ClockAdvanceRequest, ClockResponse
from artemis.auth.dependencies import require_role
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models.clock import SimulatedClock
from artemis.workflows.clock import AdvanceTimeInput, CLOCK_WORKFLOW_ID, SimulatedClockWorkflow

router = APIRouter()


@router.get("", response_model=ClockResponse)
async def get_clock(
    request: Request,
    user: UserInfo = Depends(require_role(
        "admin", "nasa-program-manager", "nasa-tech-authority",
        "nasa-contracts-officer", "contractor-pm", "contractor-engineer",
        "egs-ground-ops",
    )),
    db: AsyncSession = Depends(get_db_session),
):
    # Try to query the clock workflow first
    client = request.app.state.temporal_client
    try:
        handle = client.get_workflow_handle(CLOCK_WORKFLOW_ID)
        time_iso = await handle.query(SimulatedClockWorkflow.get_current_time)
        return ClockResponse(
            current_time=datetime.fromisoformat(time_iso),
            last_advance_reason=None,
        )
    except WorkflowNotFoundError:
        pass

    # Fall back to DB if workflow is not running
    result = await db.execute(select(SimulatedClock).limit(1))
    clock = result.scalar_one_or_none()
    if clock is None:
        raise HTTPException(status_code=404, detail="Simulated clock not initialized. Run admin/seed first.")
    return clock


@router.post("/advance", response_model=ClockResponse)
async def advance_clock(
    body: ClockAdvanceRequest,
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    client = request.app.state.temporal_client
    try:
        handle = client.get_workflow_handle(CLOCK_WORKFLOW_ID)
        await handle.signal(
            SimulatedClockWorkflow.advance_time,
            AdvanceTimeInput(seconds=body.duration_seconds, reason=body.reason),
        )
    except WorkflowNotFoundError:
        raise HTTPException(
            status_code=409,
            detail="Clock workflow not running. Start it via admin/seed first.",
        )

    # Query the updated time from the workflow
    time_iso = await handle.query(SimulatedClockWorkflow.get_current_time)
    return ClockResponse(
        current_time=datetime.fromisoformat(time_iso),
        last_advance_reason=body.reason,
    )
