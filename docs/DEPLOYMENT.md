# Deployment Guide

Two deployment paths: **docker-compose** for local development, **K3s** for a
cluster demo. Both use the same application image and Keycloak realm config.

---

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- For K3s path: a running K3s cluster, `kubectl`, and `helm` (optional)

---

## Option A: Local Development (docker-compose)

Start the infrastructure (PostgreSQL, Temporal, Keycloak):

```bash
docker compose up -d
```

Set up the application:

```bash
cp .env.example .env          # edit LLM settings for your setup
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn artemis.main:app --reload
```

Services:

| Service | URL |
|---|---|
| Artemis app | http://localhost:8000 |
| Temporal UI | http://localhost:8080 |
| Keycloak admin | http://localhost:8180/admin (admin / admin) |

All Keycloak test users share password `password`. See [KEYCLOAK.md](KEYCLOAK.md)
for the full user list and token examples.

To skip Keycloak during development, set `ARTEMIS_AUTH_DISABLED=true` in `.env`
and pass roles via headers:

```bash
curl -H "X-Simulation-Role: admin" -H "X-Simulation-Org: nasa" \
  http://localhost:8000/api/v1/admin/status
```

---

## Option B: K3s Cluster

### 1. Set up the in-cluster container registry

```bash
kubectl apply -f k8s/registry/registry.yaml
sudo ./scripts/setup-registry.sh           # auto-detects node IP
# or: sudo ./scripts/setup-registry.sh 10.0.0.5
```

This creates a registry at `registry.local:30500` (NodePort). The setup script
adds `/etc/hosts` entries, configures K3s containerd mirrors, and sets Docker's
insecure-registries.

### 2. Create namespaces

```bash
kubectl create namespace artemis
kubectl create namespace keycloak
```

### 3. Deploy infrastructure

```bash
# Keycloak + its PostgreSQL
kubectl apply -f k8s/keycloak/postgres.yaml
kubectl apply -f k8s/keycloak/keycloak.yaml

# Temporal + its PostgreSQL
kubectl apply -f k8s/artemis/temporal.yaml
kubectl apply -f k8s/artemis/postgres.yaml
```

### 4. Configure and deploy the application

Edit `k8s/artemis/configmap.yaml`:
- Set `ARTEMIS_LLM_BASE_URL` to your LLM inference server
- Verify `ARTEMIS_KEYCLOAK_URL` matches your Keycloak ingress

Edit `k8s/artemis/app.yaml`:
- Replace `YOUR_NODE_IP` in `hostAliases` with the node IP where Keycloak's
  ingress resolves

Edit `k8s/artemis/secret.yaml`:
- Set `session-secret` to a random value (`openssl rand -hex 32`)
- Set `llm-api-key` if using OpenAI/Anthropic

Deploy:

```bash
./scripts/deploy.sh --migrate
```

### 5. Ingress and /etc/hosts

The manifests use Traefik (K3s default) with these hostnames:

| Hostname | Service |
|---|---|
| `artemis.local` | Artemis web app |
| `temporal.local` | Temporal UI |
| `keycloak.local` | Keycloak |

Add entries to `/etc/hosts` on any machine that needs to reach them:

```
<NODE_IP>  artemis.local temporal.local keycloak.local
```

---

## Using GitHub Container Registry (ghcr.io) instead

If you prefer ghcr.io over a local registry, skip the registry setup and
override the `REGISTRY` variable:

```bash
# Build + push
REGISTRY=ghcr.io/yourorg ./scripts/deploy.sh --migrate
```

You'll also need to update the `image:` lines in `k8s/artemis/app.yaml` and
`k8s/artemis/worker.yaml` to `ghcr.io/yourorg/artemis-sim:latest`, and ensure
the cluster has pull access (imagePullSecrets or public repo).

---

## Credentials Summary

All credentials below are **dev defaults** for local/demo use. Replace them
for any internet-facing deployment.

| Component | Location | Default |
|---|---|---|
| App PostgreSQL | docker-compose.yml, k8s/artemis/postgres.yaml | artemis / artemis |
| Temporal PostgreSQL | docker-compose.yml, k8s/artemis/temporal.yaml | temporal / temporal |
| Keycloak PostgreSQL | k8s/keycloak/postgres.yaml | keycloak / keycloak |
| Keycloak admin | docker-compose.yml, k8s/keycloak/keycloak.yaml | admin / admin |
| Keycloak test users | docker/keycloak/realm-export.json | password |
| Session signing key | k8s/artemis/secret.yaml | `change-me` |
