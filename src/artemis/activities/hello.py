from dataclasses import dataclass

from temporalio import activity


@dataclass
class SayHelloInput:
    name: str


@activity.defn
async def say_hello(input: SayHelloInput) -> str:
    activity.logger.info(f"Saying hello to {input.name}")
    return f"Hello, {input.name}! Welcome to Artemis Mission Simulation."
