"""View helpers — session-based auth for browser routes."""

from fastapi import HTTPException, Request
from starlette.responses import RedirectResponse

from artemis.auth.keycloak import VALID_ROLES, UserInfo
from artemis.config import get_settings


def get_session_user(request: Request) -> UserInfo | None:
    """Extract user info from the session cookie. Returns None if not logged in."""
    session = request.session
    user_data = session.get("user")
    if user_data is None:
        return None
    return UserInfo(**user_data)


def require_browser_auth(request: Request) -> UserInfo:
    """Get the logged-in user or redirect to login."""
    user = get_session_user(request)
    if user is None:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


ROLE_DISPLAY_NAMES = {
    "admin": "Administrator",
    "nasa-program-manager": "NASA Program Manager",
    "nasa-tech-authority": "NASA Technical Authority",
    "nasa-contracts-officer": "NASA Contracts Officer",
    "contractor-pm": "Contractor PM",
    "contractor-engineer": "Contractor Engineer",
    "egs-ground-ops": "Ground Operations",
}
