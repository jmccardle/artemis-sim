# Development Roadmap

## Overview

Target: Deployable demo in K3s by end of week (5 working days).
Stack: Python + Temporal + FastAPI + HTMX + Keycloak + PostgreSQL + LLM compatibility layer.

**Key architectural constraints:**
- API-first: every operation available via REST with bearer token auth
- Keycloak SSO for authentication and role mapping
- Jinja2/HTMX frontend consumes the same REST API (not a privileged path)
- LLM costs managed by running locally; REST API enables cached/pre-generated inputs
- Admin API for simulation reset, scenario seeding, and data injection

---

## Phase 0: Foundation (Day 1, Morning)

**Goal:** Running local dev environment with Temporal, a hello-world workflow, database
schema, auth skeleton, and the REST API structure in place.

### Tasks

- [ ] Initialize Python project with `pyproject.toml`
  - Dependencies: temporalio, fastapi, uvicorn, sqlalchemy, alembic, asyncpg,
    jinja2, httpx, pydantic, python-jose (JWT), authlib (OIDC)
- [ ] Create `docker-compose.yml` with:
  - Temporal server (temporalio/auto-setup)
  - Temporal Web UI
  - PostgreSQL (for app data; Temporal uses its own DB)
  - Keycloak (dev instance with pre-seeded realm)
- [ ] Keycloak dev setup:
  - Realm: `artemis-sim`
  - OIDC client: `artemis-app`
  - Realm roles: `nasa-program-manager`, `nasa-tech-authority`, `nasa-contracts-officer`,
    `contractor-pm`, `contractor-engineer`, `egs-ground-ops`, `admin`
  - Pre-seeded users: one per role (e.g., `pm@nasa.test`, `tech@nasa.test`,
    `pm@benning.test`, etc.)
  - Organization attribute on contractor users
  - Export realm config as JSON for reproducible setup
- [ ] Auth layer:
  - `auth/keycloak.py`: OIDC discovery, token validation, JWKS caching
  - `auth/dependencies.py`: `get_current_user`, `require_role(...)` FastAPI dependencies
  - `auth/dev_bypass.py`: `AUTH_DISABLED=true` mode — accepts `X-Simulation-Role` and
    `X-Simulation-Org` headers, no token required
- [ ] FastAPI skeleton: `main.py` with:
  - Health check endpoint
  - `/api/v1/` router prefix
  - Jinja2 template config + static files mount
  - OpenAPI docs at `/api/docs`
  - Auth middleware (Keycloak or dev bypass based on config)
- [ ] Database models (SQLAlchemy async):
  - `Mission` — id, name, architecture_type, status, created_at
  - `Task` — id, mission_id, phase, name, task_type, status, assigned_role,
    assigned_contractor, facility, prerequisites (JSON), nominal_duration,
    failure_probability, simulated_start, simulated_end, inputs (JSON), outputs (JSON)
  - `Contractor` — id, name, slug, reliability, cost_factor, speed_factor,
    specialties (JSON), llm_profile, branding (JSON)
  - `Facility` — id, name, location, capacity, current_occupancy, capabilities (JSON)
  - `TaskArtifact` — id, task_id, artifact_type (proposal, scorecard, test_report,
    invoice), content (JSON/text), created_at
  - `SimulatedClock` — id, current_time, last_advance_reason
- [ ] Alembic initial migration
- [ ] LLM compatibility layer:
  - `LLMProvider` abstract base class: `async def complete(prompt, system, **kwargs) -> str`
  - `OpenAIProvider` (works with OpenAI API and any compatible endpoint)
  - `AnthropicProvider`
  - `LocalProvider` (ollama / llama.cpp via OpenAI-compatible API)
  - Config: `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`
- [ ] Hello-world Temporal workflow: start → activity → complete
- [ ] REST API skeleton: mount routers for `/api/v1/missions`, `/api/v1/tasks`,
  `/api/v1/contractors`, `/api/v1/facilities`, `/api/v1/admin`, `/api/v1/clock`
- [ ] Admin endpoints (stub implementations):
  - `POST /api/v1/admin/reset` — wipe and reseed
  - `POST /api/v1/admin/seed/{scenario}` — load named scenario
  - `POST /api/v1/admin/inject` — inject actions into running sim
  - `GET /api/v1/admin/status` — simulation state summary
- [ ] Verify: `docker-compose up`, Keycloak login works, workflow executes, FastAPI
  serves a page, auth dev bypass works with curl

### Deliverable
Running local stack. Keycloak issues tokens. REST API accepts bearer tokens or dev
bypass headers. Can start a workflow from the API and see it in Temporal Web UI.

---

## Phase 1: Estes MVP Core Workflow (Day 1 Afternoon - Day 2)

