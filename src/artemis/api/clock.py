from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import ClockAdvanceRequest, ClockResponse
from artemis.auth.dependencies import require_role
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models.clock import SimulatedClock

router = APIRouter()


@router.get("", response_model=ClockResponse)
async def get_clock(
    user: UserInfo = Depends(require_role(
        "admin", "nasa-program-manager", "nasa-tech-authority",
        "nasa-contracts-officer", "contractor-pm", "contractor-engineer",
        "egs-ground-ops",
    )),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(SimulatedClock).limit(1))
    clock = result.scalar_one_or_none()
    if clock is None:
        raise HTTPException(status_code=404, detail="Simulated clock not initialized. Run admin/seed first.")
    return clock


@router.post("/advance", response_model=ClockResponse)
async def advance_clock(
    body: ClockAdvanceRequest,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    raise HTTPException(
        status_code=501,
        detail="Clock advancement via SimulatedClockWorkflow not yet implemented (Phase 1)",
    )
