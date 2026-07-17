import asyncio
import logging
from collections.abc import AsyncIterator
from collections.abc import Callable
from dataclasses import dataclass

from app.models import Event


logger = logging.getLogger(__name__)


DEFAULT_SUBSCRIBER_QUEUE_SIZE = 100


@dataclass(frozen=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[Event]


class EventBus:
    """Deliver events through bounded subscriber queues without blocking publishers.

    A slow subscriber keeps at most ``subscriber_queue_size`` events.  Once its
    queue is full, newly published events for that subscriber are dropped.
    """

    def __init__(self, subscriber_queue_size: int = DEFAULT_SUBSCRIBER_QUEUE_SIZE) -> None:
        if subscriber_queue_size < 1:
            raise ValueError("subscriber_queue_size must be positive")
        self._subscribers: set[_Subscriber] = set()
        self._lock = asyncio.Lock()
        self._recorder: Callable[[Event], None] | None = None
        self._subscriber_queue_size = subscriber_queue_size

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
        stale_subscribers: list[_Subscriber] = []
        for subscriber in subscribers:
            if subscriber.loop is running_loop:
                self._enqueue(subscriber, event)
            else:
                try:
                    subscriber.loop.call_soon_threadsafe(self._enqueue, subscriber, event)
                except RuntimeError:
                    if subscriber.loop.is_closed():
                        stale_subscribers.append(subscriber)
                    else:
                        logger.exception("Unable to schedule event delivery")

        if stale_subscribers:
            async with self._lock:
                self._subscribers.difference_update(stale_subscribers)

    @staticmethod
    def _enqueue(subscriber: _Subscriber, event: Event) -> None:
        """Enqueue without blocking; drop the newest event when the queue is full."""
        try:
            subscriber.queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Dropping event for slow subscriber because its queue is full")

    async def subscribe(self) -> AsyncIterator[Event]:
        subscriber = _Subscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=self._subscriber_queue_size),
        )
        async with self._lock:
            self._subscribers.add(subscriber)

        try:
            while True:
                yield await subscriber.queue.get()
        finally:
            async with self._lock:
                self._subscribers.discard(subscriber)


event_bus = EventBus()
