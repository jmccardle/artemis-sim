# Keycloak: Development vs Production

## Development (docker-compose)

A local Keycloak instance runs in `start-dev` mode:

| Setting | Value |
|---|---|
| Image | `quay.io/keycloak/keycloak:26.0` |
| URL | `http://localhost:8180` |
| Admin console | `http://localhost:8180/admin` (admin/admin) |
| Realm | `artemis-sim` (auto-imported from `docker/keycloak/realm-export.json`) |
| TLS | Disabled (`sslRequired: none`, `start-dev` mode) |
| Client | `artemis-app` — public client, direct access grants enabled |
| Users | Pre-seeded (one per role, password: `password`) |
| Token endpoint | `http://localhost:8180/realms/artemis-sim/protocol/openid-connect/token` |
| JWKS endpoint | `http://localhost:8180/realms/artemis-sim/protocol/openid-connect/certs` |
| OIDC discovery | `http://localhost:8180/realms/artemis-sim/.well-known/openid-configuration` |

### Quick token test

```bash
# Get a token for the admin user
curl -s -X POST http://localhost:8180/realms/artemis-sim/protocol/openid-connect/token \
  -d 'grant_type=password&client_id=artemis-app&username=admin&password=password' \
  | python -m json.tool

# Use it
TOKEN=$(curl -s -X POST http://localhost:8180/realms/artemis-sim/protocol/openid-connect/token \
  -d 'grant_type=password&client_id=artemis-app&username=admin&password=password' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/admin/status
```

### Dev bypass mode

Set `ARTEMIS_AUTH_DISABLED=true` to skip Keycloak entirely:

```bash
curl -H "X-Simulation-Role: admin" -H "X-Simulation-Org: nasa" \
  http://localhost:8000/api/v1/admin/status
```

---

## Production (K3s — External Keycloak)

The K3s deployment connects to an existing enterprise Keycloak instance.

| Setting | Difference from dev |
|---|---|
| Keycloak URL | External (e.g., `https://keycloak.example.com`) — not deployed in cluster |
| TLS | Required (`sslRequired: external` or `all`) |
| Client | May be **confidential** (with client secret) depending on enterprise policy |
| Redirect URIs | Must match the production ingress URL |
| Web origins | Must match the production ingress URL |
| Users | Managed by enterprise IdP (LDAP/AD federation, not pre-seeded) |
| Token issuer | Different from dev — JWKS URI and issuer in JWT change |
| Admin console | Managed by enterprise Keycloak admins |

### What must be configured in the external Keycloak

1. **Realm**: `artemis-sim` (or use an existing realm with the roles below)
2. **Client**: `artemis-app` with:
   - Standard flow enabled (authorization code)
   - Direct access grants enabled (for CLI/API usage — optional, depends on security policy)
   - Redirect URIs: `https://<ingress-host>/*`
   - Web origins: `https://<ingress-host>`
3. **Realm roles**: The 7 simulation roles must exist:
   - `nasa-program-manager`, `nasa-tech-authority`, `nasa-contracts-officer`
   - `contractor-pm`, `contractor-engineer`
   - `egs-ground-ops`, `admin`
4. **Protocol mappers** on the client:
   - **Realm roles mapper**: Maps realm roles to `realm_roles` claim in JWT (multivalued string)
   - **Organization attribute mapper**: Maps user attribute `organization` to JWT claim `organization`
5. **Users**: Assign realm roles and set `organization` attribute per user

### Application configuration changes for production

```yaml
# K8s ConfigMap values
ARTEMIS_KEYCLOAK_URL: "https://keycloak.example.com"
ARTEMIS_KEYCLOAK_REALM: "artemis-sim"
ARTEMIS_KEYCLOAK_CLIENT_ID: "artemis-app"
ARTEMIS_AUTH_DISABLED: "false"

# K8s Secret (only if confidential client)
ARTEMIS_KEYCLOAK_CLIENT_SECRET: "<secret>"
```

### Key differences to handle in code

| Concern | Dev | Production |
|---|---|---|
| OIDC discovery URL | `http://localhost:8180/realms/artemis-sim/...` | `https://keycloak.example.com/realms/artemis-sim/...` |
| JWT issuer claim | `http://localhost:8180/realms/artemis-sim` | `https://keycloak.example.com/realms/artemis-sim` |
| Token validation | Audience check: `artemis-app` | Same |
| Client auth | No client secret (public) | May need client secret in token exchange |
| TLS verification | Disabled / not applicable | Must verify TLS certificates |

The application handles all of these through the `ARTEMIS_KEYCLOAK_URL` setting — the
OIDC discovery document provides the correct JWKS URI, issuer, and token endpoints
automatically. No code changes required between environments.
