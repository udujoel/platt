"""Audited Azure DevOps tool layer.

Every tool call here is a thin, audited wrapper around :class:`app.clients.azdo.AzdoClient`.
Each call writes exactly one audit entry (a redacted input summary and the outcome)
before returning or raising, matching the "full audit log" guardrail in the PRD.
Credentials never appear in a tool's arguments: callers hold an already-constructed
:class:`AzdoClient` (built from the environment) and pass only business identifiers
(repository ids, work item ids, branch names, ...) to these functions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.clients.azdo import AzdoClient, AzdoError
from app.event_bus import EventBus
from app.models import AuditEntryEvent
from app.persistence import Persistence

TOOL_NAME = "azdo"
_REDACTED_KEYS = {"pat", "token", "password", "authorization", "secret"}
_MAX_VALUE_CHARS = 200


def _redact(fields: dict[str, Any]) -> str:
    """Render tool arguments as a bounded, secret-free summary for the audit log."""
    parts = []
    for key, value in fields.items():
        if key.lower() in _REDACTED_KEYS:
            parts.append(f"{key}=<redacted>")
            continue
        text = str(value)
        if len(text) > _MAX_VALUE_CHARS:
            text = text[:_MAX_VALUE_CHARS] + "...(truncated)"
        parts.append(f"{key}={text}")
    return ", ".join(parts)


async def _audit(
    persistence: Persistence,
    event_bus: EventBus | None,
    job_id: UUID | None,
    action: str,
    *,
    request_summary: str,
    ok: bool,
    result_summary: str,
) -> None:
    status = "succeeded" if ok else "error"
    outcome = f"{status} | request: {request_summary} | result: {result_summary}"
    persistence.record_audit_entry(job_id, tool=TOOL_NAME, action=action, outcome=outcome)
    if event_bus is not None and job_id is not None:
        await event_bus.publish(
            AuditEntryEvent(job_id=job_id, tool=TOOL_NAME, action=action, outcome=status, summary=outcome[:512])
        )


async def _call(
    client: AzdoClient,
    persistence: Persistence,
    *,
    event_bus: EventBus | None,
    job_id: UUID | None,
    action: str,
    request_fields: dict[str, Any],
    result_summary: Any,
    fn,
) -> Any:
    request_summary = _redact(request_fields)
    try:
        result = await fn()
    except AzdoError as exc:
        # AzdoClient wraps every failure mode (non-2xx responses AND transport
        # failures like timeouts/connection errors) in AzdoError, so this one
        # except clause is enough to guarantee exactly one audit entry per call.
        await _audit(
            persistence,
            event_bus,
            job_id,
            action,
            request_summary=request_summary,
            ok=False,
            result_summary=str(exc)[:_MAX_VALUE_CHARS],
        )
        raise
    await _audit(
        persistence,
        event_bus,
        job_id,
        action,
        request_summary=request_summary,
        ok=True,
        result_summary=str(result_summary(result))[:_MAX_VALUE_CHARS],
    )
    return result


# -- Process template ---------------------------------------------------------


async def get_process_template(
    client: AzdoClient,
    persistence: Persistence,
    *,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    """Detect the project's Boards process template (Agile, Scrum, CMMI, Basic, ...)."""

    async def _run() -> dict[str, Any]:
        project = await client.get_process_template()
        template_name = (
            project.get("capabilities", {}).get("processTemplate", {}).get("templateName", "Unknown")
        )
        return {"project": project.get("name"), "process_template": template_name}

    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="get_process_template",
        request_fields={},
        result_summary=lambda r: f"template={r['process_template']}",
        fn=_run,
    )


# -- Branches / pushes -----------------------------------------------------------


async def get_branch(
    client: AzdoClient,
    persistence: Persistence,
    *,
    repository_id: str,
    branch_name: str,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any] | None:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="get_branch",
        request_fields={"repository_id": repository_id, "branch_name": branch_name},
        result_summary=lambda r: f"found={r is not None}",
        fn=lambda: client.get_branch(repository_id, branch_name),
    )


async def push_file(
    client: AzdoClient,
    persistence: Persistence,
    *,
    repository_id: str,
    branch_name: str,
    base_object_id: str,
    file_path: str,
    content: str,
    change_type: str,
    comment: str,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="push_file",
        request_fields={
            "repository_id": repository_id,
            "branch_name": branch_name,
            "file_path": file_path,
            "change_type": change_type,
        },
        result_summary=lambda r: f"push_id={r.get('pushId')}",
        fn=lambda: client.push_file(
            repository_id,
            branch_name=branch_name,
            base_object_id=base_object_id,
            file_path=file_path,
            content=content,
            change_type=change_type,
            comment=comment,
        ),
    )


# -- Pull requests --------------------------------------------------------------


async def create_pr(
    client: AzdoClient,
    persistence: Persistence,
    *,
    repository_id: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str = "",
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="create_pr",
        request_fields={
            "repository_id": repository_id,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
        },
        result_summary=lambda r: f"pull_request_id={r.get('pullRequestId')}",
        fn=lambda: client.create_pull_request(
            repository_id,
            source_branch=source_branch,
            target_branch=target_branch,
            title=title,
            description=description,
        ),
    )


async def get_pr(
    client: AzdoClient,
    persistence: Persistence,
    *,
    repository_id: str,
    pull_request_id: int,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="get_pr",
        request_fields={"repository_id": repository_id, "pull_request_id": pull_request_id},
        result_summary=lambda r: f"status={r.get('status')}",
        fn=lambda: client.get_pull_request(repository_id, pull_request_id),
    )


