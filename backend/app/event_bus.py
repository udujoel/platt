import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.models import Event


@dataclass(frozen=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[Event]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[_Subscriber] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: Event) -> None:
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

