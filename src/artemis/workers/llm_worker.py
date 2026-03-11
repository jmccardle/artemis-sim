"""LLM activity worker — handles LLM task queue.

Phase 1: Runs stub activities. Phase 3: Real LLM provider calls.
"""
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from artemis.activities.llm import (
    evaluate_proposal,
    generate_proposal,
    generate_rfp,
    generate_rubric,
    generate_test_report,
)
from artemis.config import get_settings


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

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

    print(f"LLM worker started on queue: {settings.temporal_llm_queue}")
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
