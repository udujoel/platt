"""Lifecycle-aware helpers for application background jobs."""

import asyncio
import logging
from collections.abc import Awaitable
from typing import Any

from fastapi import FastAPI


logger = logging.getLogger(__name__)


def create_background_task(app: FastAPI, awaitable: Awaitable[Any]) -> asyncio.Task[Any]:
    """Start a job owned by ``app`` and observe any exception it raises."""
    task = asyncio.create_task(awaitable)
    app.state.background_tasks.add(task)

    def observe_completion(completed_task: asyncio.Task[Any]) -> None:
        app.state.background_tasks.discard(completed_task)
        if completed_task.cancelled():
            return
        try:
            completed_task.result()
        except Exception as error:
            logger.error("Background task failed", exc_info=error)

    task.add_done_callback(observe_completion)
    return task


async def cancel_background_tasks(tasks: set[asyncio.Task[Any]]) -> None:
    """Cancel outstanding app jobs and wait until their cancellation is complete."""
    pending_tasks = tuple(tasks)
    for task in pending_tasks:
        task.cancel()
    if pending_tasks:
        await asyncio.gather(*pending_tasks, return_exceptions=True)
