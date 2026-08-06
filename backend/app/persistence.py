import json
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import create_engine_for, resolve_database_url, run_migrations
from app.models import Event, OnboardingRecord
from app.services.onboarding import OnboardingNotFoundError


class Persistence:
    """Job/event/audit/onboarding storage on SQLite (local) or Neon Postgres (prod).

    The backend is chosen by ``DATABASE_URL`` (see ``app.db.resolve_database_url``).
    Methods stay synchronous: ``app.event_bus`` invokes its recorder callback without
    awaiting it, so this class cannot expose an async surface without silently
    dropping event writes.

    A single file-backed SQLite connection cannot serve concurrent writers safely,
    so calls are serialized with a lock only for that backend; Postgres relies on
    SQLAlchemy's pooled connections instead, so the lock would only add contention.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        database_url: str | None = None,
    ) -> None:
        self.database_url = resolve_database_url(db_path, database_url)
        self.engine: Engine = create_engine_for(self.database_url)
        self._serialize = self.database_url.startswith("sqlite")
        self._lock = Lock()
        self._closed = False
        self.init_schema()

    def init_schema(self) -> None:
        with self._serialized():
            run_migrations(self.engine)

    def close(self) -> None:
        with self._serialized():
            self._closed = True
            self.engine.dispose()

    @contextmanager
    def _serialized(self):
        if self._serialize:
            with self._lock:
                yield
        else:
            yield

    @contextmanager
    def _connect(self):
        if self._closed:
            raise RuntimeError("Cannot operate on a closed database")
        with self._serialized(), self.engine.connect() as connection:
            yield connection

    @contextmanager
    def _begin(self):
        if self._closed:
            raise RuntimeError("Cannot operate on a closed database")
        with self._serialized(), self.engine.begin() as connection:
            yield connection

    def check_ready(self) -> None:
        """Verify that the current process can read from its configured database."""
        with self._connect() as connection:
            connection.execute(text("select 1"))

    def record_job(
        self,
        job_id: UUID,
        prompt: str,
        status: str = "accepted",
        onboarding_id: UUID | None = None,
    ) -> None:
        with self._begin() as connection:
            connection.execute(
                text(
                    """
                    insert into jobs (id, prompt, status, onboarding_id)
                    values (:id, :prompt, :status, :onboarding_id)
                    on conflict(id) do update set
                        prompt = excluded.prompt,
                        status = excluded.status,
                        onboarding_id = coalesce(excluded.onboarding_id, jobs.onboarding_id),
                        updated_at = current_timestamp
                    """
                ),
                {
                    "id": str(job_id),
                    "prompt": prompt,
                    "status": status,
                    "onboarding_id": str(onboarding_id) if onboarding_id else None,
                },
            )

    def update_job_status(self, job_id: UUID, status: str) -> None:
        with self._begin() as connection:
            connection.execute(
                text("update jobs set status = :status, updated_at = current_timestamp where id = :id"),
                {"status": status, "id": str(job_id)},
            )

    def list_recent_jobs(self, limit: int) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                text(
                    """
                    select id, prompt, status, onboarding_id, created_at, updated_at
                    from jobs
                    order by created_at desc
                    limit :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        return [dict(row) for row in rows]

    def count_jobs_by_status(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                text("select status, count(*) as n from jobs group by status")
            ).all()
        return {row[0]: int(row[1]) for row in rows}

    def record_event(self, event: Event) -> None:
        payload = event.model_dump_json()
        job_id = getattr(event, "job_id", None)
        with self._begin() as connection:
            connection.execute(
                text(
                    """
                    insert into events (id, job_id, type, payload, created_at)
                    values (:id, :job_id, :type, :payload, :created_at)
                    on conflict(id) do update set
                        job_id = excluded.job_id,
                        type = excluded.type,
                        payload = excluded.payload,
                        created_at = excluded.created_at
                    """
                ),
                {
                    "id": str(event.id),
                    "job_id": str(job_id) if job_id else None,
                    "type": str(event.type),
                    "payload": payload,
                    "created_at": event.created_at.isoformat(),
                },
            )

    def record_audit_entry(self, job_id: UUID | None, tool: str, action: str, outcome: str) -> None:
        with self._begin() as connection:
            connection.execute(
                text(
                    """
                    insert into audit_entries (job_id, tool, action, outcome)
                    values (:job_id, :tool, :action, :outcome)
                    """
                ),
                {
                    "job_id": str(job_id) if job_id else None,
                    "tool": tool,
                    "action": action,
                    "outcome": outcome,
                },
            )

    def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                text(
                    "select id, prompt, status, onboarding_id, created_at, updated_at from jobs where id = :id"
                ),
                {"id": str(job_id)},
            ).mappings().first()
        return dict(row) if row else None

    def list_job_events(self, job_id: UUID) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                text(
                    """
                    select id, job_id, type, payload, created_at
                    from events
                    where job_id = :job_id
                    order by created_at asc, seq asc
                    """
                ),
                {"job_id": str(job_id)},
            ).mappings().all()
        return [dict(row) for row in rows]

    def list_recent_events(self, limit: int) -> list[dict[str, Any]]:
        """Return a bounded replay window in stable publication order."""
        with self._connect() as connection:
            rows = connection.execute(
                text(
                    """
                    select id, job_id, type, payload, created_at
                    from events
                    order by created_at desc, seq desc
                    limit :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        return [dict(row) for row in reversed(rows)]

    def list_events_since(self, seq: int, job_id: UUID | None = None) -> list[dict[str, Any]]:
        """Return events with ``seq`` greater than the given cursor, in publication order.

        Used by the SSE endpoint to backfill everything a client missed since its
        last received ``Last-Event-ID``, optionally scoped to a single job.
        """
        query = "select seq, id, job_id, type, payload, created_at from events where seq > :seq"
        params: dict[str, Any] = {"seq": seq}
        if job_id:
            query += " and job_id = :job_id"
            params["job_id"] = str(job_id)
        query += " order by seq asc"
        with self._connect() as connection:
            rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def get_event_seq(self, event_id: UUID) -> int | None:
        """Look up the durable ``seq`` assigned to an already-recorded event."""
        with self._connect() as connection:
            row = connection.execute(
                text("select seq from events where id = :id"), {"id": str(event_id)}
            ).first()
        return row[0] if row else None

    def list_audit_entries(self, job_id: UUID | None = None) -> list[dict[str, Any]]:
        query = "select id, job_id, tool, action, outcome, created_at from audit_entries"
        params: dict[str, Any] = {}
        if job_id:
            query += " where job_id = :job_id"
            params["job_id"] = str(job_id)
        query += " order by created_at desc"
        with self._connect() as connection:
            rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def create_approval(
        self,
        approval_id: UUID,
        job_id: UUID,
        plan_hash: str,
        commit_sha: str,
        scope: str,
    ) -> None:
        with self._begin() as connection:
            connection.execute(
                text(
                    """
                    insert into approvals (id, job_id, plan_hash, commit_sha, scope, status)
                    values (:id, :job_id, :plan_hash, :commit_sha, :scope, 'pending')
                    """
                ),
                {
                    "id": str(approval_id),
                    "job_id": str(job_id),
                    "plan_hash": plan_hash,
                    "commit_sha": commit_sha,
                    "scope": scope,
                },
            )

    def decide_approval(
        self,
        approval_id: UUID,
        approver: str,
        status: str,
        expires_at,
    ) -> int:
        """Transition a pending approval to a terminal decision; returns rows affected.

        Only fires when the row is still ``pending``, so a decided approval can never
        be re-decided by a second, possibly conflicting, call.
        """
        with self._begin() as connection:
            result = connection.execute(
                text(
                    """
                    update approvals
                    set status = :status, approver = :approver,
                        decided_at = current_timestamp, expires_at = :expires_at
                    where id = :id and status = 'pending'
                    """
                ),
                {
                    "id": str(approval_id),
                    "approver": approver,
                    "status": status,
                    "expires_at": expires_at,
                },
            )
            return result.rowcount

    def consume_approval(self, approval_id: UUID) -> int:
        """Atomically mark an approved, unexpired approval consumed; returns rows affected.

        The ``where`` clause is the whole safety property: consumed_at only flips from
        NULL to a timestamp once, so a concurrent double-apply can never both succeed.
        """
        with self._begin() as connection:
            result = connection.execute(
                text(
                    """
                    update approvals
                    set consumed_at = current_timestamp
                    where id = :id
                      and status = 'approved'
                      and consumed_at is null
                      and (expires_at is null or expires_at > current_timestamp)
                    """
                ),
                {"id": str(approval_id)},
            )
            return result.rowcount

    def get_approval(self, approval_id: UUID) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                text(
                    """
                    select id, job_id, plan_hash, commit_sha, scope, approver, status,
                           created_at, decided_at, expires_at, consumed_at
                    from approvals where id = :id
                    """
                ),
                {"id": str(approval_id)},
            ).mappings().first()
        return dict(row) if row else None

    def list_approvals(self, job_id: UUID | None = None) -> list[dict[str, Any]]:
        query = (
            "select id, job_id, plan_hash, commit_sha, scope, approver, status, "
            "created_at, decided_at, expires_at, consumed_at from approvals"
        )
        params: dict[str, Any] = {}
        if job_id:
            query += " where job_id = :job_id"
            params["job_id"] = str(job_id)
        query += " order by created_at desc"
        with self._connect() as connection:
            rows = connection.execute(text(query), params).mappings().all()
        return [dict(row) for row in rows]

    def find_matching_approval(
        self, job_id: UUID, plan_hash: str, commit_sha: str
    ) -> dict[str, Any] | None:
        """Find the most recent approval exactly bound to this job, plan, and commit."""
        with self._connect() as connection:
            row = connection.execute(
                text(
                    """
                    select id, job_id, plan_hash, commit_sha, scope, approver, status,
                           created_at, decided_at, expires_at, consumed_at
                    from approvals
                    where job_id = :job_id and plan_hash = :plan_hash and commit_sha = :commit_sha
                    order by created_at desc
                    limit 1
                    """
                ),
                {"job_id": str(job_id), "plan_hash": plan_hash, "commit_sha": commit_sha},
            ).mappings().first()
        return dict(row) if row else None

    def count_pending_approvals(self) -> int:
        with self._connect() as connection:
            row = connection.execute(
                text("select count(*) from approvals where status = 'pending'")
            ).first()
        return int(row[0]) if row else 0

    def save_onboarding_record(self, record: OnboardingRecord) -> OnboardingRecord:
        with self._begin() as connection:
            connection.execute(
                text(
                    """
                    insert into onboarding_records (id, repository_path, created_at, record_json)
                    values (:id, :repository_path, :created_at, :record_json)
                    """
                ),
                {
                    "id": str(record.id),
                    "repository_path": record.repository_path,
                    "created_at": record.created_at.isoformat(),
                    "record_json": record.model_dump_json(),
                },
            )
        return record

    def get_onboarding_record(self, onboarding_id: UUID) -> OnboardingRecord:
        with self._connect() as connection:
            row = connection.execute(
                text("select record_json from onboarding_records where id = :id"),
                {"id": str(onboarding_id)},
            ).first()
        if row is None:
            raise OnboardingNotFoundError(str(onboarding_id))
        return OnboardingRecord.model_validate(json.loads(row[0]))

    def get_latest_onboarding_record(self) -> OnboardingRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                text(
                    "select record_json from onboarding_records order by created_at desc limit 1"
                ),
            ).first()
        return OnboardingRecord.model_validate(json.loads(row[0])) if row else None
