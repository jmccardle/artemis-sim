"""Standard retry policies for Temporal activities."""
from datetime import timedelta

from temporalio.common import RetryPolicy

# LLM activities: retry on transient errors, generous backoff
LLM_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_attempts=3,
    maximum_interval=timedelta(seconds=60),
)

# External system adapter activities: retry on transient errors
ADAPTER_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_attempts=3,
    maximum_interval=timedelta(seconds=30),
)

# DB persistence activities: fast retry for transient hiccups
PERSISTENCE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=1.5,
    maximum_attempts=5,
    maximum_interval=timedelta(seconds=10),
)

# Simulation activities: no retry (probabilistic outcomes should not be retried)
SIMULATION_NO_RETRY = RetryPolicy(maximum_attempts=1)
