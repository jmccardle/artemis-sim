"""FacilityManagerWorkflow — manages facility reservations and capacity.

One instance per facility. Workflow ID: "facility-{slug}"
Task queue: artemis-orchestration
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from artemis.activities.facility import PersistFacilityInput, persist_facility_state


RESERVE_FACILITY_SIGNAL = "reserve_facility"
RELEASE_FACILITY_SIGNAL = "release_facility"
FACILITY_RESERVED_SIGNAL = "facility_reserved"
GET_FACILITY_STATUS_QUERY = "get_facility_status"

CONTINUE_AS_NEW_THRESHOLD = 200


@dataclass
class FacilityWorkflowInput:
    """Workflow start input."""
    slug: str
    name: str
    capacity: int


@dataclass
class FacilityReservationRequest:
    """Signal payload: request a facility reservation."""
    requesting_workflow_id: str
    mission_id: str
    purpose: str


@dataclass
class FacilityReservationResponse:
    """Signal payload sent back to requesting workflow."""
    granted: bool
    facility_slug: str
    message: str = ""


@dataclass
class FacilityReleaseInput:
    """Signal payload: release a facility reservation."""
    workflow_id: str


@dataclass
class FacilityStatusResponse:
    """Query response."""
    slug: str
    name: str
    capacity: int
    current_occupancy: int
    queue_depth: int
    occupants: list[str] = field(default_factory=list)


@workflow.defn
class FacilityManagerWorkflow:
    """Manages a single facility's capacity and reservation queue.

    Integration workflows request reservations via signal. When capacity
    is available, grants by signaling back to requesting workflow.
    On release, checks queue for waiting requests.
    """

    def __init__(self) -> None:
        self._slug: str = ""
        self._name: str = ""
        self._capacity: int = 1
        self._occupants: list[str] = []
        self._queue: list[FacilityReservationRequest] = []
        self._pending_requests: list[FacilityReservationRequest] = []
        self._pending_releases: list[FacilityReleaseInput] = []
        self._event_count: int = 0

    @workflow.run
    async def run(self, input: FacilityWorkflowInput) -> None:
        self._slug = input.slug
        self._name = input.name
        self._capacity = input.capacity

        while True:
            # Wait for any signal
            await workflow.wait_condition(
                lambda: len(self._pending_requests) > 0
                or len(self._pending_releases) > 0
            )

            # Process releases first (frees capacity)
            while self._pending_releases:
                release = self._pending_releases.pop(0)
                if release.workflow_id in self._occupants:
                    self._occupants.remove(release.workflow_id)
                self._event_count += 1

            # Enqueue new reservation requests
            while self._pending_requests:
                request = self._pending_requests.pop(0)
                self._queue.append(request)
                self._event_count += 1

            # Grant queued reservations (FIFO) while capacity allows
            while self._queue and len(self._occupants) < self._capacity:
                next_req = self._queue.pop(0)
                self._occupants.append(next_req.requesting_workflow_id)

                # Signal back to requesting workflow
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

            # Persist state to DB
            await workflow.execute_activity(
                persist_facility_state,
                PersistFacilityInput(
                    facility_name=self._name,
                    current_occupancy=len(self._occupants),
                ),
                start_to_close_timeout=timedelta(seconds=10),
            )

            # Continue-as-new if needed
            if self._event_count >= CONTINUE_AS_NEW_THRESHOLD:
                workflow.continue_as_new(input)

    @workflow.signal(name=RESERVE_FACILITY_SIGNAL)
    async def reserve(self, request: FacilityReservationRequest) -> None:
        """Signal: request a facility reservation."""
        self._pending_requests.append(request)

    @workflow.signal(name=RELEASE_FACILITY_SIGNAL)
    async def release(self, input: FacilityReleaseInput) -> None:
        """Signal: release a facility reservation."""
        self._pending_releases.append(input)

    @workflow.query(name=GET_FACILITY_STATUS_QUERY)
    def get_status(self) -> FacilityStatusResponse:
        """Query: current facility state."""
        return FacilityStatusResponse(
            slug=self._slug,
            name=self._name,
            capacity=self._capacity,
            current_occupancy=len(self._occupants),
            queue_depth=len(self._queue),
            occupants=list(self._occupants),
        )
