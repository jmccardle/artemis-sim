import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from artemis.activities.hello import say_hello
from artemis.config import get_settings
from artemis.workflows.hello import HelloWorkflow


async def run_worker() -> None:
    settings = get_settings()
    client = await Client.connect(settings.temporal_host, namespace=settings.temporal_namespace)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=[HelloWorkflow],
        activities=[say_hello],
    )

    print(f"Worker started on task queue: {settings.temporal_task_queue}")
    await worker.run()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
