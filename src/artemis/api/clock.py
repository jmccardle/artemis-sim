from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import ClockAdvanceRequest, ClockResponse
from artemis.auth.dependencies import require_role
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.services import clock as clock_svc

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
    data = await clock_svc.get_clock(request.app.state.temporal_client, db)
    return ClockResponse(current_time=data.current_time, last_advance_reason=data.last_advance_reason)


@router.post("/advance", response_model=ClockResponse)
async def advance_clock(
    body: ClockAdvanceRequest,
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    data = await clock_svc.advance_clock(
        request.app.state.temporal_client, db, body.duration_seconds, body.reason
    )
    return ClockResponse(current_time=data.current_time, last_advance_reason=data.last_advance_reason)
