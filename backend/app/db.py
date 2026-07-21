"""Backend-agnostic schema and engine selection for Neon Postgres or local SQLite.

Both backends are addressed through the same SQLAlchemy Core table definitions and
raw ``ON CONFLICT`` SQL, which is compatible across SQLite (3.24+) and PostgreSQL
(9.5+). The persistence layer stays fully synchronous: ``app.event_bus`` invokes its
recorder callback unawaited, so an async driver would silently drop writes there.
"""

import os
from pathlib import Path
from typing import Final

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.engine import Engine

DATABASE_URL_ENV: Final[str] = "DATABASE_URL"
DEFAULT_SQLITE_PATH: Final[str] = "platt.db"

metadata = MetaData()

jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("prompt", Text, nullable=False),
    Column("status", String, nullable=False),
    Column("onboarding_id", String, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

events = Table(
    "events",
    metadata,
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("id", String, nullable=False, unique=True),
    Column("job_id", String, nullable=True),
    Column("type", String, nullable=False),
    Column("payload", Text, nullable=False),
    Column("created_at", String, nullable=False),
    Index("idx_events_job_id", "job_id"),
)

audit_entries = Table(
    "audit_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("job_id", String, nullable=True),
    Column("tool", String, nullable=False),
    Column("action", String, nullable=False),
    Column("outcome", String, nullable=False),
    Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Index("idx_audit_entries_job_id", "job_id"),
)

onboarding_records = Table(
    "onboarding_records",
    metadata,
    Column("id", String, primary_key=True),
    Column("repository_path", Text, nullable=False),
    Column("created_at", String, nullable=False),
    Column("record_json", Text, nullable=False),
)

# Immutable once decided: only status/decided_at/expires_at/consumed_at ever change,
# and only through the one-time transitions in app.approvals (pending -> decided,
# then approved -> consumed). job_id/plan_hash/commit_sha/scope are set at creation
# and never updated, so an approval can only ever authorize the exact apply it named.
approvals = Table(
    "approvals",
    metadata,
    Column("id", String, primary_key=True),
    Column("job_id", String, nullable=True),
    Column("plan_hash", String, nullable=True),
    Column("commit_sha", String, nullable=True),
    Column("scope", String, nullable=True),
    Column("approver", String, nullable=True),
    Column("status", String, nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("decided_at", DateTime, nullable=True),
    Column("expires_at", DateTime, nullable=True),
    Column("consumed_at", DateTime, nullable=True),
)


def _normalize_database_url(url: str) -> str:
    """Point plain ``postgres(ql)://`` URLs (Neon's format) at the psycopg3 driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def resolve_database_url(db_path: str | Path | None = None, database_url: str | None = None) -> str:
    """Prefer a configured Postgres URL; otherwise fall back to a local SQLite file."""
    configured_url = database_url or os.getenv(DATABASE_URL_ENV)
    if configured_url:
        return _normalize_database_url(configured_url)
    configured_path = db_path or os.getenv("PLATT_DB_PATH") or DEFAULT_SQLITE_PATH
    return f"sqlite:///{configured_path}"


def create_engine_for(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, future=True, connect_args=connect_args)


def _backfill_events_seq(connection) -> None:
    """Add ``events.seq`` to a pre-this-PR table and populate it in insertion order.

    SQLite can't retrofit a new autoincrementing primary key onto an existing
    table with ``ALTER TABLE``, so the table is rebuilt: renamed aside, recreated
    from the current (post-migration) schema, and repopulated ordered by the
    original rowid, which preserves the same insertion order ``seq`` now encodes.
    """
    if connection.engine.dialect.name == "sqlite":
        connection.execute(text("ALTER TABLE events RENAME TO events_legacy"))
        # SQLite keeps index names attached to the table through a RENAME, so the
        # legacy idx_events_job_id index must be dropped before events.create()
        # recreates it on the new table, or the create fails with "already exists".
        connection.execute(text("DROP INDEX IF EXISTS idx_events_job_id"))
        events.create(connection)
        connection.execute(
            text(
                """
                INSERT INTO events (id, job_id, type, payload, created_at)
                SELECT id, job_id, type, payload, created_at FROM events_legacy ORDER BY rowid
                """
            )
        )
        connection.execute(text("DROP TABLE events_legacy"))
    else:
        # No pre-this-PR Postgres deployment can exist yet, but add the column
        # defensively so a hand-migrated legacy table doesn't hard-fail startup.
        connection.execute(text("ALTER TABLE events ADD COLUMN seq BIGSERIAL"))


def run_migrations(engine: Engine) -> None:
    """Create any missing tables/indexes and upgrade a pre-existing legacy SQLite file."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        events_columns = (
            {column["name"] for column in inspector.get_columns("events")}
            if "events" in existing_tables
            else set()
        )
        metadata.create_all(connection, checkfirst=True)
        if "jobs" in existing_tables:
            job_columns = {column["name"] for column in inspector.get_columns("jobs")}
            if "onboarding_id" not in job_columns:
                connection.execute(text("ALTER TABLE jobs ADD COLUMN onboarding_id TEXT"))
        if "events" in existing_tables and "seq" not in events_columns:
            _backfill_events_seq(connection)
        if "approvals" in existing_tables:
            approvals_columns = {column["name"] for column in inspector.get_columns("approvals")}
            if "decided_at" not in approvals_columns:
                connection.execute(text("ALTER TABLE approvals ADD COLUMN decided_at TIMESTAMP"))
            if "expires_at" not in approvals_columns:
                connection.execute(text("ALTER TABLE approvals ADD COLUMN expires_at TIMESTAMP"))