async def list_prs(
    client: AzdoClient,
    persistence: Persistence,
    *,
    repository_id: str,
    status: str = "active",
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="list_prs",
        request_fields={"repository_id": repository_id, "status": status},
        result_summary=lambda r: f"count={len(r.get('value', []))}",
        fn=lambda: client.list_pull_requests(repository_id, status=status),
    )


async def comment_pr(
    client: AzdoClient,
    persistence: Persistence,
    *,
    repository_id: str,
    pull_request_id: int,
    comment: str,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="comment_pr",
        request_fields={
            "repository_id": repository_id,
            "pull_request_id": pull_request_id,
            "comment": comment,
        },
        result_summary=lambda r: f"thread_id={r.get('id')}",
        fn=lambda: client.comment_pull_request(repository_id, pull_request_id, comment=comment),
    )


# -- Pipelines --------------------------------------------------------------------


async def run_pipeline(
    client: AzdoClient,
    persistence: Persistence,
    *,
    pipeline_id: int,
    branch: str | None = None,
    variables: dict[str, Any] | None = None,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="run_pipeline",
        request_fields={"pipeline_id": pipeline_id, "branch": branch},
        result_summary=lambda r: f"run_id={r.get('id')} state={r.get('state')}",
        fn=lambda: client.run_pipeline(pipeline_id, branch=branch, variables=variables),
    )


async def get_pipeline_run(
    client: AzdoClient,
    persistence: Persistence,
    *,
    pipeline_id: int,
    run_id: int,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="get_pipeline_run",
        request_fields={"pipeline_id": pipeline_id, "run_id": run_id},
        result_summary=lambda r: f"state={r.get('state')} result={r.get('result')}",
        fn=lambda: client.get_pipeline_run(pipeline_id, run_id),
    )


async def list_pipeline_runs(
    client: AzdoClient,
    persistence: Persistence,
    *,
    pipeline_id: int,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="list_pipeline_runs",
        request_fields={"pipeline_id": pipeline_id},
        result_summary=lambda r: f"count={len(r.get('value', []))}",
        fn=lambda: client.list_pipeline_runs(pipeline_id),
    )


async def get_pipeline_logs(
    client: AzdoClient,
    persistence: Persistence,
    *,
    pipeline_id: int,
    run_id: int,
    log_id: int | None = None,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any] | str:
    if log_id is None:
        return await _call(
            client,
            persistence,
            event_bus=event_bus,
            job_id=job_id,
            action="get_pipeline_logs",
            request_fields={"pipeline_id": pipeline_id, "run_id": run_id},
            result_summary=lambda r: f"log_count={len(r.get('logs', []))}",
            fn=lambda: client.list_pipeline_logs(pipeline_id, run_id),
        )
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="get_pipeline_log_content",
        request_fields={"pipeline_id": pipeline_id, "run_id": run_id, "log_id": log_id},
        result_summary=lambda r: f"chars={len(r)}",
        fn=lambda: client.get_pipeline_log_content(pipeline_id, run_id, log_id),
    )


# -- Work items -------------------------------------------------------------------


async def create_work_item(
    client: AzdoClient,
    persistence: Persistence,
    *,
    work_item_type: str,
    title: str,
    fields: dict[str, Any] | None = None,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="create_work_item",
        request_fields={"work_item_type": work_item_type, "title": title},
        result_summary=lambda r: f"work_item_id={r.get('id')}",
        fn=lambda: client.create_work_item(work_item_type, title=title, fields=fields),
    )


async def update_work_item_state(
    client: AzdoClient,
    persistence: Persistence,
    *,
    work_item_id: int,
    state: str,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="update_work_item_state",
        request_fields={"work_item_id": work_item_id, "state": state},
        result_summary=lambda r: f"work_item_id={r.get('id')} state={r.get('fields', {}).get('System.State')}",
        fn=lambda: client.update_work_item_state(work_item_id, state=state),
    )


async def list_work_items(
    client: AzdoClient,
    persistence: Persistence,
    *,
    wiql_query: str,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="list_work_items",
        request_fields={"wiql_query": wiql_query},
        result_summary=lambda r: f"count={len(r.get('workItems', []))}",
        fn=lambda: client.list_work_items(wiql_query),
    )


# -- Wiki -----------------------------------------------------------------------


async def get_wiki_page(
    client: AzdoClient,
    persistence: Persistence,
    *,
    wiki_identifier: str,
    path: str,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="get_wiki_page",
        request_fields={"wiki_identifier": wiki_identifier, "path": path},
        result_summary=lambda r: f"content_chars={len(r.get('content', '') or '')}",
        fn=lambda: client.get_wiki_page(wiki_identifier, path),
    )


async def update_wiki_page(
    client: AzdoClient,
    persistence: Persistence,
    *,
    wiki_identifier: str,
    path: str,
    content: str,
    version: str | None = None,
    job_id: UUID | None = None,
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    return await _call(
        client,
        persistence,
        event_bus=event_bus,
        job_id=job_id,
        action="update_wiki_page",
        request_fields={"wiki_identifier": wiki_identifier, "path": path, "content_chars": len(content)},
        result_summary=lambda r: f"page_id={r.get('id')}",
        fn=lambda: client.update_wiki_page(wiki_identifier, path, content=content, version=version),
    )
