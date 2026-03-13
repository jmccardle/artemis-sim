"""Browser authentication views — OIDC login/callback/logout + dev login."""

import logging
import secrets
import uuid

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from artemis.auth.keycloak import VALID_ROLES, UserInfo, extract_user_info
from artemis.config import get_settings
from artemis.templating import templates
from artemis.views.helpers import ROLE_DISPLAY_NAMES

logger = logging.getLogger(__name__)

router = APIRouter()


def _auth_error(request: Request, message: str, detail: str = "") -> HTMLResponse:
    """Render the auth error page instead of redirecting to /login (avoids loops)."""
    logger.warning("Auth error: %s — %s", message, detail)
    return templates.TemplateResponse(
        "auth/error.html",
        {"request": request, "message": message, "detail": detail},
        status_code=401,
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Redirect to Keycloak or show dev login form."""
    settings = get_settings()

    if settings.auth_disabled:
        return RedirectResponse(url="/dev/login", status_code=302)

    # OIDC authorization code flow
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    params = {
        "client_id": settings.keycloak_client_id,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": f"{settings.base_url}/auth/callback",
        "state": state,
    }
    authorize_url = settings.keycloak_authorize_url
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{authorize_url}?{query}", status_code=302)


@router.get("/auth/callback")
async def auth_callback(request: Request, code: str, state: str):
    """Exchange authorization code for tokens and create session."""
    settings = get_settings()

    # Verify state
    expected_state = request.session.get("oauth_state")
    if state != expected_state:
        return _auth_error(
            request,
            "OAuth state mismatch.",
            "The state parameter did not match. This can happen if your session "
            "expired or cookies were cleared during login. Try again.",
        )

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(verify=settings.verify_ssl) as client:
            token_response = await client.post(
                settings.keycloak_token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.keycloak_client_id,
                    "code": code,
                    "redirect_uri": f"{settings.base_url}/auth/callback",
                },
            )
    except Exception as exc:
        return _auth_error(
            request,
            "Could not reach the identity provider for token exchange.",
            f"{type(exc).__name__}: {exc}\n\nToken URL: {settings.keycloak_token_url}",
        )

    if token_response.status_code != 200:
        return _auth_error(
            request,
            "Token exchange failed.",
            f"Keycloak returned HTTP {token_response.status_code}:\n{token_response.text}",
        )

    tokens = token_response.json()
    access_token = tokens.get("access_token")

    if not access_token:
        return _auth_error(
            request,
            "No access token in Keycloak response.",
            f"Response keys: {list(tokens.keys())}",
        )

    # Decode and extract user info (validation via Keycloak JWKS)
    from artemis.auth.dependencies import _get_validator

    try:
        validator = _get_validator()
        claims = validator.validate_token(access_token)
        user_info = extract_user_info(claims)
    except Exception as exc:
        return _auth_error(
            request,
            "Token validation failed.",
            f"{type(exc).__name__}: {exc}\n\n"
            f"JWKS URL: {settings.keycloak_jwks_url}\n"
            f"Expected issuer: {settings.keycloak_issuer_url}",
        )

    # Store in session
    request.session["user"] = user_info.model_dump()
    request.session["access_token"] = access_token
    request.session.pop("oauth_state", None)

    return RedirectResponse(url="/", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Clear session and redirect to Keycloak logout."""
    settings = get_settings()
    request.session.clear()

    if settings.auth_disabled:
        return RedirectResponse(url="/login", status_code=302)

    logout_url = settings.keycloak_logout_url
    redirect_uri = f"{settings.base_url}/login"
    return RedirectResponse(
        url=f"{logout_url}?client_id={settings.keycloak_client_id}&post_logout_redirect_uri={redirect_uri}",
        status_code=302,
    )


@router.get("/dev/login", response_class=HTMLResponse)
async def dev_login_form(request: Request):
    """Show the dev role selector form."""
    settings = get_settings()
    if not settings.auth_disabled:
        return RedirectResponse(url="/login", status_code=302)

    roles = sorted(VALID_ROLES)
    return templates.TemplateResponse(
        "auth/dev_login.html",
        {
            "request": request,
            "roles": roles,
            "role_display_names": ROLE_DISPLAY_NAMES,
        },
    )


@router.post("/dev/login")
async def dev_login_submit(request: Request):
    """Process dev login form submission."""
    settings = get_settings()
    if not settings.auth_disabled:
        return RedirectResponse(url="/login", status_code=302)

    form = await request.form()
    role = form.get("role", "admin")
    org = form.get("organization", "nasa")

    if role not in VALID_ROLES:
        return RedirectResponse(url="/dev/login", status_code=302)

    # Determine org based on role
    if role.startswith("contractor"):
        org = org or "contractor-org"
    elif role.startswith("egs"):
        org = "egs"
    else:
        org = "nasa"

    user = UserInfo(
        sub=f"dev-{role}",
        username=f"dev-{role}",
        email=f"{role}@artemis.test",
        roles=[role],
        organization=org,
    )
    request.session["user"] = user.model_dump()

    return RedirectResponse(url="/", status_code=302)
