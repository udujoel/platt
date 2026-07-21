import asyncio
import contextlib
import os
import time
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from starlette.responses import StreamingResponse

from app.event_bus import event_bus

router = APIRouter(prefix="/events", tags=["events"])

SSE_MAX_SECONDS_ENV = "PLATT_SSE_MAX_SECONDS"
SSE_KEEPALIVE_SECONDS_ENV = "PLATT_SSE_KEEPALIVE_SECONDS"
DEFAULT_SSE_MAX_SECONDS = 25.0
DEFAULT_SSE_KEEPALIVE_SECONDS = 15.0


def _resolve_positive_float(env_var: str, default: float) -> float:
    raw = os.environ.get(env_var)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _parse_last_event_id(last_event_id: str | None) -> int:
    if last_event_id and last_event_id.strip().isdigit():
        return int(last_event_id.strip())
    return 0


def _format_sse(seq: int, event_type: str, payload: str) -> str:
    return f"id: {seq}\nevent: {event_type}\ndata: {payload}\n\n"


async def _stream_events(request: Request, last_seq: int, job_id: UUID | None) -> AsyncIterator[str]:
    persistence = request.app.state.persistence
    max_seconds = _resolve_positive_float(SSE_MAX_SECONDS_ENV, DEFAULT_SSE_MAX_SECONDS)
    keepalive_seconds = _resolve_positive_float(SSE_KEEPALIVE_SECONDS_ENV, DEFAULT_SSE_KEEPALIVE_SECONDS)
    deadline = time.monotonic() + max_seconds

    subscription = event_bus.subscribe()
    pending_next: asyncio.Task | None = None
    try:
        backfill = await asyncio.to_thread(persistence.list_events_since, last_seq, job_id)
        for row in backfill:
            if await request.is_disconnected():
                return
            yield _format_sse(row["seq"], row["type"], row["payload"])
            last_seq = row["seq"]

        next_keepalive = time.monotonic() + keepalive_seconds
        while True:
            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                return
            if await request.is_disconnected():
                return

            if pending_next is None:
                pending_next = asyncio.ensure_future(subscription.__anext__())

            wait_timeout = max(0.0, min(remaining, next_keepalive - now))
            done, _pending = await asyncio.wait({pending_next}, timeout=wait_timeout)

            if pending_next not in done:
                if time.monotonic() >= next_keepalive:
                    yield ": keep-alive\n\n"
                    next_keepalive = time.monotonic() + keepalive_seconds
                continue

            resolved_task, pending_next = pending_next, None
            try:
                event = resolved_task.result()
            except StopAsyncIteration:
                return

            if job_id is not None and getattr(event, "job_id", None) != job_id:
                continue

            seq = await asyncio.to_thread(persistence.get_event_seq, event.id)
            if seq is None or seq <= last_seq:
                # Already delivered during backfill, or not yet durably recorded.
                continue
            yield _format_sse(seq, event.type, event.model_dump_json())
            last_seq = seq
    finally:
        if pending_next is not None:
            pending_next.cancel()
            with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
                await pending_next
        await subscription.aclose()


@router.get("/stream")
async def stream_events(
    request: Request,
    job_id: Annotated[UUID | None, Query()] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Bounded SSE delivery of the same events the WebSocket streams.

    Runs for at most ``PLATT_SSE_MAX_SECONDS`` (default 25s) so a single
    invocation stays short enough for a serverless function; the client is
    expected to reconnect with ``Last-Event-ID`` to resume where it left off.
    """
    return StreamingResponse(
        _stream_events(request, _parse_last_event_id(last_event_id), job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
