from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer

from artemis.auth.dev_bypass import get_dev_user
from artemis.auth.keycloak import KeycloakTokenValidator, UserInfo, extract_user_info
from artemis.config import Settings, get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

_validator: KeycloakTokenValidator | None = None


def _get_validator() -> KeycloakTokenValidator:
    global _validator
    if _validator is None:
        _validator = KeycloakTokenValidator()
    return _validator


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    settings: Settings = Depends(get_settings),
) -> UserInfo:
    """Resolve the current user from either Keycloak JWT or dev bypass headers."""
    if settings.auth_disabled:
        return get_dev_user(request)

    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        validator = _get_validator()
        claims = validator.validate_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return extract_user_info(claims)


def require_role(*roles: str) -> Callable:
    """FastAPI dependency that requires the user to have at least one of the specified roles."""

    async def _check(user: UserInfo = Depends(get_current_user)) -> UserInfo:
        if not any(r in user.roles for r in roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of roles: {list(roles)}. User has: {user.roles}",
            )
        return user

    return _check
