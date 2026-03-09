import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.api.schemas import (
    InjectRequest,
    ResetRequest,
    ResetResponse,
    SimulationStatusResponse,
)
from artemis.auth.dependencies import require_role
from artemis.auth.keycloak import UserInfo
from artemis.database import get_db_session
from artemis.models import (
    Contractor,
    Facility,
    Mission,
    SimulatedClock,
    Task,
    TaskArtifact,
)
from artemis.seed.contractors import seed_contractors
from artemis.seed.facilities import seed_facilities

router = APIRouter()


@router.post("/reset", response_model=ResetResponse)
async def reset_simulation(
    body: ResetRequest,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Must confirm reset with confirm=true")

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

    return ResetResponse(
        status=f"Simulation reset by {user.username}: {body.reason}",
        timestamp=datetime.now(timezone.utc),
    )


@router.post("/seed/{scenario_name}", response_model=ResetResponse)
async def seed_scenario(
    scenario_name: str,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    known_scenarios = {"clean"}  # Expand as we implement more
    if scenario_name not in known_scenarios:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_name}' is not yet implemented. Available: {sorted(known_scenarios)}",
        )

    if scenario_name == "clean":
        # Reset calls the same logic
        return await reset_simulation(
            ResetRequest(confirm=True, reason=f"seed scenario: {scenario_name}"),
            user=user,
            db=db,
        )


@router.post("/inject")
async def inject_actions(
    body: InjectRequest,
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    raise HTTPException(
        status_code=501,
        detail="Data injection requires Temporal workflow signaling (Phase 1)",
    )


@router.get("/status", response_model=SimulationStatusResponse)
async def simulation_status(
    user: UserInfo = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db_session),
):
    # Get counts from DB
    mission_count = (await db.execute(select(func.count(Mission.id)))).scalar() or 0
    task_count = (await db.execute(select(func.count(Task.id)))).scalar() or 0
    facility_count = (await db.execute(select(func.count(Facility.id)))).scalar() or 0
    contractor_count = (await db.execute(select(func.count(Contractor.id)))).scalar() or 0

    # Get simulated time
    clock_result = await db.execute(select(SimulatedClock).limit(1))
    clock = clock_result.scalar_one_or_none()

    return SimulationStatusResponse(
        simulated_time=clock.current_time if clock else None,
        mission_count=mission_count,
        task_count=task_count,
        facility_count=facility_count,
        contractor_count=contractor_count,
        temporal_connected=False,  # Will check actual connection in Phase 1
    )


@router.post("/test-workflow")
async def test_workflow(
    request: Request,
    user: UserInfo = Depends(require_role("admin")),
):
    """Run the hello-world workflow to verify Temporal connectivity."""
    from artemis.workflows.hello import HelloWorkflow

    client = request.app.state.temporal_client
    handle = await client.start_workflow(
        HelloWorkflow.run,
        "Artemis",
        id=f"hello-{uuid.uuid4()}",
        task_queue=request.app.state.settings.temporal_task_queue,
    )
    result = await handle.result()
    return {"workflow_id": handle.id, "result": result}
