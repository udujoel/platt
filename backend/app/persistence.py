import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import UUID

from app.models import Event


DEFAULT_DB_PATH = "platt.db"


class Persistence:
    def __init__(self, db_path: str | Path | None = None) -> None:
        configured_path = db_path or os.getenv("PLATT_DB_PATH") or DEFAULT_DB_PATH
        self.path = str(configured_path)
        self._lock = Lock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self.init_schema()

    def init_schema(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                create table if not exists jobs (
                    id text primary key,
                    prompt text not null,
                    status text not null,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp
                );

                create table if not exists events (
                    id text primary key,
                    job_id text,
                    type text not null,
                    payload text not null,
                    created_at text not null
                );

                create table if not exists audit_entries (
                    id integer primary key autoincrement,
                    job_id text,
                    tool text not null,
                    action text not null,
                    outcome text not null,
                    created_at text not null default current_timestamp
                );
                """
            )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def record_job(self, job_id: UUID, prompt: str, status: str = "accepted") -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                insert into jobs (id, prompt, status)
                values (?, ?, ?)
                on conflict(id) do update set
                    prompt = excluded.prompt,
                    status = excluded.status,
                    updated_at = current_timestamp
                """,
                (str(job_id), prompt, status),
            )

    def update_job_status(self, job_id: UUID, status: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "update jobs set status = ?, updated_at = current_timestamp where id = ?",
                (status, str(job_id)),
            )

    def record_event(self, event: Event) -> None:
        payload = event.model_dump_json()
        job_id = getattr(event, "job_id", None)
        with self._lock, self._connection:
            self._connection.execute(
                """
                insert or replace into events (id, job_id, type, payload, created_at)
                values (?, ?, ?, ?, ?)
                """,
                (
                    str(event.id),
                    str(job_id) if job_id else None,
                    str(event.type),
                    payload,
                    event.created_at.isoformat(),
                ),
            )

    def record_audit_entry(self, job_id: UUID | None, tool: str, action: str, outcome: str) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                """
                insert into audit_entries (job_id, tool, action, outcome)
                values (?, ?, ?, ?)
                """,
                (str(job_id) if job_id else None, tool, action, outcome),
            )

    def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(
                "select id, prompt, status, created_at, updated_at from jobs where id = ?",
                (str(job_id),),
            ).fetchone()
        return dict(row) if row else None

    def list_job_events(self, job_id: UUID) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                """
                select id, job_id, type, payload, created_at
                from events
                where job_id = ?
                order by created_at asc
                """,
                (str(job_id),),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_audit_entries(self, job_id: UUID | None = None) -> list[dict[str, Any]]:
        query = "select id, job_id, tool, action, outcome, created_at from audit_entries"
        params: tuple[str, ...] = ()
        if job_id:
            query += " where job_id = ?"
            params = (str(job_id),)
        query += " order by created_at desc"
        with self._lock:
            rows = self._connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

