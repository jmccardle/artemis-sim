"""Simulation activities — automated pass/fail checks and data generation."""
from __future__ import annotations

import random
from dataclasses import dataclass

from temporalio import activity


@dataclass
class RunInspectionInput:
    task_id: str
    task_name: str
    failure_probability: float


@dataclass
class RunInspectionResult:
    task_id: str
    passed: bool
    details: str = ""


@activity.defn
async def run_inspection(input: RunInspectionInput) -> RunInspectionResult:
    """Run an automated inspection with configurable failure probability."""
    passed = random.random() >= input.failure_probability

    if passed:
        details = f"Inspection '{input.task_name}' passed all acceptance criteria."
    else:
        details = (
            f"Inspection '{input.task_name}' FAILED. "
            f"Component did not meet acceptance criteria. Rework required."
        )

    return RunInspectionResult(
        task_id=input.task_id,
        passed=passed,
        details=details,
    )


@dataclass
class SimulateDurationInput:
    task_id: str
    task_name: str
    nominal_duration_seconds: int
    speed_factor: float = 1.0
    difficulty_factor: float = 1.0


@dataclass
class SimulateDurationResult:
    task_id: str
    duration_seconds: int
    nominal_seconds: int
    escalated: bool = False
    escalation_level: str = "none"


@activity.defn
async def simulate_task_duration(input: SimulateDurationInput) -> SimulateDurationResult:
    """Simulate a variable task duration using lognormal model."""
    from artemis.activities.delay_model import compute_actual_duration, get_escalation_level

    actual = compute_actual_duration(
        input.nominal_duration_seconds,
        speed_factor=input.speed_factor,
        difficulty_factor=input.difficulty_factor,
    )
    level = get_escalation_level(actual, input.nominal_duration_seconds)

    return SimulateDurationResult(
        task_id=input.task_id,
        duration_seconds=actual,
        nominal_seconds=input.nominal_duration_seconds,
        escalated=level != "none",
        escalation_level=level,
    )
