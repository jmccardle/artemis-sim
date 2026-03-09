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
