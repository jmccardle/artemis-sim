"""Contractor service functions — shared by API routers and view routes."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models.contractor import Contractor


async def list_contractors(db: AsyncSession) -> list[Contractor]:
    result = await db.execute(select(Contractor).order_by(Contractor.name))
    return list(result.scalars().all())


async def get_contractor(db: AsyncSession, slug: str) -> Contractor:
    result = await db.execute(select(Contractor).where(Contractor.slug == slug))
    contractor = result.scalar_one_or_none()
    if contractor is None:
        raise HTTPException(status_code=404, detail=f"Contractor '{slug}' not found")
    return contractor
