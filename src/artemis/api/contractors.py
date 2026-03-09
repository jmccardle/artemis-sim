from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import ContractorResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models.contractor import Contractor

router = APIRouter()


@router.get("", response_model=list[ContractorResponse])
async def list_contractors(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Contractor).order_by(Contractor.name))
    return result.scalars().all()


@router.get("/{slug}", response_model=ContractorResponse)
async def get_contractor(
    slug: str,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    result = await db.execute(select(Contractor).where(Contractor.slug == slug))
    contractor = result.scalar_one_or_none()
    if contractor is None:
        raise HTTPException(status_code=404, detail=f"Contractor '{slug}' not found")
    return contractor
