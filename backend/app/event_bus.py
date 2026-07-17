import asyncio
import logging
from collections.abc import AsyncIterator
from collections.abc import Callable
from dataclasses import dataclass

from app.models import Event


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[Event]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[_Subscriber] = set()
        self._lock = asyncio.Lock()
        self._recorder: Callable[[Event], None] | None = None

    def set_recorder(self, recorder: Callable[[Event], None] | None) -> None:
        self._recorder = recorder

    def clear_recorder(self, recorder: Callable[[Event], None]) -> None:
        """Clear a recorder only when it is still the active app's recorder."""
        if self._recorder is recorder:
            self._recorder = None

    async def publish(self, event: Event) -> None:
        """Record and deliver an event; recording is synchronous for the low-throughput local path."""
        if self._recorder:
            try:
                self._recorder(event)
            except Exception:
                logger.exception("Unable to record event; continuing delivery to subscribers")

        async with self._lock:
            subscribers = tuple(self._subscribers)

        running_loop = asyncio.get_running_loop()
        for subscriber in subscribers:
            if subscriber.loop is running_loop:
                subscriber.queue.put_nowait(event)
            else:
                subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, event)

    async def subscribe(self) -> AsyncIterator[Event]:
        subscriber = _Subscriber(loop=asyncio.get_running_loop(), queue=asyncio.Queue())
        async with self._lock:
            self._subscribers.add(subscriber)

        try:
            while True:
                yield await subscriber.queue.get()
        finally:
            async with self._lock:
                self._subscribers.discard(subscriber)


event_bus = EventBus()
