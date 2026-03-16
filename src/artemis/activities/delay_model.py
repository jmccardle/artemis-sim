"""Duration variability model for task simulation.

Uses lognormal distribution to model realistic task duration variance.
No Temporal or I/O dependencies — safe to import anywhere.
"""
import math
import random


def compute_actual_duration(
    nominal_seconds: int,
    speed_factor: float = 1.0,
    difficulty_factor: float = 1.0,
) -> int:
    """Compute a variable actual duration from a nominal duration.

    Uses lognormal distribution so that:
    - Median ≈ nominal_seconds * speed_factor * difficulty_factor
    - ~15% of tasks take >1.5x nominal
    - ~3% of tasks take >2x nominal
    - Tasks never complete in < 10% of nominal (hard floor)

    Args:
        nominal_seconds: The expected/planned duration in seconds.
        speed_factor: Contractor speed multiplier (< 1.0 = faster, > 1.0 = slower).
        difficulty_factor: Task-specific difficulty multiplier.

    Returns:
        Actual duration in seconds (always >= 1).
    """
    if nominal_seconds <= 0:
        return 0

    adjusted = nominal_seconds * speed_factor * difficulty_factor
    mu = math.log(adjusted)
    sigma = 0.3  # Gives ~15% chance of >1.5x, ~3% chance of >2x

    actual = random.lognormvariate(mu, sigma)

    # Hard floor at 10% of nominal to prevent unrealistically fast completion
    floor = nominal_seconds * 0.1
    actual = max(actual, floor)

    return max(1, int(actual))


def is_escalation_needed(
    actual_seconds: int,
    nominal_seconds: int,
    threshold_multiplier: float = 2.0,
) -> bool:
    """Check if actual duration exceeds escalation threshold."""
    if nominal_seconds <= 0:
        return False
    return actual_seconds > nominal_seconds * threshold_multiplier


def get_escalation_level(actual_seconds: int, nominal_seconds: int) -> str:
    """Determine escalation severity based on duration overrun.

    Returns: "none", "warning" (1.5x), "critical" (2x), or "halt" (3x).
    """
    if nominal_seconds <= 0:
        return "none"
    ratio = actual_seconds / nominal_seconds
    if ratio >= 3.0:
        return "halt"
    if ratio >= 2.0:
        return "critical"
    if ratio >= 1.5:
        return "warning"
    return "none"
