# Artemis Mission Architecture Simulation

## System Overview

A simulation platform demonstrating Temporal workflow orchestration and LLM-assisted
automation in the context of NASA mission assembly operations. The system models the
full lifecycle of rocket mission preparation — from contractor bidding through launch
readiness — with human-driven task progression, LLM-generated contractor outputs, and
LLM-powered compliance analysis.

**Primary audiences:**
- NASA personnel (demo of workflow automation and LLM-assisted decision support)
- Temporal community (showcase of complex, long-running, human-in-the-loop workflows)
- LLM/AI community (practical agent integration in structured business processes)

**What this is:** A Demo/POC for Temporal workflows and LLM automation, built as a
complete pretend system to advertise LLM-assisted development capabilities (Claude Code).
The application views and roles are realistic starting points for real workflow requests.

**What this is not:** A production system for managing actual missions.

---

## 1. Naming Conventions

### 1.1 Contractors (Fictional)

All contractor entities are fictional. No real corporation names appear in the system.

| Simulated Role | Fictional Name | Real Analog |
|---|---|---|
| Core stage manufacturer | Benning | Boeing |
| Commercial launch provider | XYZSpace | SpaceX |
| Solid rocket booster manufacturer | Caltrop Candlesticks, Inc. | Northrop Grumman |
| Ground systems operations | John Jingleheimer GmbH | Jacobs |
| Rocket engine manufacturer | Jetwash Aerodyne Alliance | Aerojet Rocketdyne |
| Upper stage manufacturer | Conglomerate Risk Distributors (CRD) | ULA |
| Crew vehicle manufacturer | Lunkhead Marmot, LLC | Lockheed Martin |
| International service module | Vol Magnifique S.A.R.L. / Antarctic Space Agency | Airbus / ESA |

Contractors have configurable attributes:
- **Reliability rate**: probability of passing quality checks on first attempt
- **Cost factor**: multiplier on baseline task costs
- **Speed factor**: multiplier on baseline task durations
- **Specialty areas**: what they can bid on
- **Personality profile**: LLM prompt characteristics for generating proposals/reports

Additional fictional contractors may be created freely to increase competitive variety.

### 1.2 NASA Facilities (Real Names)

| Facility | Location | Function |
|---|---|---|
| Vehicle Assembly Building (VAB) | KSC, FL | Vehicle stacking and integration |
| Launch Complex 39B (LC-39B) | KSC, FL | Launch pad |
| Rotation, Processing and Surge Facility (RPSF) | KSC, FL | SRB segment receiving and rotation |
| Multi-Payload Processing Facility (MPPF) | KSC, FL | Orion fueling and servicing |
| Launch Abort System Facility (LASF) | KSC, FL | LAS integration with Orion |
| Neil Armstrong Operations and Checkout Building (O&C) | KSC, FL | Orion assembly |
| Mobile Launcher 1 (ML-1) | KSC, FL | Launch platform and tower |
| Crawler-Transporter 2 (CT-2) | KSC, FL | Vehicle transport |
| Michoud Assembly Facility (MAF) | New Orleans, LA | Core stage manufacturing |
| Stennis Space Center (SSC) | Bay St. Louis, MS | Engine testing (Green Run) |
| Marshall Space Flight Center (MSFC) | Huntsville, AL | SLS program management |

Facilities are modeled as **resources with capacity constraints**. A facility can
process a limited number of items concurrently. This drives contention when multiple
missions compete for the same facility.

---

## 2. Simulation Model

### 2.1 Time Model

The simulation runs in **real time** with **user-driven advancement**.

- A system-wide **simulated clock** tracks mission time independently of wall-clock time.
- When a user completes a task (e.g., "receive component at dock"), the simulated clock
  advances to reflect realistic elapsed time for that operation, even if the user
  completed it in seconds.
- Each task has a **nominal simulated duration** (e.g., "barge transit: 6 days"). When a
  user marks it complete, the simulated clock jumps forward by that duration.
- **Debug/demo mode**: any pending task can be "delivered early" — instantly completed
  with its full simulated duration applied to the clock. This allows rapid progression
  through non-interesting phases during demos.
- **No continuous processing simulation.** Tasks are discrete state transitions:
  `not_started` → `in_progress` → `completed` (or `failed` → `rework`). A shipped item
  is simply "shipped" until someone accepts it, at which point it "arrives."
- Timestamps on all events, Gantt charts, and logs use **simulated time**, producing
  coherent project timelines regardless of how quickly users advance through tasks.

### 2.2 Simulated Time Mechanics

```
SimulatedClock:
  - base_time: datetime         # mission T-0 reference
  - current_time: datetime      # current simulated time
  - advance(duration) -> None   # jump forward
  - now() -> datetime           # current simulated time
```

When multiple missions run concurrently, they share the same simulated clock. If
Mission A's user advances a 6-day task while Mission B is mid-assembly, Mission B's
pending tasks also see the clock advance. This is intentional — it models real calendar
time pressure.

### 2.3 Task Model

