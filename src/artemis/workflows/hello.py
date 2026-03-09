from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from artemis.activities.hello import SayHelloInput, say_hello


@workflow.defn
class HelloWorkflow:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say_hello,
            SayHelloInput(name=name),
            start_to_close_timeout=timedelta(seconds=10),
        )
