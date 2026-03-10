"""In-memory event bus for SSE real-time updates.

Single-process demo implementation. Upgradeable to Redis pub/sub for multi-process.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """An SSE event with type and JSON-serializable data."""

    event_type: str
    data: dict[str, Any]
    id: str | None = None


class EventBus:
    """In-memory pub/sub for broadcasting events to SSE subscribers."""

    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=50)
        async with self._lock:
            self._subscribers.append(queue)
        logger.debug("SSE subscriber added (total: %d)", len(self._subscribers))
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        async with self._lock:
            try:
                self._subscribers.remove(queue)
            except ValueError:
                pass
        logger.debug("SSE subscriber removed (total: %d)", len(self._subscribers))

    async def publish(self, event: Event) -> None:
        async with self._lock:
            dead: list[asyncio.Queue[Event]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead.append(queue)
            for q in dead:
                try:
                    self._subscribers.remove(q)
                except ValueError:
                    pass

    async def stream(self, queue: asyncio.Queue[Event]) -> AsyncGenerator[Event, None]:
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            return
        finally:
            await self.unsubscribe(queue)


# Global singleton
event_bus = EventBus()