Every action in the system is a **Task** with:

```
Task:
  - id: UUID
  - mission_id: str             # which mission this belongs to
  - phase: str                  # design, manufacture, deliver, integrate, etc.
  - name: str                   # human-readable description
  - task_type: enum             # AUTOMATED, SIMULATED, USER, AGENT
  - assigned_role: str          # which user role handles this
  - assigned_contractor: str    # if contractor work
  - facility: str | None        # facility required (resource lock)
  - prerequisites: list[UUID]   # tasks that must complete first
  - nominal_duration: timedelta # simulated time this task "takes"
  - status: enum                # NOT_READY, AVAILABLE, IN_PROGRESS, COMPLETED, FAILED, REWORK
  - inputs: dict                # components/data required
  - outputs: dict               # components/data produced
  - failure_probability: float  # chance of failure on completion
  - rework_of: UUID | None      # if this is a rework of a failed task
```

**Task types:**
- **AUTOMATED**: System runs automatically (ops checks, pressurization validation).
  Completes after simulated duration with pass/fail based on probability.
- **SIMULATED**: Represents real rocket operations (engine tests, structural loads).
  System generates realistic output data. May require LLM to produce test reports.
- **USER**: Requires a human to act. User receives notification, performs the action,
  marks complete. The human is the primary driver.
- **AGENT**: LLM agent processes inputs and generates outputs. Proposals, compliance
  reviews, scorecards. May run autonomously or queue for human review.

### 2.4 Failure and Rework

- Tasks have a configurable `failure_probability` (influenced by contractor reliability).
- On failure, the system generates a **failure report** (LLM-generated, describing what
  went wrong in domain-appropriate language).
- Failed tasks create **rework tasks** with updated prerequisites and potentially new
  failure modes.
- Rework can cascade: fixing a booster segment issue may require partial destacking,
  which blocks other integration work.
- **Rollback scenarios**: a failed integration test mid-stack may require removing
  components, returning them to a facility, and re-processing.
- Failure probability is tunable per-demo. "Everything goes right" mode for happy-path
  demos, "Murphy's Law" mode for stress-testing the workflow.

---

## 3. User Roles

### 3.1 Role Definitions

| Role | Responsibilities | Key Views |
|---|---|---|
| **NASA Program Manager** | Mission-level oversight, milestone approval, schedule review | Gantt chart, mission progress bars, milestone gates |
| **NASA Technical Authority** | Validate contractor technical work, review test results | Task queue, compliance scorecards, test reports |
| **NASA Contracts Officer** | Authorize payments, manage contract actions | Invoice queue, budget tracking, contract status |
| **Contractor PM** | Submit proposals/quotes, manage contractor work | RFP inbox, proposal editor, work status |
| **Contractor Engineer** | Execute technical work, generate reports (LLM-driven in sim) | Work orders, report generation, status updates |
| **EGS / Ground Ops** | Receive components, transfer between facilities, integration | Facility status, transport queue, integration checklist |

### 3.2 User Experience

- Users authenticate via **Keycloak SSO**. Their simulation role and organization are
  derived from Keycloak realm role and organization claims in the JWT.
- Each user session operates as a **single role** for a **single organization**.
- The dashboard shows only tasks relevant to that role and organization.
- **Notifications**: when a task becomes AVAILABLE for a user's role, they see it in
  their queue. In-app notification list with SSE push for real-time updates.
- **Kanban view** per role: columns for `Blocked` → `Available` → `In Progress` → `Done`,
  with the most critical-path item highlighted.
- **Critical path suggestion**: the system identifies which available task, if completed
  next, would most advance the overall mission timeline.
- **Multi-user interactive demo**: Real people can be assigned Keycloak accounts with
  specific roles and work interactively in the same simulation, each seeing their own
  task queue and advancing the shared mission state.

---

## 4. LLM Integration

### 4.1 Architecture

```
LLM Compatibility Layer:
  - Provider interface: send(prompt, system_context) -> response
  - Backends: OpenAI API, Anthropic API, local (llama.cpp / ollama / OpenAI-compatible)
  - Configuration: provider selection, model selection, API keys, base URLs
  - No streaming requirement — batch request/response only
  - Retry with fallback: if primary provider fails, try secondary
```

### 4.2 Use Cases

#### A. Contractor Simulation (Behind the Scenes)

LLM generates realistic contractor outputs that become inputs to the real demo system:

1. **Proposal generation**: Given an RFP, generate a contractor proposal with technical
   approach, cost breakdown, schedule, and risk assessment. Different contractors have
   different prompt profiles producing different quality/style.
2. **Test report generation**: Given a test procedure and pass/fail outcome, generate a
   realistic test report with data tables, observations, and recommendations.
3. **Status report generation**: Periodic contractor status updates with progress,
   issues, and schedule impacts.
4. **Invoice generation**: Itemized invoices with labor hours, materials, overhead.

#### B. NASA Decision Support (The Core Demo)

LLM assists NASA personnel in processing contractor outputs:

