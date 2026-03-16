"""Scheduling API — available work, blocking analysis, critical path."""

import uuid
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import (
    AvailableWorkResponse,
    BlockingAnalysisResponse,
    CriticalPathResponse,
    WorkSuggestionsResponse,
)
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.services import scheduling as scheduling_svc

router = APIRouter()


@router.get(
    "/missions/{mission_id}/available-work",
    response_model=list[AvailableWorkResponse],
)
async def get_available_work(
    mission_id: uuid.UUID,
    role: Optional[str] = Query(None, description="Filter by assigned role"),
    contractor: Optional[str] = Query(None, description="Filter by contractor"),
    facility: Optional[str] = Query(None, description="Filter by facility"),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[AvailableWorkResponse]:
    items = await scheduling_svc.get_available_work(
        db,
        mission_id=mission_id,
        role=role,
        contractor=contractor,
        facility=facility,
    )
    return [AvailableWorkResponse(**asdict(item)) for item in items]


@router.get(
    "/tasks/{task_id}/blocking-analysis",
    response_model=BlockingAnalysisResponse,
)
async def get_blocking_analysis(
    task_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> BlockingAnalysisResponse:
    result = await scheduling_svc.get_blocking_analysis(db, task_id)
    return BlockingAnalysisResponse(**asdict(result))


@router.get(
    "/missions/{mission_id}/work-suggestions",
    response_model=WorkSuggestionsResponse,
)
async def get_work_suggestions(
    mission_id: uuid.UUID,
    role: str = Query(..., description="Role to find suggestions for"),
    blocked_task_id: Optional[uuid.UUID] = Query(
        None, description="Task ID that is currently blocked"
    ),
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorkSuggestionsResponse:
    result = await scheduling_svc.get_work_suggestions(
        db,
        mission_id=mission_id,
        role=role,
        blocked_task_id=blocked_task_id,
    )
    return WorkSuggestionsResponse(
        available_same_mission=[
            AvailableWorkResponse(**asdict(item))
            for item in result.available_same_mission
        ],
        available_other_missions=[
            AvailableWorkResponse(**asdict(item))
            for item in result.available_other_missions
        ],
    )


@router.get(
    "/missions/{mission_id}/critical-path",
    response_model=CriticalPathResponse,
)
async def get_critical_path(
    mission_id: uuid.UUID,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> CriticalPathResponse:
    result = await scheduling_svc.compute_critical_path(db, mission_id)
    return CriticalPathResponse(**asdict(result))
