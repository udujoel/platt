import asyncio
from typing import Any
from uuid import uuid4

import pytest

from app.models import Event
from app.persistence import Persistence
from app.tools.research import (
    ResearchError,
    fetch_latest_provider_version,
    fetch_provider_release_notes,
)


class CapturingBus:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-research-test.db")
    try:
        yield instance
    finally:
        instance.close()


def make_fetcher(responses: dict[str, Any]):
    async def _fetch(url: str) -> Any:
        if url not in responses:
            raise AssertionError(f"unexpected URL fetched: {url}")
        result = responses[url]
        if isinstance(result, Exception):
            raise result
        return result

    return _fetch


def test_fetch_latest_provider_version_returns_the_highest_semver(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        fetcher = make_fetcher(
            {
                "https://registry.terraform.io/v1/providers/hashicorp/azurerm/versions": {
                    "versions": [{"version": "4.9.0"}, {"version": "4.10.0"}, {"version": "3.99.0"}]
                }
            }
        )

        info = await fetch_latest_provider_version(fetcher, persistence, job_id=job_id, event_bus=bus)

        assert info.namespace == "hashicorp"
        assert info.name == "azurerm"
        assert info.latest_version == "4.10.0"

        audit_entries = persistence.list_audit_entries(job_id)
        assert len(audit_entries) == 1
        assert audit_entries[0]["tool"] == "research"
        assert audit_entries[0]["action"] == "fetch_latest_provider_version"
        assert "succeeded" in audit_entries[0]["outcome"]
        assert any(event.type == "audit_entry" for event in bus.events)

    asyncio.run(_run())


def test_fetch_latest_provider_version_raises_and_audits_on_transport_failure(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        fetcher = make_fetcher(
            {"https://registry.terraform.io/v1/providers/hashicorp/azurerm/versions": RuntimeError("timeout")}
        )

        with pytest.raises(ResearchError, match="failed to fetch provider versions"):
            await fetch_latest_provider_version(fetcher, persistence, job_id=job_id, event_bus=bus)

        audit_entries = persistence.list_audit_entries(job_id)
        assert len(audit_entries) == 1
        assert "error" in audit_entries[0]["outcome"]

    asyncio.run(_run())


def test_fetch_latest_provider_version_raises_on_empty_version_list(persistence: Persistence) -> None:
    async def _run() -> None:
        fetcher = make_fetcher({"https://registry.terraform.io/v1/providers/hashicorp/azurerm/versions": {"versions": []}})

        with pytest.raises(ResearchError, match="no versions"):
            await fetch_latest_provider_version(fetcher, persistence)

    asyncio.run(_run())


def test_fetch_latest_provider_version_respects_custom_namespace_and_name(persistence: Persistence) -> None:
    async def _run() -> None:
        fetcher = make_fetcher(
            {
                "https://registry.terraform.io/v1/providers/myorg/mycloud/versions": {
                    "versions": [{"version": "1.2.3"}]
                }
            }
        )

        info = await fetch_latest_provider_version(fetcher, persistence, namespace="myorg", name="mycloud")

        assert info.latest_version == "1.2.3"

    asyncio.run(_run())


def test_fetch_provider_release_notes_returns_the_release_body(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        fetcher = make_fetcher(
            {
                "https://api.github.com/repos/hashicorp/terraform-provider-azurerm/releases/tags/v4.10.0": {
                    "body": "## 4.10.0\n\nBREAKING CHANGES: none."
                }
            }
        )

        notes = await fetch_provider_release_notes(fetcher, persistence, version="4.10.0", job_id=job_id, event_bus=bus)

        assert "BREAKING CHANGES" in notes
        audit_entries = persistence.list_audit_entries(job_id)
        assert len(audit_entries) == 1
        assert audit_entries[0]["action"] == "fetch_provider_release_notes"
        assert "succeeded" in audit_entries[0]["outcome"]

    asyncio.run(_run())


def test_fetch_provider_release_notes_is_best_effort_and_returns_empty_string_on_failure(
    persistence: Persistence,
) -> None:
    async def _run() -> None:
        job_id = uuid4()
        fetcher = make_fetcher(
            {
                "https://api.github.com/repos/hashicorp/terraform-provider-azurerm/releases/tags/v4.10.0": RuntimeError(
                    "404 not found"
                )
            }
        )

        notes = await fetch_provider_release_notes(fetcher, persistence, version="4.10.0", job_id=job_id)

        assert notes == ""
        audit_entries = persistence.list_audit_entries(job_id)
        assert len(audit_entries) == 1
        assert "error" in audit_entries[0]["outcome"]

    asyncio.run(_run())