1. **RFP → Rubric**: Given an RFP document (natural language), the LLM generates an
   evaluation rubric with weighted criteria and scoring guidelines.
2. **Proposal → Scorecard**: Given a proposal and the rubric, the LLM fills out a
   scorecard with per-criterion scores, citations from the proposal, and a summary
   assessment.
3. **Compliance checking**: Given contractor outputs and applicable NASA Procedural
   Requirements (NPRs), the LLM identifies compliant/noncompliant elements with
   specific citations to both the output and the NPR.
4. **Test report analysis**: Given a test report, the LLM extracts key metrics, flags
   anomalies, compares against acceptance criteria, and produces a pass/fail
   recommendation with rationale.
5. **Schedule impact analysis**: Given a failure or delay, the LLM assesses downstream
   impacts and suggests mitigation options.

#### C. Data Flow

```
Contractor Task Completes
  → LLM generates contractor output (proposal, test report, invoice, etc.)
  → Output stored as task artifact
  → NASA user's queue shows new item to review
  → User opens item → sees raw contractor output + LLM-generated scorecard/analysis
  → User can drill into citations, adjust scores, approve/reject
  → Decision feeds back into Temporal workflow, advancing or blocking next tasks
```

### 4.3 NPR Integration

For the demo, we include a small set of simplified NPR excerpts relevant to the
simulation:

- **NPR 7120.5** (NASA Space Flight Program and Project Management Requirements) —
  milestone review gates, decision authority
- **NPR 8705.2** (Human-Rating Requirements) — safety and reliability standards
- **NPR 7150.2** (NASA Software Engineering Requirements) — for avionics/software tasks

These are stored as reference documents. The LLM is prompted with relevant NPR sections
when evaluating contractor outputs, enabling it to cite specific requirements in its
compliance assessments.

---

## 5. Mission Architecture Data Model

### 5.1 Core Entities

```
MissionArchitecture:
  - name: str                           # "Estes I", "Artemis II"
  - components: list[ComponentSpec]     # what needs to be built/procured
  - phases: list[Phase]                 # ordered phases of the mission
  - facilities: list[FacilityRef]       # facilities this mission will use

ComponentSpec:
  - name: str                           # "Solid Motor", "Core Stage"
  - type: str                           # category for contractor bidding
  - required_by_phase: str              # which phase needs this component
  - transport_method: str               # barge, rail, truck, aircraft
  - transport_origin: str               # where it ships from
  - transport_destination: str          # where it arrives

Phase:
  - name: str                           # "procurement", "delivery", "integration"
  - tasks: list[TaskTemplate]           # task templates for this phase
  - depends_on: list[str]               # phases that must complete first

Facility:
  - name: str                           # "VAB High Bay 3"
  - location: str                       # "KSC"
  - capacity: int                       # concurrent items/missions
  - capabilities: list[str]            # what can be done here

Contractor:
  - name: str
  - reliability: float                  # 0.0-1.0
  - cost_factor: float                  # 1.0 = baseline
  - speed_factor: float                 # 1.0 = baseline
  - specialties: list[str]
  - llm_profile: str                    # prompt template for personality
  - branding: ContractorBranding        # CSS theme, logo, colors

ContractorBranding:
  - primary_color: str
  - secondary_color: str
  - logo_url: str | None
  - css_class: str                      # for contractor portal color-swap
```

### 5.2 MVP Mission: "Estes Model Rocket"

A minimal mission architecture to prove the full workflow pipeline:

**Components:**
| Component | Transport | Contractor Specialty |
|---|---|---|
| B-class solid motor | truck / "from store" | propulsion |
| Plastic parachute | truck / "from store" | recovery systems |
| Rocket body (tube) | truck / "from store" | structures |
| Fins (x3) | truck / "from store" | structures |
| Bottle of glue | truck / "from store" | materials |

**Phases and Tasks:**

```
Phase 1: Procurement
  ├── NASA issues RFP for each component type
  ├── Contractors submit proposals (AGENT: LLM-generated)
  ├── NASA Technical Authority evaluates proposals (AGENT: LLM scorecard)
  ├── NASA Contracts Officer selects winners (USER)
  └── Contracts awarded, purchase orders issued

Phase 2: Delivery
  ├── Each contractor "ships" their component (SIMULATED: instant, marks as shipped)
  ├── EGS receives each component at "garage" (USER: marks as received)
  └── EGS inspects each component (AUTOMATED: pass/fail check)

Phase 3: Gluing (Body + Fins Integration)
  ├── Prerequisites: body + 3 fins + glue all received and inspected
  ├── Contractor engineer performs gluing (USER/AGENT: generates work report)
  ├── Inspection: structural check of fin attachment (AUTOMATED + AGENT: test report)
  └── Output: "BodyAndFins" integrated component

Phase 4: Assembly
  ├── Prerequisites: BodyAndFins + solid motor + parachute all available
  ├── Assembly task: integrate all components (USER: marks complete)
  ├── Final integration test (AUTOMATED: systems check)
  └── Output: "ModelRocket" complete assembly

Phase 5: Launch Readiness
  ├── Final inspection review (USER: NASA Technical Authority)
  ├── Launch readiness review (USER: NASA Program Manager)
  └── Status: READY_TO_LAUNCH
```

