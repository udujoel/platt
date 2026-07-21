"""Import and route-mount checks for the Vercel Python Function entrypoint.

api/index.py lives outside the `backend` package (it is the deployment
entrypoint Vercel builds directly), so it is loaded here via its file path
rather than a normal import, mirroring how Vercel's Python runtime loads it.
"""

import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

API_INDEX_PATH = Path(__file__).resolve().parents[2] / "api" / "index.py"


@pytest.fixture
def vercel_app():
    spec = importlib.util.spec_from_file_location("vercel_api_index", API_INDEX_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        with TestClient(module.app) as client:
            yield client
    finally:
        sys.modules.pop(spec.name, None)


def test_backend_app_mounts_under_api_prefix(vercel_app: TestClient) -> None:
    response = vercel_app.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_is_reachable_under_api_prefix(vercel_app: TestClient) -> None:
    response = vercel_app.get("/api/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "persistence": "ok"}


def test_unprefixed_health_is_not_routed(vercel_app: TestClient) -> None:
    response = vercel_app.get("/health")

    assert response.status_code == 404
