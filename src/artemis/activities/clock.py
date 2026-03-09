"""Activities for the SimulatedClockWorkflow."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from temporalio import activity


@dataclass
class PersistClockInput:
    current_time_iso: str
    reason: str


@activity.defn
async def persist_clock_state(input: PersistClockInput) -> None:
    """Write the current clock state to the database."""
    from sqlalchemy import select

    from artemis.database import async_session_factory
    from artemis.models.clock import SimulatedClock

    new_time = datetime.fromisoformat(input.current_time_iso)

    async with async_session_factory() as session:
        result = await session.execute(select(SimulatedClock).limit(1))
        clock = result.scalar_one_or_none()

        if clock:
            clock.current_time = new_time
            clock.last_advance_reason = input.reason
        else:
            clock = SimulatedClock(
                current_time=new_time,
                last_advance_reason=input.reason,
            )
            session.add(clock)

        await session.commit()