**Multi-mission demo**: Estes I, Estes II, Estes III running concurrently. Different
contractors win different component bids. Missions compete for the single "garage"
facility. One mission encounters a gluing failure requiring rework while others proceed.

### 5.3 Target Mission: Artemis (Simplified)

After the Estes MVP proves the architecture, we expand to the full Artemis model:

**Components:** SRB segments (10), core stage, RS-25 engines (4), ICPS/Centaur V, LVSA,
Orion crew module, European Service Module, Launch Abort System, Orion Stage Adapter.

**Transport:**
| Component | Method | Origin | Destination |
|---|---|---|---|
| SRB segments | Rail | Utah (Caltrop Candlesticks) | KSC RPSF |
| Core stage | Barge (Pegasus) | MAF, New Orleans | KSC Turn Basin |
| ICPS | Barge (RocketShip) | Alabama (CRD) | KSC |
| Orion crew module | Aircraft (Super Guppy) | MAF | KSC O&C |
| European Service Module | Aircraft | Antarctic Space Agency HQ | KSC O&C |
| RS-25 engines | Truck | Jetwash Aerodyne, CA | MAF → integrated into core stage |
| LVSA | Truck | Huntsville, AL | KSC VAB |

**Phases:** Design → Manufacture → Test → Deliver → Inspect → Stage → Integrate →
Test Integration → Transfer (rollout) → Wet Dress Rehearsal → Launch Readiness → Launch.

**Facility contention model:**
- VAB High Bay 3: 1 active stack at a time (can we fit a second in another high bay?)
- LC-39B: 1 vehicle at a time, ~2-week pad turnaround minimum
- Crawler-Transporter 2: 1 trip at a time, ~12 hours each way
- RPSF: can process multiple SRB segment sets concurrently
- The barge is shared — if it's delivering Artemis IV's core stage, it can't
  simultaneously carry Artemis V's

This is where the simulation answers the real question: **what launch cadence can the
infrastructure actually support?**

---

## 6. Temporal Workflow Architecture

### 6.1 Workflow Hierarchy

```
MissionWorkflow (top-level, one per mission)
  ├── ProcurementWorkflow (child)
  │     ├── RFPWorkflow (child, one per component type)
  │     │     ├── Activity: generate_rfp (LLM)
  │     │     ├── Signal: contractor_proposal_submitted
  │     │     ├── Activity: evaluate_proposal (LLM)
  │     │     ├── Signal: nasa_award_decision (USER)
  │     │     └── Activity: issue_contract
  │     └── ... (one RFPWorkflow per component)
  │
  ├── DeliveryWorkflow (child)
  │     ├── TransportWorkflow (child, one per component)
  │     │     ├── Activity: initiate_shipment
  │     │     ├── Signal: component_received (USER: EGS)
  │     │     └── Activity: receiving_inspection
  │     └── ...
  │
  ├── IntegrationWorkflow (child)
  │     ├── Activity: check_prerequisites (components + facility available)
  │     ├── Signal: facility_reserved
  │     ├── Activity: perform_integration (USER/AGENT)
  │     ├── Activity: integration_test (AUTOMATED)
  │     └── Activity: generate_test_report (LLM)
  │
  └── LaunchReadinessWorkflow (child)
        ├── Signal: final_inspection_complete (USER: Tech Authority)
        ├── Signal: launch_readiness_review (USER: Program Manager)
        └── Activity: update_mission_status → READY_TO_LAUNCH
```

### 6.2 Key Temporal Patterns Used

- **Signals** for all human-in-the-loop actions (approvals, receiving, inspections)
- **Child workflows** per phase to isolate failure domains and bound event history
- **Queries** for dashboard state (current phase, blocked tasks, progress %)
- **Activities** for LLM calls, database writes, notification dispatch
- **Durable timers** for simulated time tracking and deadline enforcement
- **Continue-As-New** on the MissionWorkflow if event history grows large
- **Task queues**: separate queues for `mission-orchestration`, `llm-processing`,
  `simulation`, `notifications`
- **Search attributes**: `mission_id`, `phase`, `status`, `assigned_role`,
  `contractor`, `facility` for filtering in dashboards and Temporal Web UI
- **Saga pattern** for rollback: if integration fails, compensating actions unstack
  components and return them to prior facility

### 6.3 Facility Resource Management

Facilities are modeled as shared resources using a **FacilityManagerWorkflow** (one per
facility):

```
FacilityManagerWorkflow:
  - Maintains a queue of reservation requests (Signals)
  - Grants access based on capacity (Signal back to requesting workflow)
  - Tracks current occupants
  - Releases capacity when work completes (Signal)
  - Queryable for current status, queue depth, estimated wait time
```