**Goal:** Complete Estes model rocket workflow from procurement through launch readiness,
drivable via REST API signals.

### Day 1 Afternoon: Workflow Skeleton

- [ ] Seed data: Estes mission architecture (components, phases, tasks, contractors)
- [ ] Seed data: 3+ contractors with different reliability/cost profiles and branding
- [ ] Seed data: "Garage" facility with capacity=1
- [ ] `SimulatedClockWorkflow`:
  - Query handler returns current simulated time
  - Signal handler advances time by a given duration
  - Continue-As-New after N events
- [ ] `FacilityManagerWorkflow` (one per facility):
  - Signal: `request_reservation(mission_id, task_id)`
  - Signal: `release_reservation(mission_id, task_id)`
  - Query: current status, queue depth
  - Logic: grant if capacity available, else queue; signal back when granted
- [ ] `MissionWorkflow`:
  - Receives mission architecture definition
  - Spawns child workflows for each phase in dependency order
  - Tracks overall progress (queryable)
- [ ] REST endpoints for mission lifecycle:
  - `POST /api/v1/missions` — create and start a mission
  - `GET /api/v1/missions` — list missions with status
  - `GET /api/v1/missions/{id}` — mission detail with progress
  - `GET /api/v1/clock` — current simulated time
  - `POST /api/v1/clock/advance` — manual time advance (admin)

### Day 2 Morning: Procurement & Delivery

- [ ] `ProcurementWorkflow`:
  - For each component type, spawn `RFPWorkflow` (concurrently where possible)
  - Wait for all RFPs to complete (all contracts awarded)
- [ ] `RFPWorkflow`:
  - Activity: `generate_rfp` — creates RFP text (LLM or template)
  - Activity: `generate_proposals` — each eligible contractor generates a proposal
    (LLM activity on llm-processing task queue)
  - Activity: `evaluate_proposals` — LLM generates rubric + scorecards
  - Signal: `award_decision` — NASA user selects winning contractor
  - Activity: `issue_contract` — records contract in DB
- [ ] `DeliveryWorkflow`:
  - For each contracted component, spawn `TransportWorkflow`
  - Wait for all components received
- [ ] `TransportWorkflow`:
  - Activity: `initiate_shipment` — marks component as shipped, records in DB
  - Signal: `component_received` — EGS user marks as received at facility
  - Activity: `receiving_inspection` — automated pass/fail check
  - On fail: create rework/reorder task
- [ ] REST endpoints for task actions:
  - `GET /api/v1/missions/{id}/tasks` — list tasks, filter by status/role/phase
  - `GET /api/v1/tasks/{id}` — task detail with prerequisites, artifacts
  - `POST /api/v1/tasks/{id}/complete` — mark task complete (sends Temporal signal)
  - `POST /api/v1/tasks/{id}/fail` — mark task failed (sends Temporal signal)
  - `POST /api/v1/tasks/{id}/advance` — "deliver early" debug action
  - `GET /api/v1/rfps` — list open RFPs
  - `POST /api/v1/rfps/{id}/award` — award contract to selected contractor

### Day 2 Afternoon: Integration & Launch Readiness

- [ ] `IntegrationWorkflow` (Estes: gluing + assembly):
  - Check prerequisites (all required components available + inspected)
  - Signal `FacilityManagerWorkflow` for garage reservation
  - Wait for facility grant
  - Signal: `integration_started` — user begins work
  - Activity: `simulate_integration` — pass/fail based on contractor reliability
  - On fail: generate failure report (LLM), create rework task, release facility
  - On pass: generate integration report (LLM), produce output component
  - Signal: release facility
- [ ] `LaunchReadinessWorkflow`:
  - Signal: `inspection_complete` — Technical Authority approves
  - Signal: `launch_readiness_approved` — Program Manager approves
  - Activity: update mission status to READY_TO_LAUNCH
- [ ] REST endpoints:
  - `GET /api/v1/facilities` — facility status
  - `GET /api/v1/tasks/{id}/artifacts` — artifacts for a task
  - `GET /api/v1/scorecards` — list all scorecards
  - `GET /api/v1/scorecards/{id}` — scorecard detail with citations
- [ ] End-to-end test: start Estes mission via REST, advance through all phases via
  REST signals, verify workflow completion. All via `curl` or `httpie`.

### Deliverable
Can run complete Estes mission lifecycle through REST API. Every action is a REST call
with bearer token or dev bypass header. Visible in Temporal Web UI. LLM generates
proposals and reports.

---

## Phase 2: Dashboard Views (Day 3)

**Goal:** Web UI for all six roles, with Gantt chart and Kanban views. The Jinja2/HTMX
frontend consumes the REST API built in Phase 1.

