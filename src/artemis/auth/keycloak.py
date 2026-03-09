import jwt
from pydantic import BaseModel

from artemis.config import get_settings

VALID_ROLES = frozenset({
    "nasa-program-manager",
    "nasa-tech-authority",
    "nasa-contracts-officer",
    "contractor-pm",
    "contractor-engineer",
    "egs-ground-ops",
    "admin",
})


class UserInfo(BaseModel):
    sub: str
    username: str
    email: str
    roles: list[str]
    organization: str


class KeycloakTokenValidator:
    def __init__(self) -> None:
        settings = get_settings()
        self._jwks_client = jwt.PyJWKClient(
            settings.keycloak_jwks_url,
            cache_jwk_set=True,
            lifespan=300,
        )
        self._issuer = settings.keycloak_issuer_url
        self._client_id = settings.keycloak_client_id

    def validate_token(self, token: str) -> dict:
        """Validate a JWT and return its claims.

        Keycloak 26 access tokens use 'azp' (authorized party) instead of 'aud'
        for the client identifier. We verify the issuer and signature via JWKS,
        then check azp matches our client_id.
        """
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=self._issuer,
            options={
                "verify_exp": True,
                "verify_aud": False,  # Keycloak access tokens may not have 'aud'
            },
        )

        # Verify authorized party matches our client
        azp = claims.get("azp")
        if azp != self._client_id:
            raise jwt.InvalidTokenError(
                f"Token azp '{azp}' does not match expected client '{self._client_id}'"
            )

        return claims


def extract_user_info(claims: dict) -> UserInfo:
    """Extract UserInfo from decoded JWT claims.

    Keycloak 26 access tokens may not include 'sub' — fall back to 'preferred_username'.
    """
    roles = claims.get("realm_roles", [])
    if isinstance(roles, str):
        roles = [roles]

    sub = claims.get("sub") or claims.get("preferred_username", "unknown")

    return UserInfo(
        sub=sub,
        username=claims.get("preferred_username", ""),
        email=claims.get("email", ""),
        roles=roles,
        organization=claims.get("organization", ""),
    )
