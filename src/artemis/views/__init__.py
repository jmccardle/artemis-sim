"""Browser view routes — Jinja2/HTMX frontend that consumes the service layer."""

from fastapi import FastAPI


def register_view_routes(app: FastAPI) -> None:
    """Mount all browser-facing view routers on the app."""
    from artemis.views.auth_views import router as auth_router
    from artemis.views.dashboard import router as dashboard_router
    from artemis.views.events import router as events_router
    from artemis.views.partials import router as partials_router
    from artemis.views.actions import router as actions_router
    from artemis.views.contractor_portal import router as contractor_portal_router

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(events_router, prefix="/views")
    app.include_router(partials_router, prefix="/views")
    app.include_router(actions_router, prefix="/views")
    app.include_router(contractor_portal_router)
