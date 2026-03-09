from fastapi import HTTPException, Request

from artemis.auth.keycloak import VALID_ROLES, UserInfo


def get_dev_user(request: Request) -> UserInfo:
    """Extract user info from dev bypass headers.

    Requires X-Simulation-Role header. X-Simulation-Org defaults to 'nasa'.
    Raises HTTP 400 if the role is not recognized.
    """
    role = request.headers.get("X-Simulation-Role")
    if role is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "AUTH_DISABLED mode requires X-Simulation-Role header. "
                f"Valid roles: {sorted(VALID_ROLES)}"
            ),
        )

    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown role: '{role}'. Valid roles: {sorted(VALID_ROLES)}",
        )

    org = request.headers.get("X-Simulation-Org", "nasa")

    return UserInfo(
        sub="dev-user",
        username="dev",
        email="dev@artemis.test",
        roles=[role],
        organization=org,
    )
