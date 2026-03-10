"""Facility service functions — shared by API routers and view routes."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models.facility import Facility


async def list_facilities(db: AsyncSession) -> list[Facility]:
    result = await db.execute(select(Facility).order_by(Facility.name))
    return list(result.scalars().all())
