from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from temporalio.client import Client

from artemis.api import admin, clock, contractors, facilities, missions, tasks
from artemis.config import get_settings
from artemis.database import engine

APP_DIR = Path(__file__).parent


async def _ensure_system_workflows(client: Client, settings) -> None:
    """Start long-lived system workflows if not already running."""
    from datetime import datetime, timezone

    from temporalio.service import RPCError

    from artemis.workflows.clock import (
        CLOCK_WORKFLOW_ID,
        ClockWorkflowInput,
        SimulatedClockWorkflow,
    )
    from artemis.workflows.facility_manager import (
        FacilityManagerWorkflow,
        FacilityWorkflowInput,
    )

    # Start clock workflow
    try:
        handle = client.get_workflow_handle(CLOCK_WORKFLOW_ID)
        await handle.describe()  # Check if running
    except RPCError:
        await client.start_workflow(
            SimulatedClockWorkflow.run,
            ClockWorkflowInput(
                initial_time_iso=datetime.now(timezone.utc).isoformat(),
            ),
            id=CLOCK_WORKFLOW_ID,
            task_queue=settings.temporal_orchestration_queue,
        )

    # Start facility workflows (MVP: just The Garage)
    mvp_facilities = [
        ("the-garage", "The Garage", 1),
    ]
    for slug, name, capacity in mvp_facilities:
        wf_id = f"facility-{slug}"
        try:
            handle = client.get_workflow_handle(wf_id)
            await handle.describe()
        except RPCError:
            await client.start_workflow(
                FacilityManagerWorkflow.run,
                FacilityWorkflowInput(slug=slug, name=name, capacity=capacity),
                id=wf_id,
                task_queue=settings.temporal_orchestration_queue,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings

    # Verify database connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))

    # Connect to Temporal
    app.state.temporal_client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    # Start system workflows (clock + facility managers)
    await _ensure_system_workflows(app.state.temporal_client, settings)

    yield

    await engine.dispose()


app = FastAPI(
    title="Artemis Mission Architecture Simulation",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:8080",  # Temporal UI
        "http://localhost:8180",  # Keycloak
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")

# REST API routers
app.include_router(missions.router, prefix="/api/v1/missions", tags=["missions"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(contractors.router, prefix="/api/v1/contractors", tags=["contractors"])
app.include_router(facilities.router, prefix="/api/v1/facilities", tags=["facilities"])
app.include_router(clock.router, prefix="/api/v1/clock", tags=["clock"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