This makes facility contention visible: if VAB High Bay 3 is occupied by Estes II,
Estes III's integration workflow blocks on the facility reservation signal, and the
dashboard shows it as "waiting for facility."

### 6.4 Simulated Clock as Workflow

```
SimulatedClockWorkflow:
  - Maintains current simulated time
  - Receives advance_time signals when tasks complete
  - Queryable for current time
  - Broadcasts time updates to interested workflows
  - Handles Continue-As-New to manage event history
```

---

## 7. Technical Architecture

### 7.1 Stack

| Layer | Technology | Notes |
|---|---|---|
| Workflow engine | Temporal (self-hosted in K3s) | Core orchestration |
| Backend language | Python 3.12+ | All workflows, activities, API |
| Temporal SDK | temporalio (Python SDK) | Workflow/activity definitions |
| API server | FastAPI | Strict REST API (primary interface) |
| Authentication | Keycloak (SSO) | OIDC/OAuth2, role mapping, enterprise SSO |
| Database | PostgreSQL | Mission data, artifacts, user state |
| LLM layer | Custom compatibility layer | OpenAI, Anthropic, ollama/llama.cpp |
| Frontend (bundled) | FastAPI + Jinja2 templates + HTMX | Server-rendered, consumes own REST API |
| Charts | Frappe Gantt or similar JS lib | Gantt chart rendering |
| Kanban | Simple HTML/CSS/JS | Drag-drop task board |
| Real-time updates | SSE (Server-Sent Events) | Live dashboard refresh |
| Deployment | K3s (existing cluster) | Kubernetes manifests |
| Container runtime | Docker | Dockerfiles for each service |

### 7.2 API-First Design

The system is **API-first**. Every operation is available through a strict REST API
with token-based authentication (OAuth2 bearer tokens from Keycloak). The bundled
Jinja2/HTMX frontend is one consumer of this API — not a privileged one.

**Design principles:**
- All state mutations go through REST endpoints, never through template-only routes.
- Every REST endpoint returns JSON by default. The Jinja2 layer calls the same endpoints
  (or shared service functions) to render HTML.
- Bearer token auth on all API endpoints. The Jinja2 frontend uses session cookies
  (backed by the same Keycloak OIDC flow) for browser convenience.
- API is fully usable from CLI tools (`curl`, `httpie`), test scripts, external
  automation, and future React/Vue.js replacements.
- OpenAPI schema auto-generated by FastAPI, always accurate.

**REST API structure:**
```
/api/v1/
  ├── /missions                    # CRUD + start/reset
  ├── /missions/{id}/tasks         # Task listing, filtering by status/role/phase
  ├── /missions/{id}/gantt         # Gantt chart data (JSON)
  ├── /tasks/{id}                  # Task detail + action (complete, fail, advance)
  ├── /tasks/{id}/artifacts        # Task artifacts (proposals, reports, scorecards)
  ├── /contractors                 # Contractor listing + detail
  ├── /contractors/{slug}/invoices # Invoice CRUD
  ├── /contractors/{slug}/portal   # Contractor portal data
  ├── /facilities                  # Facility status, reservations
  ├── /clock                       # Simulated time (GET current, POST advance)
  ├── /rfps                        # RFP listing, detail, proposal submission
  ├── /scorecards                  # Scorecard listing, detail
  ├── /notifications               # Per-user notification feed
  ├── /admin/reset                 # Wipe simulation to clean state
  ├── /admin/inject                # Inject data for mid-demo state
  ├── /admin/seed/{scenario}       # Load a named scenario (estes-mvp, artemis-ii, etc.)
  └── /auth/...                    # Keycloak OIDC callback, token exchange
```

### 7.3 Authentication & Authorization (Keycloak SSO)

**Architecture:**
- Keycloak instance deployed in K3s (or shared enterprise Keycloak).
- Artemis realm with OIDC client configuration.
- Users authenticate via Keycloak login page (redirect flow for browser, direct grant
  for CLI/API clients).
- JWT access tokens contain role claims mapped to simulation roles.

**Keycloak role mapping:**
```
Keycloak Realm Roles → Simulation Roles:
  nasa-program-manager    → NASA Program Manager
  nasa-tech-authority     → NASA Technical Authority
  nasa-contracts-officer  → NASA Contracts Officer
  contractor-pm           → Contractor PM (org from token claim)
  contractor-engineer     → Contractor Engineer (org from token claim)
  egs-ground-ops          → EGS / Ground Ops
  admin                   → System admin (reset, inject, seed)
```

**Organization mapping:** Contractor roles include an `organization` claim in the
token (e.g., `benning`, `caltrop-candlesticks`). This scopes their view to only
their contractor's data.

**Auth flows:**
- **Browser (Jinja2/HTMX)**: Standard OIDC authorization code flow. Keycloak login
  redirects back to app. Session cookie stores tokens. Refresh handled transparently.
- **CLI / API clients**: Client credentials grant or direct access grant (resource
  owner password for demo convenience). Returns bearer token for Authorization header.
