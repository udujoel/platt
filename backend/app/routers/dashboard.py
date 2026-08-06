"""HTTP entry points for the platform health dashboard (PRD §F6).

``GET /dashboard`` and ``GET /dashboard/module-graph`` serve the real data
the dashboard UI renders in place of ``seededDashboardData`` /
``seededModuleGraphNodes``. Both are graceful when Azure DevOps isn't
configured: sections that need it come back ``source: "unavailable"`` with
empty data instead of erroring.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import APIRouter, Request

from app.clients.azdo import AzdoClient, AzdoNotConfiguredError
from app.collectors import DashboardPayload, ModuleGraphPayload, collect_dashboard, collect_module_graph

router = APIRouter(tags=["dashboard"])

PIPELINE_IDS_ENV = "PLATT_DASHBOARD_PIPELINE_IDS"


def _seed_infra_path() -> Path:
    return Path(__file__).resolve().parents[3] / "seed-infra"


def _pipeline_ids_from_environment() -> list[int]:
    """Pipelines the dashboard reports on, from a comma-separated env var.

    There is no bound-free "list all pipelines and their runs" query cheap enough
    for the free tier default, so which pipelines to poll is operator-configured,
    the same way ``PLATT_PROVISION_APPLY_PIPELINE_ID`` already is.
    """
    raw = os.environ.get(PIPELINE_IDS_ENV, "").strip()
    if not raw:
        return []
    return [int(part) for part in raw.split(",") if part.strip()]


@router.get("/dashboard", response_model=DashboardPayload)
async def get_dashboard(request: Request) -> DashboardPayload:
    cache = request.app.state.dashboard_cache
    now = time.monotonic()
    cached = cache.get(now=now)
    if cached is not None:
        return cached

    try:
        azdo_client: AzdoClient | None = AzdoClient.from_environment()
    except AzdoNotConfiguredError:
        azdo_client = None

    try:
        payload = await collect_dashboard(
            request.app.state.persistence,
            azdo_client=azdo_client,
            repository_id=request.app.state.provision_repository_id,
            pipeline_ids=_pipeline_ids_from_environment(),
            seed_infra_path=_seed_infra_path(),
        )
    finally:
        if azdo_client is not None:
            await azdo_client.aclose()

    cache.set(payload, now=now)
    return payload


@router.get("/dashboard/module-graph", response_model=ModuleGraphPayload)
def get_dashboard_module_graph(request: Request) -> ModuleGraphPayload:
    return collect_module_graph(request.app.state.persistence)
