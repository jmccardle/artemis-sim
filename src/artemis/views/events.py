"""SSE endpoint for real-time updates to browser clients."""

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from artemis.events import event_bus

router = APIRouter()


@router.get("/events")
async def sse_stream(request: Request):
    """Server-Sent Events stream for real-time dashboard updates."""
    queue = await event_bus.subscribe()

    async def event_generator():
        try:
            async for event in event_bus.stream(queue):
                if await request.is_disconnected():
                    break
                yield {
                    "event": event.event_type,
                    "data": json.dumps(event.data),
                    "id": event.id,
                }
        except asyncio.CancelledError:
            pass
        finally:
            await event_bus.unsubscribe(queue)

    return EventSourceResponse(event_generator())