### Morning: Core UI Framework

- [ ] Keycloak browser login flow:
  - `/login` → redirect to Keycloak → callback → session cookie
  - `/logout` → clear session, redirect to Keycloak logout
  - Session middleware stores user info (role, org) from JWT
- [ ] Base template: nav bar (user name, role badge, mission selector, simulated time
  display), main content area, notification badge
- [ ] HTMX setup: SSE endpoint for live updates, `hx-trigger="sse:update"` on
  dynamic components
- [ ] View layer (`views/dashboards.py`): Jinja2 route handlers that call REST API
  endpoints and render templates
- [ ] Kanban component: `hx-get` loads tasks by status for current role, drag-drop
  moves tasks between columns (triggers POST to REST API → Temporal signal)
- [ ] Task detail modal: shows task info, prerequisites, artifacts, action buttons

### Afternoon: Role-Specific Dashboards

- [ ] **Program Manager**: multi-mission progress bars (horizontal stacked bars per
  phase), Gantt chart (using Frappe Gantt or similar), milestone gate approvals
- [ ] **Technical Authority**: review queue (pending scorecards/test reports), scorecard
  detail view with citations highlighted, approve/reject buttons
- [ ] **Contracts Officer**: invoice list, budget summary table, payment action buttons
- [ ] **Contractor PM**: RFP inbox, proposal submission form (or "generate proposal"
  button for LLM), contract status
- [ ] **Ground Ops**: facility status board (cards per facility showing occupant/empty),
  incoming shipment list, "Mark Received" buttons
- [ ] **Contractor Engineer**: work order list, "Complete Task" button, report viewer
- [ ] **Admin view**: simulation status, reset button, scenario selector, inject form

### Deliverable
All six roles have functional dashboards. Actions in the UI trigger REST API calls →
Temporal signals. Gantt chart shows mission timeline in simulated time. Same actions
work from both browser UI and curl.

---

## Phase 3: LLM Integration (Day 4, Morning)

**Goal:** End-to-end LLM flow: RFP → rubric → proposals → scorecards → compliance check.

### Tasks

- [ ] Prompt templates stored as files in `src/artemis/prompts/`:
  - `rfp_generation.txt`
  - `proposal_generation.txt`
  - `rubric_generation.txt`
  - `scorecard_generation.txt`
  - `compliance_check.txt`
  - `test_report_generation.txt`
  - `failure_report_generation.txt`
- [ ] NPR excerpts stored in `src/artemis/seed/nprs/` as text files
- [ ] Activity: `generate_rfp` — uses mission component spec + NPR context → RFP text
- [ ] Activity: `generate_rubric` — uses RFP text → evaluation rubric (JSON)
- [ ] Activity: `generate_proposal` — uses RFP + contractor profile → proposal text
- [ ] Activity: `evaluate_proposal` — uses proposal + rubric + NPR context →
  scorecard (JSON with citations)
- [ ] Activity: `generate_test_report` — uses test parameters + pass/fail outcome →
  realistic test report
- [ ] Activity: `analyze_test_report` — uses test report + acceptance criteria + NPR →
  analysis with recommendations
- [ ] Scorecard display in Technical Authority dashboard: table with criteria, scores,
  color-coded compliance flags, expandable citation sections
- [ ] REST endpoints for LLM artifacts are already in place from Phase 1
  (`/api/v1/tasks/{id}/artifacts`, `/api/v1/scorecards`). Verify they return the
  generated content correctly.
- [ ] End-to-end test: start mission → LLM generates RFP → LLM generates proposals →
  LLM evaluates → user sees scorecard → user approves → workflow continues

### Deliverable
LLM is actively generating and analyzing content throughout the workflow. Scorecards
show citations and compliance flags. The "core demo" of LLM-assisted decision support
is functional.

---

## Phase 4: Multi-Mission & Contractor Portal (Day 4, Afternoon)

**Goal:** Three concurrent Estes missions competing for facilities. Contractor portal
with branded views and invoice API. Admin reset and seed working.

### Tasks

- [ ] Start Estes I, II, III via `POST /api/v1/missions` — each spawns MissionWorkflow
- [ ] Verify facility contention: only one mission can use the garage at a time,
  others queue and show "Blocked: waiting for facility" in dashboards
- [ ] Program Manager Gantt shows all three missions on one timeline
- [ ] Contractor portal template: `/contractor/{slug}` with:
  - CSS theme loaded from contractor branding config
  - Invoice submission form
  - Invoice list with status badges
  - Active contracts and work orders