- **Service-to-service**: Temporal workers use service account tokens for DB and API
  calls.

**For local development / quick demos:** Keycloak can be configured with pre-seeded
users (one per role), or bypassed entirely with a `AUTH_DISABLED=true` env var that
accepts a role header (`X-Simulation-Role`) instead. This keeps the dev loop fast.

### 7.4 Service Architecture

```
┌──────────────────────────────────────────────────┐
│                    K3s Cluster                    │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐      │
│  │ Temporal  │  │ Temporal │  │ PostgreSQL│      │
│  │ Server   │  │ Web UI   │  │           │      │
│  └──────────┘  └──────────┘  └───────────┘      │
│                                                  │
│  ┌──────────┐                                    │
│  │ Keycloak │  (or shared enterprise Keycloak)   │
│  └──────────┘                                    │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │         FastAPI Application              │    │
│  │  ┌────────────┐ ┌──────┐ ┌───────────┐  │    │
│  │  │  REST API  │ │ SSE  │ │  Jinja2   │  │    │
│  │  │ (primary)  │ │ Push │ │ (bundled) │  │    │
│  │  └────────────┘ └──────┘ └───────────┘  │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────────────────────────────────────┐    │
│  │        Temporal Workers (Python)         │    │
│  │  ┌─────────────┐ ┌───────────────┐       │    │
│  │  │Orchestration│ │LLM Processing │       │    │
│  │  │   Worker    │ │    Worker     │       │    │
│  │  └─────────────┘ └───────────────┘       │    │
│  │  ┌─────────────┐ ┌───────────────┐       │    │
│  │  │ Simulation  │ │ Notification  │       │    │
│  │  │   Worker    │ │    Worker     │       │    │
│  │  └─────────────┘ └───────────────┘       │    │
│  └──────────────────────────────────────────┘    │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 7.5 Directory Structure

```
artemis-sim/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml              # local development
├── k8s/                            # Kubernetes manifests
│   ├── namespace.yaml
│   ├── temporal/                   # Temporal server + dependencies
│   ├── keycloak/                   # Keycloak + realm config
│   ├── app/                        # FastAPI + workers
│   └── postgres/
├── src/
│   └── artemis/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app entry point
│       ├── config.py               # Settings, env vars
│       ├── models/                 # SQLAlchemy / Pydantic models
│       │   ├── mission.py
│       │   ├── task.py
│       │   ├── contractor.py
│       │   ├── facility.py
│       │   └── user.py
│       ├── workflows/              # Temporal workflow definitions
│       │   ├── mission.py          # MissionWorkflow
│       │   ├── procurement.py      # ProcurementWorkflow, RFPWorkflow
│       │   ├── delivery.py         # DeliveryWorkflow, TransportWorkflow
│       │   ├── integration.py      # IntegrationWorkflow
│       │   ├── launch_readiness.py
│       │   ├── facility_manager.py # FacilityManagerWorkflow
│       │   └── clock.py            # SimulatedClockWorkflow
│       ├── activities/             # Temporal activity implementations
│       │   ├── llm.py              # LLM calls (proposals, scorecards, etc.)
│       │   ├── simulation.py       # Pass/fail simulation, data generation
│       │   ├── notifications.py    # User notification dispatch
│       │   └── persistence.py      # Database reads/writes
│       ├── llm/                    # LLM compatibility layer
│       │   ├── __init__.py
│       │   ├── base.py             # Provider interface
│       │   ├── openai_provider.py
│       │   ├── anthropic_provider.py
│       │   └── local_provider.py   # ollama / llama.cpp / OpenAI-compatible
│       ├── workers/                # Worker entry points
│       │   ├── orchestration.py
│       │   ├── llm_worker.py
│       │   ├── simulation.py
│       │   └── notifications.py
│       ├── auth/                    # Authentication layer
│       │   ├── __init__.py
│       │   ├── keycloak.py         # OIDC client, token validation
│       │   ├── dependencies.py     # FastAPI dependencies (get_current_user, require_role)
│       │   └── dev_bypass.py       # AUTH_DISABLED mode (X-Simulation-Role header)
│       ├── api/                    # FastAPI route modules (REST, JSON responses)
│       │   ├── missions.py
│       │   ├── tasks.py
│       │   ├── contractors.py
│       │   ├── facilities.py
│       │   ├── invoices.py
│       │   ├── clock.py            # Simulated time endpoints
│       │   ├── rfps.py
│       │   ├── scorecards.py
│       │   ├── notifications.py
│       │   └── admin.py            # Reset, inject, seed, status
│       ├── views/                   # Jinja2 HTML route handlers (consume REST API)
│       │   ├── dashboards.py       # Role-specific dashboard pages
│       │   ├── contractor_portal.py
│       │   └── auth_views.py       # Login/logout/callback pages
│       ├── templates/              # Jinja2 HTML templates
│       │   ├── base.html
│       │   ├── dashboard/
│       │   │   ├── program_manager.html    # Gantt + progress bars
│       │   │   ├── tech_authority.html     # Compliance scorecards
│       │   │   ├── contracts_officer.html  # Invoice/payment queue
│       │   │   ├── contractor_pm.html      # RFP inbox, proposals
│       │   │   ├── contractor_eng.html     # Work orders
│       │   │   └── ground_ops.html         # Facility status, receiving
│       │   ├── components/
│       │   │   ├── gantt.html
│       │   │   ├── kanban.html
│       │   │   ├── progress_bar.html
│       │   │   ├── scorecard.html
│       │   │   └── task_detail.html
│       │   └── contractor_portal/          # Color-swap CSS per contractor
│       │       └── invoice.html
│       ├── static/
│       │   ├── css/
│       │   │   ├── main.css
│       │   │   └── contractors/            # Per-contractor color themes
│       │   └── js/
│       │       ├── gantt.js
│       │       ├── kanban.js
│       │       └── htmx.min.js
│       └── seed/                   # Seed data
│           ├── contractors.py      # Contractor definitions + branding
│           ├── facilities.py       # Facility definitions + capacities
│           ├── estes_mission.py    # Estes model rocket architecture
│           └── artemis_mission.py  # Artemis SLS architecture
├── tests/
│   ├── test_workflows/
│   ├── test_activities/
│   ├── test_llm/
│   └── test_api/
└── docs/
    ├── REQUIREMENTS.md             # this file (symlinked or copied)
    └── ROADMAP.md                  # development roadmap
