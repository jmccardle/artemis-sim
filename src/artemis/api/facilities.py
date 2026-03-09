from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import FacilityResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models.facility import Facility

router = APIRouter()


@router.get("", response_model=list[FacilityResponse])
async def list_facilities(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Facility).order_by(Facility.name))
    return result.scalars().all()
