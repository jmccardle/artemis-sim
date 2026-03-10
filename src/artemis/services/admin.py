"""Admin service functions — shared by API routers and view routes."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models import Contractor, Facility, Mission, SimulatedClock, Task, TaskArtifact
from artemis.seed.contractors import seed_contractors
from artemis.seed.facilities import seed_facilities


class ResetResult:
    def __init__(self, status: str, timestamp: datetime):
        self.status = status
        self.timestamp = timestamp


class StatusResult:
    def __init__(
        self,
        simulated_time: datetime | None,
        mission_count: int,
        task_count: int,
        facility_count: int,
        contractor_count: int,
        temporal_connected: bool,
    ):
        self.simulated_time = simulated_time
        self.mission_count = mission_count
        self.task_count = task_count
        self.facility_count = facility_count
        self.contractor_count = contractor_count
        self.temporal_connected = temporal_connected


async def reset_simulation(db: AsyncSession, username: str, reason: str) -> ResetResult:
    # Truncate all application tables (order matters for FK constraints)
    await db.execute(delete(TaskArtifact))
    await db.execute(delete(Task))
    await db.execute(delete(Mission))
    await db.execute(delete(SimulatedClock))
    await db.execute(delete(Contractor))
    await db.execute(delete(Facility))

    # Re-seed contractors and facilities
    await seed_contractors(db)
    await seed_facilities(db)

    # Initialize simulated clock
    clock = SimulatedClock(current_time=datetime.now(timezone.utc))
    db.add(clock)

    await db.commit()

    return ResetResult(
        status=f"Simulation reset by {username}: {reason}",
        timestamp=datetime.now(timezone.utc),
    )


async def seed_scenario(
    db: AsyncSession, scenario_name: str, username: str
) -> ResetResult:
    known_scenarios = {"clean"}
    if scenario_name not in known_scenarios:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_name}' is not yet implemented. Available: {sorted(known_scenarios)}",
        )

    if scenario_name == "clean":
        return await reset_simulation(db, username, f"seed scenario: {scenario_name}")

    # Unreachable given the check above, but explicit for clarity
    raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_name}")


async def get_status(db: AsyncSession) -> StatusResult:
    mission_count = (await db.execute(select(func.count(Mission.id)))).scalar() or 0
    task_count = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    facility_count = (await db.execute(select(func.count(Facility.id)))).scalar() or 0
    contractor_count = (await db.execute(select(func.count(Contractor.id)))).scalar() or 0

    clock_result = await db.execute(select(SimulatedClock).limit(1))
    clock = clock_result.scalar_one_or_none()

    return StatusResult(
        simulated_time=clock.current_time if clock else None,
        mission_count=mission_count,
        task_count=task_count,
        facility_count=facility_count,
        contractor_count=contractor_count,
        temporal_connected=False,
    )
