from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware
from temporalio.client import Client

from artemis.api import admin, clock, contractors, facilities, invoices, missions, scheduling, tasks
from artemis.config import get_settings
from artemis.database import engine
from artemis.events import event_bus
from artemis.templating import templates  # noqa: F401 — re-export for backwards compat

APP_DIR = Path(__file__).parent


async def _ensure_system_workflows(client: Client, settings) -> None:
    """Start long-lived system workflows if not already running."""
    from datetime import datetime, timezone

    from temporalio.client import WorkflowExecutionStatus
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

    async def _is_running(workflow_id: str) -> bool:
        """Check if a workflow is actually running (not terminated/completed)."""
        try:
            handle = client.get_workflow_handle(workflow_id)
            desc = await handle.describe()
            return desc.status == WorkflowExecutionStatus.RUNNING
        except RPCError:
            return False

    # Start clock workflow
    if not await _is_running(CLOCK_WORKFLOW_ID):
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
        if not await _is_running(wf_id):
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
    app.state.event_bus = event_bus

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

# Session middleware (signed cookies for browser auth)
settings = get_settings()
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

# CORS
_cors_origins = [
    settings.base_url,
    settings.keycloak_url,
]
if settings.cors_origins:
    _cors_origins.extend(o.strip() for o in settings.cors_origins.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

# REST API routers
app.include_router(missions.router, prefix="/api/v1/missions", tags=["missions"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(contractors.router, prefix="/api/v1/contractors", tags=["contractors"])
app.include_router(facilities.router, prefix="/api/v1/facilities", tags=["facilities"])
app.include_router(clock.router, prefix="/api/v1/clock", tags=["clock"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(invoices.router, prefix="/api/v1", tags=["invoices"])
app.include_router(scheduling.router, prefix="/api/v1", tags=["scheduling"])

# Browser view routes
from artemis.views import register_view_routes  # noqa: E402

register_view_routes(app)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
