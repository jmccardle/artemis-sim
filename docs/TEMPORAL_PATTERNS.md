# Temporal Patterns in Artemis

This document catalogs every Temporal pattern used in the Artemis codebase,
with code references and explanations. Use it as a guided tour for talks,
demos, or self-study.

> **Suggested reading order:** Start at [1. Multi-Phase Orchestration](#1-multi-phase-orchestration),
> then follow the numbers. Each section builds on the previous one.

---

## Architecture at a Glance

```
MissionWorkflow (parent)
 ├── ProcurementWorkflow (child)
 │    ├── RFPWorkflow (grandchild) ──signals──▶ human award decision
 │    ├── RFPWorkflow                          ◀── LLM activities on dedicated queue
 │    └── ...
 ├── DeliveryWorkflow (child)
 │    ├── TransportWorkflow ──signals──▶ SimulatedClockWorkflow (singleton)
 │    ├── TransportWorkflow ──signals──▶ human receive confirmation
 │    └── ...
 ├── IntegrationWorkflow (child) ──signals──▶ FacilityManagerWorkflow (singleton)
 │    │                          ◀──signals── (reservation granted)
 │    └── ──signals──▶ human step completion
 └── LaunchReadinessWorkflow (child)
      ├── ──signals──▶ human: Tech Authority inspection review
      └── ──signals──▶ human: Program Manager launch go/no-go
```

**Key files:**

| File | Lines | What to look for |
|------|-------|------------------|
| `workflows/mission.py` | ~250 | Parent/child orchestration, queries, phase tracking |
| `workflows/procurement.py` | ~370 | Fan-out, LLM activities, human signals, wait_condition |
| `workflows/facility_manager.py` | ~165 | Entity workflow, inter-workflow signals, continue-as-new |
| `workflows/clock.py` | ~85 | Singleton, continue-as-new, query |
| `workflows/delivery.py` | ~235 | External workflow handles, simulation activities |
| `workflows/integration.py` | ~285 | Facility request/grant cycle, lambda closures in wait_condition |
| `workflows/launch_readiness.py` | ~158 | Sequential human review chain |
| `workflows/data_types.py` | ~395 | Workflow IDs, task queues, all dataclass contracts |
| `workers/main.py` | ~100 | Worker setup, workflow/activity registration |
| `workers/llm_worker.py` | ~50 | Dedicated LLM worker on separate task queue |
| `activities/llm.py` | ~190 | LLM activities with long timeouts |
| `activities/persistence.py` | ~215 | Database activities with short timeouts |
| `services/clock.py` | ~70 | Client-side query and signal from REST API |
| `services/missions.py` | ~80 | Starting workflows from the API layer |
| `api/admin.py` | ~200 | Workflow listing, termination, test-workflow |
| `main.py` | ~145 | System workflow startup on app boot |

---

## 1. Multi-Phase Orchestration

**Pattern:** A parent workflow delegates phases to child workflows, running them
sequentially and tracking progress in queryable state.

**File:** `workflows/mission.py:148-233`

```python
# MissionWorkflow.run() — sequential phase execution
self._phase = MissionPhase.PROCUREMENT
procurement_result = await workflow.execute_child_workflow(
    ProcurementWorkflow.run,
    ProcurementInput(mission_id=mission_id, components=components),
    id=procurement_workflow_id(mission_id),
    task_queue=ORCHESTRATION_QUEUE,
)
self._progress_pct = 25.0

self._phase = MissionPhase.DELIVERY
await workflow.execute_child_workflow(
    DeliveryWorkflow.run,
    DeliveryInput(mission_id=mission_id, components=delivery_components),
    id=delivery_workflow_id(mission_id),
    task_queue=ORCHESTRATION_QUEUE,
)
self._progress_pct = 50.0
# ... INTEGRATION (75%) ... LAUNCH_READINESS (100%)
```

**Why this matters:** The parent workflow is durable — if the process crashes
mid-delivery, Temporal replays events and resumes exactly where it left off.
The parent's state (phase, progress) is always queryable even during long waits
for human input in child workflows.

**What to show in the Temporal UI:** Open the mission workflow and expand the
child workflow tree. You'll see each phase as a nested execution with its own
event history.

---

## 2. Fan-Out / Fan-In (Parallel Child Workflows)

**Pattern:** Start multiple child workflows concurrently with
`start_child_workflow` (returns a handle immediately), then await all results.

**File:** `workflows/procurement.py:102-126`

```python
# Start one RFP child workflow per component — all launch concurrently
handles = []
for comp in components:
    handle = await workflow.start_child_workflow(
        RFPWorkflow.run,
        RFPInput(
            mission_id=input.mission_id,
            component_name=comp.component_name,
            component_type=comp.component_type,
            eligible_contractors=contractors_by_type.get(comp.component_type, []),
        ),
        id=rfp_workflow_id(input.mission_id, comp_slug),
        task_queue=ORCHESTRATION_QUEUE,
    )
    handles.append((comp.component_name, handle))

# Wait for all RFPs to complete (fan-in)
for comp_name, handle in handles:
    result: RFPResult = await handle
    self._awards[comp_name] = result.winning_contractor_slug
```

The same pattern appears in `workflows/delivery.py:73-95` for parallel
component transports.

**Key distinction:** `start_child_workflow` returns immediately (the child runs
concurrently). `execute_child_workflow` blocks until the child finishes. The
fan-out pattern uses `start` to launch all children, then `await handle` to
collect results.

---

## 3. Human-in-the-Loop (Signals + wait_condition)

**Pattern:** A workflow blocks on `wait_condition` until a human (via the REST
API) sends a signal. This is how Temporal models human tasks.

**File:** `workflows/procurement.py:331-356`

```python
# Inside RFPWorkflow.run() — after LLM generates and evaluates proposals:

# Block until a human awards the contract
await workflow.wait_condition(lambda: self._award is not None)

# ...later in the same class:
@workflow.signal
async def award_contract(self, decision: AwardDecision) -> None:
    """Signal: NASA awards the contract to a contractor."""
    self._award = decision
```

The workflow can block for seconds, hours, or months — Temporal handles it. The
REST API sends the signal when the user clicks "Award" in the UI:

**File:** `services/tasks.py:44-51` (signal from API)

```python
handle = temporal_client.get_workflow_handle(wf_id)
await handle.signal(
    "task_completion",
    TaskCompletionInput(
        task_name=task.name,
        outcome=signal_outcome,
        details=f"Completed by {username}",
    ),
)
```

### Sequential human review chain

`workflows/launch_readiness.py:50-137` demonstrates two sequential human gates:

```python
# Gate 1: Tech Authority must approve before Gate 2 is even offered
await workflow.wait_condition(lambda: self._inspection_decision is not None)

if not self._inspection_decision.approved:
    return LaunchReadinessOutput(approved=False, ...)  # early exit

# Gate 2: Program Manager final go/no-go
await workflow.wait_condition(lambda: self._readiness_decision is not None)
```

### Lambda closure in a loop

`workflows/integration.py:132-136` — when waiting for multiple steps inside a
loop, the lambda must capture the current value:

```python
for step in input.steps:
    self._step_completion_signals[step.name] = False
    await workflow.wait_condition(
        # Default parameter captures step.name by value, not by reference
        lambda step_name=step.name: self._step_completion_signals.get(step_name, False)
    )
```

Without `step_name=step.name`, all lambdas would close over the same loop
variable and only the last step would work.

---

## 4. Inter-Workflow Communication (External Handles)

**Pattern:** One running workflow signals another running workflow via
`get_external_workflow_handle`. This is how workflows collaborate without
sharing state.

### Request/response between workflows

IntegrationWorkflow requests a facility reservation from
FacilityManagerWorkflow, which processes the request and signals back.

**File:** `workflows/integration.py:91-105` (requester side)

```python
# Get a handle to the facility manager workflow (already running)
facility_handle = workflow.get_external_workflow_handle(
    facility_workflow_id(input.facility_slug)
)

# Send reservation request
await facility_handle.signal(
    RESERVE_FACILITY_SIGNAL,
    FacilityReservationRequest(
        requesting_workflow_id=wf_id,  # so facility can signal us back
        mission_id=input.mission_id,
        purpose="Integration",
    ),
)

# Block until the facility grants our reservation
await workflow.wait_condition(lambda: self._facility_granted)
```

**File:** `workflows/facility_manager.py:116-127` (responder side)

```python
# Grant reservation and signal back to the requesting workflow
handle = workflow.get_external_workflow_handle(
    next_req.requesting_workflow_id
)
await handle.signal(
    FACILITY_RESERVED_SIGNAL,
    FacilityReservationResponse(
        granted=True,
        facility_slug=self._slug,
        message=f"Reservation granted at {self._name}",
    ),
)
```

### Advancing the simulated clock

Multiple workflows advance the clock as tasks complete:

**File:** `workflows/delivery.py:158-165`

```python
clock_handle = workflow.get_external_workflow_handle(CLOCK_WORKFLOW_ID)
await clock_handle.signal(
    "advance_time",
    AdvanceTimeInput(
        seconds=input.nominal_duration_seconds,
        reason=f"Shipped {input.component_name}",
    ),
)
```

---

## 5. Entity Workflow (Long-Lived Singleton with State)

**Pattern:** A workflow that runs forever, processing signals in a loop and
maintaining in-memory state. Conceptually similar to an actor.

### Facility Manager — resource queue

**File:** `workflows/facility_manager.py:85-141`

```python
@workflow.run
async def run(self, input: FacilityWorkflowInput) -> None:
    self._slug = input.slug
    self._capacity = input.capacity

    while True:
        # Block until there's work to do
        await workflow.wait_condition(
            lambda: len(self._pending_requests) > 0
            or len(self._pending_releases) > 0
        )

        # Process releases first (frees capacity for waiting requests)
        while self._pending_releases:
            release = self._pending_releases.pop(0)
            self._occupants.remove(release.workflow_id)

        # Enqueue new requests
        while self._pending_requests:
            self._queue.append(self._pending_requests.pop(0))

        # Grant from FIFO queue while capacity allows
        while self._queue and len(self._occupants) < self._capacity:
            next_req = self._queue.pop(0)
            self._occupants.append(next_req.requesting_workflow_id)
            # Signal back to requester (see Pattern 4 above)

        # Persist to DB and check continue-as-new threshold
```

This workflow manages facility capacity as a FIFO queue. Multiple integration
workflows can contend for the same facility — the facility manager serializes
access and signals each requester when their turn comes.

### Simulated Clock — event-driven singleton

**File:** `workflows/clock.py:49-73`

```python
@workflow.run
async def run(self, input: ClockWorkflowInput) -> None:
    self._current_time = datetime.fromisoformat(input.initial_time_iso)

    while True:
        await workflow.wait_condition(lambda: len(self._pending_advances) > 0)

        while self._pending_advances:
            advance = self._pending_advances.pop(0)
            self._current_time += timedelta(seconds=advance.seconds)
            # Persist to DB after each advance
```

Any workflow or API endpoint can signal `advance_time` and query
`get_current_time`. The clock has a single source of truth that's
durable across restarts.

---

## 6. continue-as-new (Bounded Event History)

**Pattern:** Long-lived workflows accumulate events. After a threshold,
`continue_as_new` atomically starts a fresh execution with the current state,
resetting the event history to zero.

**File:** `workflows/clock.py:70-73`

```python
CONTINUE_AS_NEW_THRESHOLD = 500

# Inside the main loop:
if self._advance_count >= CONTINUE_AS_NEW_THRESHOLD:
    workflow.continue_as_new(
        ClockWorkflowInput(initial_time_iso=self._current_time.isoformat())
    )
```

**File:** `workflows/facility_manager.py:140-141`

```python
CONTINUE_AS_NEW_THRESHOLD = 200

if self._event_count >= CONTINUE_AS_NEW_THRESHOLD:
    workflow.continue_as_new(input)
```

**Why this matters:** Without continue-as-new, a workflow running for weeks
would accumulate millions of events. Replay would get slower and eventually hit
Temporal's history size limit. The threshold values (200-500) are conservative —
production systems tune these based on event size.

**Key detail:** The clock carries forward `self._current_time` in the new input.
The facility manager can reuse `input` directly because its state is derived
from signals (occupants and queue will be empty at continue-as-new time since
all pending work was just processed).

---

## 7. Task Queue Routing (Multi-Worker Architecture)

**Pattern:** Different activity types run on different task queues, processed by
dedicated workers. This prevents slow operations from starving fast ones.

**File:** `workflows/data_types.py:12-17` (queue constants)

```python
ORCHESTRATION_QUEUE = "artemis-orchestration"   # fast DB ops, workflow logic
LLM_QUEUE = "artemis-llm"                       # slow LLM generation (up to 600s)
SIMULATION_QUEUE = "artemis-simulation"          # reserved for future use
NOTIFICATION_QUEUE = "artemis-notifications"     # reserved for future use
```

**File:** `workflows/procurement.py:194-203` (routing an activity to the LLM queue)

```python
rfp_result = await workflow.execute_activity(
    generate_rfp,
    GenerateRFPInput(...),
    start_to_close_timeout=timedelta(seconds=600),  # LLM can be slow
    task_queue=LLM_QUEUE,                            # route to LLM worker
)
```

**File:** `workers/main.py:83-88` (orchestration worker — handles everything)

```python
worker = Worker(
    client,
    task_queue=settings.temporal_orchestration_queue,
    workflows=ALL_WORKFLOWS,     # 10 workflow types
    activities=ALL_ACTIVITIES,   # 16 activity types
)
```

**File:** `workers/llm_worker.py:27-37` (LLM worker — activities only, no workflows)

```python
worker = Worker(
    client,
    task_queue=settings.temporal_llm_queue,
    activities=[
        generate_rfp,
        generate_rubric,
        generate_proposal,
        evaluate_proposal,
        generate_test_report,
    ],
)
```

**Why two workers?** LLM calls take 10-600 seconds. If they ran on the
orchestration queue, a burst of LLM requests would block all DB persistence
activities (10s timeout), stalling every workflow. The dedicated LLM worker
isolates this latency.

---

## 8. Deterministic Workflow IDs

**Pattern:** Every workflow gets a predictable, human-readable ID. This enables
idempotent starts, external handle lookups, and easy Temporal UI navigation.

**File:** `workflows/data_types.py:20-56`

```python
CLOCK_WORKFLOW_ID = "clock-global"

def mission_workflow_id(mission_id: str) -> str:
    return f"mission-{mission_id}"

def facility_workflow_id(facility_slug: str) -> str:
    return f"facility-{facility_slug}"

def rfp_workflow_id(mission_id: str, component_type: str) -> str:
    return f"rfp-{mission_id}-{component_type}"

def transport_workflow_id(mission_id: str, component_name: str) -> str:
    slug = component_name.lower().replace(" ", "-").replace("(", "").replace(")", "")
    return f"transport-{mission_id}-{slug}"
```

This hierarchy is visible in the Temporal UI as a browsable tree:

```
clock-global
facility-the-garage
mission-abc123
  ├── procurement-abc123
  │    ├── rfp-abc123-b-class-solid-motor
  │    ├── rfp-abc123-plastic-parachute
  │    └── ...
  ├── delivery-abc123
  │    ├── transport-abc123-b-class-solid-motor
  │    └── ...
  ├── integration-abc123
  └── launch-readiness-abc123
```

**Why this matters:**
- **Idempotent starts:** Starting `mission-abc123` twice is a no-op (Temporal
  rejects duplicate IDs).
- **External handles:** Any workflow can get a handle to `clock-global` without
  storing the workflow ID — it's derived from convention.
- **Debugging:** Find any workflow instantly in the UI by its business ID.

---

## 9. Queries for Live Workflow State

**Pattern:** `@workflow.query` exposes read-only state from a running workflow
without affecting its execution. The REST API queries workflows directly instead
of polling a database.

**File:** `workflows/mission.py:240-249`

```python
@workflow.query
def get_state(self) -> MissionState:
    return MissionState(
        mission_id=self._mission_id,
        name=self._name,
        phase=self._phase.value,
        status=self._status,
        progress_pct=self._progress_pct,
    )
```

**File:** `services/clock.py:26-31` (querying from the API)

```python
handle = temporal_client.get_workflow_handle(CLOCK_WORKFLOW_ID)
time_iso = await handle.query(SimulatedClockWorkflow.get_current_time)
```

Every workflow in the system exposes at least one query:

| Workflow | Query | Returns |
|----------|-------|---------|
| MissionWorkflow | `get_state()` | Phase, progress %, status |
| ProcurementWorkflow | `get_progress()` | "3/5 components awarded" |
| RFPWorkflow | `get_rfp_state()` | Which LLM artifacts exist, whether awarded |
| DeliveryWorkflow | `get_progress()` | "2/5 components delivered" |
| TransportWorkflow | `get_status()` | Shipped/received/inspected booleans |
| IntegrationWorkflow | `get_integration_state()` | Current step, completed steps |
| LaunchReadinessWorkflow | `get_readiness_state()` | Inspection and readiness decisions |
| SimulatedClockWorkflow | `get_current_time()` | ISO timestamp |
| FacilityManagerWorkflow | `get_status()` | Capacity, occupancy, queue depth |

---

## 10. Workflow Lifecycle from the REST API

### Starting workflows

**File:** `services/missions.py:70-76` (creating a mission starts its workflow)

```python
wf_id = mission_workflow_id(str(mission.id))
await temporal_client.start_workflow(
    MissionWorkflow.run,
    args=[str(mission.id), architecture_type],
    id=wf_id,
    task_queue=ORCHESTRATION_QUEUE,
)
```

### Starting system workflows on app boot

**File:** `main.py:20-69`

```python
async def _ensure_system_workflows(client, settings) -> None:
    async def _is_running(workflow_id: str) -> bool:
        try:
            handle = client.get_workflow_handle(workflow_id)
            desc = await handle.describe()
            return desc.status == WorkflowExecutionStatus.RUNNING
        except RPCError:
            return False

    if not await _is_running(CLOCK_WORKFLOW_ID):
        await client.start_workflow(SimulatedClockWorkflow.run, ...)

    for slug, name, capacity in mvp_facilities:
        if not await _is_running(f"facility-{slug}"):
            await client.start_workflow(FacilityManagerWorkflow.run, ...)
```

### Listing and terminating workflows (admin reset)

**File:** `api/admin.py:21-33`

```python
async def _terminate_all_workflows(client) -> int:
    terminated = 0
    async for wf in client.list_workflows('ExecutionStatus="Running"'):
        handle = client.get_workflow_handle(wf.id, run_id=wf.run_id)
        await handle.terminate(reason="Simulation reset")
        terminated += 1
    return terminated
```

---

## 11. Activity Design Patterns

### Timeout strategy

Activities use `start_to_close_timeout` calibrated to their workload:

| Activity Type | Timeout | Rationale |
|---------------|---------|-----------|
| DB persistence | 10s | Fast queries, fail fast on DB issues |
| Task creation (setup) | 30s | Bulk inserts for a new mission |
| LLM generation | 600s | LLM inference can be slow, especially local models |
| Simulation (inspection) | 10s | Pure compute, no I/O |
| Clock/facility persist | 10s | Single-row updates |

### Import isolation (workflow-safe imports)

**File:** `workflows/mission.py:12-19`

```python
with workflow.unsafe.imports_passed_through():
    from artemis.activities.persistence import (
        create_mission_tasks,
        update_mission_status,
    )
```

Activities import database libraries, HTTP clients, etc. — things that aren't
deterministic. The `unsafe.imports_passed_through()` context tells the Temporal
SDK to pass these imports through without sandboxing, since they're only used as
activity references (the actual code runs in the worker, not the workflow).

### Deferred imports inside activities

**File:** `activities/persistence.py:63-66`

```python
@activity.defn
async def create_mission_tasks(input: CreateMissionTasksInput) -> CreateMissionTasksResult:
    from sqlalchemy import select
    from artemis.database import async_session_factory
    from artemis.models.mission import Mission
```

Activities import heavy dependencies at call time rather than module level.
This keeps workflow modules importable without pulling in SQLAlchemy, and avoids
module-level side effects during workflow replay.

---

## 12. Data Contract Design

**File:** `workflows/data_types.py`

All inter-workflow and activity communication uses `@dataclass` types. This
single file defines every contract in the system:

- **Signal payloads:** `AwardDecision`, `ReviewDecision`,
  `FacilityReservationRequest`, `AdvanceTimeInput`, etc.
- **Activity inputs/outputs:** `CreateMissionTasksInput`, `LLMResult`,
  `RunInspectionInput`, etc.
- **Query responses:** `MissionState`, `FacilityStatusResponse`
- **Workflow-safe enums:** `MissionPhase`, `TaskStatusW` (duplicated from DB
  enums to avoid importing SQLAlchemy)

**Why a separate file?** Workflow code must be deterministic — it can't import
database models, HTTP clients, or anything with side effects. Putting all data
types in one import-safe module avoids circular dependencies and keeps the
workflow sandbox clean.

---

## Patterns Not Yet Used (Extension Ideas)

These are Temporal capabilities that Artemis doesn't use yet but could be
added for a richer demo:

| Pattern | What it does | Where it could apply |
|---------|-------------|---------------------|
| `@workflow.update` | Synchronous request/response to a running workflow (returns a result, unlike signals) | Replace signal+wait_condition pairs for contract award — caller gets confirmation inline |
| RetryPolicy | Automatic retries with backoff for failing activities | LLM activities (transient API errors, rate limits) |
| Heartbeats | Long-running activities report progress; auto-cancel on missed heartbeat | LLM generation could report token count progress |
| Search Attributes | Tag workflows with queryable metadata | Filter by mission phase, contractor, or status in the Temporal UI |
| Saga / Compensation | Undo completed steps when a later step fails | Roll back integration steps if a test fails mid-assembly |
| `workflow.sleep` | Timer-based delays | Simulated shipping delays instead of instant clock advances |
| Schedules | Cron-like recurring workflow execution | Periodic status reports, health checks |
| Side Effects | Non-deterministic operations inside workflows (e.g., UUID generation) | Currently handled by activities, but `workflow.side_effect` is more lightweight |

---

## Demo Walkthrough

For a live demo or talk, this sequence tells a clear story:

1. **Start here:** `workflows/mission.py` — show the 4-phase parent/child
   structure. Run a mission and watch the Temporal UI build the workflow tree.

2. **Zoom into procurement:** `workflows/procurement.py` — fan-out 5 RFP
   workflows. Show them running concurrently in the UI. Point out the LLM
   activities on the separate task queue.

3. **Human-in-the-loop:** Signal an `award_contract` via the REST API or UI.
   Watch the blocked `wait_condition` unblock and the workflow proceed.

4. **Inter-workflow communication:** `workflows/integration.py` requests a
   facility from `workflows/facility_manager.py`. Show the signal exchange in
   both workflows' event histories.

5. **Entity workflow + continue-as-new:** `workflows/clock.py` — query the
   current time, signal an advance, query again. Show the continue-as-new
   event in the history after many advances.

6. **Worker architecture:** Show two terminal panes: orchestration worker
   and LLM worker. Kill the LLM worker — workflows keep running but LLM
   activities queue up. Restart it — they resume automatically.

7. **Admin reset:** `api/admin.py` — terminate all workflows, wipe DB,
   restart system workflows. Show the full lifecycle.