```

---

## 8. Dashboard Views

### 8.1 Program Manager Dashboard

- **Multi-mission progress bars**: each active mission shown as a horizontal bar from
  0% to 100%, segmented by phase, colored by status (green/yellow/red).
- **Gantt chart**: all missions on a shared timeline (simulated time), showing task
  dependencies, critical path highlighted, current time marker.
- **Milestone gates**: upcoming milestones that need PM approval, with go/no-go status.
- **Facility utilization**: which facilities are in use by which mission.

### 8.2 Technical Authority Dashboard

- **Review queue**: contractor outputs awaiting technical review.
- **Compliance scorecards**: LLM-generated scorecards with per-criterion scores, drill-
  down to citations from contractor output and applicable NPR sections.
- **Test report summaries**: key metrics extracted by LLM, anomalies flagged,
  pass/fail recommendation.
- **Critical path indicator**: which review, if completed, unblocks the most work.

### 8.3 Contracts Officer Dashboard

- **Invoice queue**: pending invoices from contractors, with status (submitted, under
  review, approved, paid).
- **Budget tracking**: per-mission and per-contractor spend vs. contract value.
- **Contract actions**: upcoming contract milestones, modifications pending.

### 8.4 Contractor PM Dashboard

- **RFP inbox**: open RFPs the contractor is eligible to bid on.
- **Active contracts**: current work status, upcoming deliverables.
- **Proposal editor**: interface to submit/edit proposals (or trigger LLM generation).

### 8.5 Ground Ops Dashboard

- **Facility status board**: real-time view of all facilities, current occupants,
  available capacity.
- **Transport queue**: incoming shipments, ETAs, receiving actions needed.
- **Integration checklist**: step-by-step integration tasks with prerequisites shown.

### 8.6 All Roles: Kanban View

Every role gets a personal Kanban board:
- **Blocked**: tasks whose prerequisites aren't met yet (visible for awareness).
- **Available**: tasks ready to work — prerequisites met, facility available.
- **In Progress**: tasks the user has started.
- **Done**: recently completed tasks.

The **top Available task** is highlighted as "Suggested Next Action" based on critical
path analysis.

---

## 9. Contractor Portal (Shallow Simulation)

Each contractor has a branded portal accessible at `/contractor/{contractor_slug}`:

- **Visual branding**: CSS color-swap based on `ContractorBranding` — different primary/
  secondary colors per contractor. Same HTML templates, different look.
- **Invoice API**: REST endpoints for invoice management:
  - `POST /api/v1/contractors/{slug}/invoices` — submit invoice
  - `GET /api/v1/contractors/{slug}/invoices` — list invoices
  - `GET /api/v1/contractors/{slug}/invoices/{inv_id}` — invoice detail
  - `PATCH /api/v1/contractors/{slug}/invoices/{inv_id}` — update status (paid/unpaid)
- **Proposal submission**: interface to submit proposals against open RFPs.
- **Work status**: view of assigned tasks and their status.

---

## 10. Simulation Control (Admin API)

### 10.1 Reset ("Big Red Button")

`POST /api/v1/admin/reset`

Wipes the simulation to a clean state:
- Terminates all running Temporal workflows (missions, facilities, clock)
- Truncates all application database tables (missions, tasks, artifacts, invoices)
- Resets the simulated clock to a configurable start time
- Re-seeds contractor and facility definitions
- Returns confirmation with timestamp

**Safety**: Requires `admin` role. Confirmation parameter required:
`{"confirm": true, "reason": "demo reset"}`. Logged with user identity.

### 10.2 Scenario Seeding

`POST /api/v1/admin/seed/{scenario_name}`

Loads a named scenario to a specific simulation state:

| Scenario | Description |
|---|---|
| `clean` | Empty — just contractors and facilities defined |
| `estes-procurement` | Estes I with RFPs issued, awaiting proposals |
| `estes-mid-delivery` | Estes I mid-delivery, Estes II in procurement |
| `estes-integration` | Estes I in integration, II delivering, III in procurement |
| `estes-failure` | Estes I hit a gluing failure, rework in progress |
| `artemis-stacking` | Full Artemis architecture, mid-VAB stacking |

Each scenario:
1. Resets the simulation (calls reset internally)
2. Creates missions at the specified state
3. Starts Temporal workflows with pre-injected signal history so they resume at the
   correct point in the workflow
4. Sets the simulated clock to match the scenario timeline
5. Pre-generates LLM artifacts (proposals, scorecards) so the demo doesn't wait for
   LLM calls

### 10.3 Data Injection

`POST /api/v1/admin/inject`

Injects arbitrary data into a running simulation without resetting:

```json
{
  "actions": [
    {
      "type": "complete_task",
      "task_id": "uuid",
      "outcome": "success",
      "advance_clock": true
    },
    {
      "type": "fail_task",
      "task_id": "uuid",
      "failure_reason": "Hydrogen leak detected during pressurization"
    },
    {
      "type": "create_mission",
      "architecture": "estes",
      "name": "Estes IV"
    },
    {
      "type": "advance_clock",
      "duration_hours": 48
    },
    {
      "type": "set_contractor_reliability",
      "contractor_slug": "benning",
      "reliability": 0.3
    }
  ]
}
```

This enables:
- Rapidly advancing a demo to an interesting state
- Triggering failures on demand ("now watch what happens when this breaks")
- Adding new missions mid-demo
- Adjusting simulation parameters live

### 10.4 Simulation Status

`GET /api/v1/admin/status`

Returns complete simulation state summary:
- Simulated clock time
- Active missions with phase/progress
- Running Temporal workflow count
- Facility utilization
- Pending tasks by role
- LLM call statistics

---

## 11. Development Roadmap

See [ROADMAP.md](ROADMAP.md) for the detailed day-by-day development plan.

---

## Appendix A: Simulated NPR Excerpts

For the demo, we include simplified excerpts (not full documents) to give the LLM
enough context for meaningful compliance checking:

**NPR 7120.5F §4.2 — Key Decision Points (simplified):**
> Each project shall conduct milestone reviews at Key Decision Points (KDP-A through
> KDP-F). Progression past each KDP requires: (1) documented assessment of technical
> maturity, (2) independent cost estimate validation, (3) risk disposition for all
> open risks rated 3x3 or higher, (4) approval by the Decision Authority.

**NPR 8705.2C §3.4 — Structural Verification (simplified):**
> All human-rated structural components shall demonstrate a factor of safety of 1.4
> for yield and 2.0 for ultimate under all design load conditions. Verification shall
> be by test (preferred), analysis, or a combination thereof with documented rationale
> for any analysis-only verification.

**NPR 7150.2D §5.1 — Software Assurance (simplified):**
> All flight software shall be classified by criticality level (A through D). Class A
> software (loss of life/vehicle) requires: 100% requirements-based test coverage,
> independent verification and validation (IV&V), formal code inspection of all safety-
> critical paths, and documented traceability from requirements through test results.

These are illustrative and simplified. Real NPRs are substantially more detailed.

---

## Appendix B: Example LLM Prompts

### B.1 Contractor Proposal Generation

```
System: You are simulating a contractor engineer at {contractor_name}, a company known
for {contractor_personality}. Generate a technical proposal in response to the following
NASA Request for Proposals.

Your proposal should include:
1. Technical Approach (2-3 paragraphs)
2. Cost Breakdown (table with line items)
3. Schedule (milestones with dates)
4. Risk Assessment (top 3 risks with mitigation)

Quality level: {contractor_reliability_descriptor}
Budget tendency: {contractor_cost_descriptor}

RFP:
{rfp_text}
```

### B.2 Compliance Scorecard Generation

```
System: You are a NASA technical evaluation assistant. Given the following:
1. RFP requirements
2. Evaluation rubric
3. Contractor proposal
4. Applicable NPR sections

Generate a compliance scorecard with:
- Per-criterion score (1-5) with brief justification
- Specific citations from the proposal (quote the relevant text)
- NPR compliance flags (COMPLIANT / NONCOMPLIANT / INSUFFICIENT_INFORMATION)
- For each NPR flag, cite the specific NPR section and the evidence (or lack thereof)
- Overall recommendation (STRONG_ACCEPT / ACCEPT / CONDITIONAL / REJECT)

Output as structured JSON matching this schema: {scorecard_schema}

RFP:
{rfp_text}

Rubric:
{rubric_text}

Proposal:
{proposal_text}

Applicable NPR Sections:
{npr_text}
```