- [ ] Invoice REST API:
  - `POST /api/v1/contractors/{slug}/invoices`
  - `GET /api/v1/contractors/{slug}/invoices`
  - `GET /api/v1/contractors/{slug}/invoices/{id}`
  - `PATCH /api/v1/contractors/{slug}/invoices/{id}` (status update)
- [ ] Contracts Officer can view and approve/reject invoices
- [ ] Budget tracking: per-mission and per-contractor totals
- [ ] Admin API fully functional:
  - `POST /api/v1/admin/reset` — terminates all workflows, truncates tables, reseeds
  - `POST /api/v1/admin/seed/estes-mid-delivery` — loads scenario with pre-generated
    LLM artifacts
  - `POST /api/v1/admin/inject` — complete/fail tasks, add missions, adjust parameters
  - `GET /api/v1/admin/status` — full simulation state summary
- [ ] "Deliver Early" via `POST /api/v1/tasks/{id}/advance` working for any pending task

### Deliverable
Three missions running concurrently with visible facility contention. Contractor portals
look distinct. Invoice flow works end-to-end. Admin can reset to clean slate or seed
mid-demo state. All operations available via REST.

---

## Phase 5: K3s Deployment (Day 5)

**Goal:** Running in existing K3s cluster, accessible via ingress, demo-ready.

### Tasks

- [ ] Dockerfile: multi-stage build for the Python app (FastAPI + workers)
- [ ] Separate entry points: `web` (FastAPI), `worker-orchestration`,
  `worker-llm`, `worker-simulation`, `worker-notifications`
- [ ] Kubernetes manifests:
  - Namespace: `artemis-sim`
  - Temporal server: StatefulSet (or use temporal-helm-charts)
  - PostgreSQL: StatefulSet with PVC (or external managed DB)
  - Keycloak: Deployment + Service (or connect to existing enterprise Keycloak)
  - Keycloak realm import: ConfigMap with realm JSON, init on first boot
  - FastAPI: Deployment + Service + Ingress
  - Workers: Deployment per worker type (independently scalable)
  - ConfigMap: LLM settings, Temporal connection, DB connection, Keycloak URL
  - Secret: API keys, Keycloak client secret, DB password
- [ ] Ingress configuration:
  - `/` → FastAPI (Jinja2 UI)
  - `/api/` → FastAPI (REST API)
  - `/auth/` → Keycloak (or reverse proxy path)
  - `/temporal/` → Temporal Web UI (optional)
- [ ] Health checks: liveness + readiness probes on all pods
- [ ] Resource requests/limits for all containers
- [ ] Seed data: auto-run on first deployment (init container or startup command)
- [ ] End-to-end smoke test: deploy to K3s, login via Keycloak, start a mission,
  advance through workflow via both UI and curl, verify dashboards
- [ ] Document demo script: step-by-step walkthrough for presentations

### Deliverable
Running in K3s. All services healthy. Keycloak SSO working. Can run the full Estes demo
from a browser pointed at the ingress URL. Can also drive the entire simulation from
CLI via REST API with bearer tokens.

---

## Phase 6: Artemis Architecture (Post-MVP, Week 2+)

- [ ] Define Artemis mission architecture in seed data:
  - All SLS components with real transport methods and durations
  - VAB stacking sequence as ordered integration tasks
  - Parallel Orion processing pipeline (O&C → MPPF → LASF → VAB)
- [ ] Add all KSC facilities with realistic capacity constraints
- [ ] Barge workflow: Pegasus transit (MAF → SSC → KSC, 7+ days)
- [ ] Rail workflow: SRB segments from Utah (4+ days)
- [ ] VAB stacking sequence: 10+ ordered integration tasks
- [ ] Rollout workflow: VAB → LC-39B via CT-2 (12 hours simulated)
- [ ] Wet Dress Rehearsal workflow: propellant loading + countdown sim
- [ ] Launch readiness review chain
- [ ] Failure scenarios: hydrogen leak at WDR, helium flow issue, battery replacement
- [ ] Rollback workflow: LC-39B → VAB (reverse of rollout)
- [ ] Multi-mission cadence analysis: how fast can the infrastructure support launches?
- [ ] Artemis-specific seed scenarios for admin API

## Phase 7: Polish & Expand (Post-MVP, Ongoing)

- [ ] More contractors (10+) for competitive variety
- [ ] Detailed NPR integration with more document sections
- [ ] Notification system (in-app + optional Slack/email)
- [ ] Historical comparison mode (simulated vs. actual Artemis timelines)
- [ ] Admin panel polish: live parameter adjustment, simulation speed control
- [ ] Temporal search attributes for rich filtering in Web UI
- [ ] Performance testing: 10+ concurrent missions
- [ ] User guide / demo script for presentations
- [ ] React/Vue.js frontend option consuming the same REST API
