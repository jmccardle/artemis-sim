from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import ContractorResponse
from artemis.auth.dependencies import get_current_user
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.services import contractors as contractor_svc

router = APIRouter()


@router.get("", response_model=list[ContractorResponse])
async def list_contractors(
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await contractor_svc.list_contractors(db)


@router.get("/{slug}", response_model=ContractorResponse)
async def get_contractor(
    slug: str,
    user: UserInfo = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    return await contractor_svc.get_contractor(db, slug)
