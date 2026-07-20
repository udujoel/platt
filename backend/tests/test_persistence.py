import os
from uuid import uuid4

import pytest
import sqlalchemy

from app.db import resolve_database_url
from app.models import AgentStateEvent, PlattState
from app.persistence import Persistence
from app.services.onboarding import OnboardingNotFoundError, inspect_repository


def test_resolve_database_url_prefers_database_url_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@example.com/platt")

    url = resolve_database_url(db_path=tmp_path / "unused.db")

    assert url == "postgresql+psycopg://user:pass@example.com/platt"


def test_resolve_database_url_falls_back_to_sqlite(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_path = tmp_path / "platt.db"

    url = resolve_database_url(db_path=db_path)

    assert url == f"sqlite:///{db_path}"


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-persistence-test.db")
    try:
        yield instance
    finally:
        instance.close()


def test_persistence_round_trips_jobs_events_and_audit_entries(persistence: Persistence) -> None:
    job_id = uuid4()
    persistence.record_job(job_id, prompt="Plan a rollout")
    persistence.record_event(AgentStateEvent(job_id=job_id, state=PlattState.THINKING, label="Planning"))
    persistence.record_audit_entry(job_id, tool="chat", action="create_job", outcome="accepted")

    job = persistence.get_job(job_id)
    events = persistence.list_job_events(job_id)
    audit_entries = persistence.list_audit_entries(job_id)

    assert job is not None
    assert job["prompt"] == "Plan a rollout"
    assert job["status"] == "accepted"
    assert [event["type"] for event in events] == ["agent_state"]
    assert [entry["action"] for entry in audit_entries] == ["create_job"]


def test_persistence_update_job_status(persistence: Persistence) -> None:
    job_id = uuid4()
    persistence.record_job(job_id, prompt="Bump version")

    persistence.update_job_status(job_id, "working")

    assert persistence.get_job(job_id)["status"] == "working"


def test_persistence_onboarding_record_round_trip(persistence: Persistence, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_ONBOARDING_ROOT", str(tmp_path))
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "main.tf").write_text('variable "region" { type = string }\n')
    record = inspect_repository(str(repository))

    persistence.save_onboarding_record(record)
    fetched = persistence.get_onboarding_record(record.id)

    assert fetched == record


def test_persistence_get_onboarding_record_raises_when_missing(persistence: Persistence) -> None:
    with pytest.raises(OnboardingNotFoundError):
        persistence.get_onboarding_record(uuid4())


def test_persistence_creates_approvals_table_schema_stub(persistence: Persistence) -> None:
    inspector = sqlalchemy.inspect(persistence.engine)

    columns = {column["name"] for column in inspector.get_columns("approvals")}

    assert columns == {
        "id",
        "job_id",
        "plan_hash",
        "commit_sha",
        "scope",
        "approver",
        "status",
        "created_at",
        "consumed_at",
    }


def test_persistence_init_schema_is_idempotent(tmp_path) -> None:
    db_path = tmp_path / "idempotent.db"
    first = Persistence(db_path=db_path)
    first.close()

    second = Persistence(db_path=db_path)
    try:
        second.check_ready()
    finally:
        second.close()


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not configured; skipping live Postgres checks")
def test_persistence_round_trips_against_configured_postgres() -> None:
    persistence = Persistence(database_url=os.environ["DATABASE_URL"])
    try:
        job_id = uuid4()
        persistence.record_job(job_id, prompt="Postgres smoke test")
        persistence.record_audit_entry(job_id, tool="chat", action="create_job", outcome="accepted")

        job = persistence.get_job(job_id)

        assert job is not None
        assert job["prompt"] == "Postgres smoke test"
        assert persistence.list_audit_entries(job_id)[0]["outcome"] == "accepted"
    finally:
        persistence.close()
