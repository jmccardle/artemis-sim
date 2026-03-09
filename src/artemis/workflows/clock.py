"""SimulatedClockWorkflow — system-wide simulated clock.

Workflow ID: "clock-global" (singleton)
Task queue: artemis-orchestration
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from artemis.activities.clock import PersistClockInput, persist_clock_state


CLOCK_WORKFLOW_ID = "clock-global"
CONTINUE_AS_NEW_THRESHOLD = 500


@dataclass
class AdvanceTimeInput:
    """Signal payload."""
    seconds: int
    reason: str


@dataclass
class ClockWorkflowInput:
    """Workflow start input."""
    initial_time_iso: str


@workflow.defn
class SimulatedClockWorkflow:
    """Singleton workflow managing the system-wide simulated clock.

    Receives advance_time signals when tasks complete.
    Queryable for current simulated time.
    Persists state to DB after each advance.
    Uses continue-as-new to bound event history.
    """

    def __init__(self) -> None:
        self._current_time: datetime = datetime.now(timezone.utc)
        self._advance_count: int = 0
        self._pending_advances: list[AdvanceTimeInput] = []

    @workflow.run
    async def run(self, input: ClockWorkflowInput) -> None:
        self._current_time = datetime.fromisoformat(input.initial_time_iso)

        while True:
            await workflow.wait_condition(lambda: len(self._pending_advances) > 0)

            while self._pending_advances:
                advance = self._pending_advances.pop(0)
                self._current_time += timedelta(seconds=advance.seconds)
                self._advance_count += 1

                await workflow.execute_activity(
                    persist_clock_state,
                    PersistClockInput(
                        current_time_iso=self._current_time.isoformat(),
                        reason=advance.reason,
                    ),
                    start_to_close_timeout=timedelta(seconds=10),
                )

            if self._advance_count >= CONTINUE_AS_NEW_THRESHOLD:
                workflow.continue_as_new(
                    ClockWorkflowInput(initial_time_iso=self._current_time.isoformat())
                )

    @workflow.signal
    async def advance_time(self, input: AdvanceTimeInput) -> None:
        """Signal to advance the clock."""
        self._pending_advances.append(input)

    @workflow.query
    def get_current_time(self) -> str:
        """Query: returns ISO format string of current simulated time."""
        return self._current_time.isoformat()
