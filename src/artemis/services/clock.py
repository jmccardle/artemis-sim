"""Clock service functions — shared by API routers and view routes."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.service import RPCError, RPCStatusCode

from artemis.models.clock import SimulatedClock
from artemis.workflows.clock import AdvanceTimeInput, CLOCK_WORKFLOW_ID, SimulatedClockWorkflow


class ClockData:
    """Simple container for clock query results."""

    def __init__(self, current_time: datetime, last_advance_reason: str | None = None):
        self.current_time = current_time
        self.last_advance_reason = last_advance_reason


async def get_clock(temporal_client: Client, db: AsyncSession) -> ClockData:
    # Try workflow first
    try:
        handle = temporal_client.get_workflow_handle(CLOCK_WORKFLOW_ID)
        time_iso = await handle.query(SimulatedClockWorkflow.get_current_time)
        return ClockData(
            current_time=datetime.fromisoformat(time_iso),
            last_advance_reason=None,
        )
    except RPCError as e:
        if e.status != RPCStatusCode.NOT_FOUND:
            raise

    # Fall back to DB
    result = await db.execute(select(SimulatedClock).limit(1))
    clock = result.scalar_one_or_none()
    if clock is None:
        raise HTTPException(
            status_code=404, detail="Simulated clock not initialized. Run admin/seed first."
        )
    return ClockData(current_time=clock.current_time, last_advance_reason=clock.last_advance_reason)


async def advance_clock(
    temporal_client: Client,
    db: AsyncSession,
    duration_seconds: int,
    reason: str,
) -> ClockData:
    try:
        handle = temporal_client.get_workflow_handle(CLOCK_WORKFLOW_ID)
        await handle.signal(
            SimulatedClockWorkflow.advance_time,
            AdvanceTimeInput(seconds=duration_seconds, reason=reason),
        )
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            raise HTTPException(
                status_code=409,
                detail="Clock workflow not running. Start it via admin/seed first.",
            )
        raise

    time_iso = await handle.query(SimulatedClockWorkflow.get_current_time)
    return ClockData(
        current_time=datetime.fromisoformat(time_iso),
        last_advance_reason=reason,
    )
