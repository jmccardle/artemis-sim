"""Activities for the FacilityManagerWorkflow."""
from __future__ import annotations

from dataclasses import dataclass

from temporalio import activity


@dataclass
class PersistFacilityInput:
    facility_name: str
    current_occupancy: int


@activity.defn
async def persist_facility_state(input: PersistFacilityInput) -> None:
    """Update facility occupancy in the database."""
    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.facility import Facility

    async with async_session_factory() as session:
        result = await session.execute(
            select(Facility).where(Facility.name == input.facility_name)
        )
        facility = result.scalar_one_or_none()

        if facility:
            facility.current_occupancy = input.current_occupancy
            await session.commit()
