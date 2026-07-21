import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import respx

from app.clients.azdo import AzdoClient, AzdoConfig
from app.models import Event
from app.persistence import Persistence
from app.services.onboarding import inspect_repository
from app.tools.context import ToolContext, ToolExecutionError
from app.tools.executor import (
    DEFAULT_TOOL_CALL_CAP,
    ToolCapExceededError,
    ToolExecutor,
    ToolNotAllowedError,
    ToolNotFoundError,
    ToolValidationError,
)
from app.tools.registry import (
    AZDO_READ_TOOLS,
    JOB_ALLOWLISTS,
    REPO_READ_TOOLS,
    ToolDefinition,
    ToolRegistry,
    build_default_registry,
)
from app.tools.schema import SchemaValidationError, validate_arguments


class CapturingBus:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-tools-test.db")
    try:
        yield instance
    finally:
        instance.close()


ECHO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["value"],
    "properties": {"value": {"type": "string", "minLength": 1, "maxLength": 32}},
}


async def _echo(arguments: dict, ctx: ToolContext) -> dict:
    del ctx
    return {"echoed": arguments["value"]}


def _echo_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(ToolDefinition("echo", "Echo back a string.", ECHO_SCHEMA, _echo))
    return registry


# -- schema validation --------------------------------------------------------


def test_validate_arguments_accepts_a_matching_payload() -> None:
    validate_arguments({"value": "hi"}, ECHO_SCHEMA)


def test_validate_arguments_rejects_missing_required_field() -> None:
    with pytest.raises(SchemaValidationError, match="missing required"):
        validate_arguments({}, ECHO_SCHEMA)


def test_validate_arguments_rejects_unexpected_field() -> None:
    with pytest.raises(SchemaValidationError, match="unexpected argument"):
        validate_arguments({"value": "hi", "extra": 1}, ECHO_SCHEMA)


def test_validate_arguments_rejects_wrong_type() -> None:
    with pytest.raises(SchemaValidationError, match="must be of type"):
        validate_arguments({"value": 5}, ECHO_SCHEMA)


def test_validate_arguments_enforces_max_length() -> None:
    with pytest.raises(SchemaValidationError, match="at most"):
        validate_arguments({"value": "x" * 40}, ECHO_SCHEMA)


def test_validate_arguments_enforces_integer_bounds() -> None:
    schema = {
        "type": "object",
        "required": ["count"],
        "properties": {"count": {"type": "integer", "minimum": 1, "maximum": 5}},
    }
    validate_arguments({"count": 3}, schema)
    with pytest.raises(SchemaValidationError, match=">="):
        validate_arguments({"count": 0}, schema)
    with pytest.raises(SchemaValidationError, match="<="):
        validate_arguments({"count": 6}, schema)
    with pytest.raises(SchemaValidationError, match="integer"):
        validate_arguments({"count": True}, schema)


# -- registry ------------------------------------------------------------------


def test_registry_rejects_duplicate_registration() -> None:
    registry = _echo_registry()
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ToolDefinition("echo", "dup", ECHO_SCHEMA, _echo))


def test_registry_schemas_for_renders_openai_function_shape() -> None:
    registry = _echo_registry()
    schemas = registry.schemas_for(["echo"])
    assert schemas == [
        {
            "type": "function",
            "function": {"name": "echo", "description": "Echo back a string.", "parameters": ECHO_SCHEMA},
        }
    ]


def test_registry_schemas_for_unknown_tool_raises() -> None:
    registry = _echo_registry()
    with pytest.raises(KeyError):
        registry.schemas_for(["missing"])


def test_default_registry_registers_repo_and_azdo_read_tools() -> None:
    registry = build_default_registry()
    assert REPO_READ_TOOLS <= set(registry.names())
    assert AZDO_READ_TOOLS <= set(registry.names())


def test_job_allowlists_are_read_only_and_scoped_per_job_type() -> None:
    assert JOB_ALLOWLISTS["onboarding_chat"] == REPO_READ_TOOLS
    assert JOB_ALLOWLISTS["chat"] == AZDO_READ_TOOLS


# -- executor: allowlist, validation, cap, audit -------------------------------


def test_executor_runs_an_allowed_valid_call_and_writes_a_success_audit_entry(persistence: Persistence) -> None:
    async def _run() -> None:
        job_id = uuid4()
        bus = CapturingBus()
        executor = ToolExecutor(_echo_registry(), persistence, {"echo"}, job_id=job_id, event_bus=bus)

        result = await executor.execute("echo", {"value": "hi"})

        assert result == {"echoed": "hi"}
        assert executor.call_count == 1

        entries = persistence.list_audit_entries(job_id)
        assert len(entries) == 1
        assert entries[0]["tool"] == "agent"
        assert entries[0]["action"] == "echo"
        assert entries[0]["outcome"].startswith("succeeded")
        assert "value=hi" in entries[0]["outcome"]
        assert any(event.tool == "agent" and event.outcome == "succeeded" for event in bus.events)

    asyncio.run(_run())


def test_executor_rejects_a_tool_outside_the_allowlist(persistence: Persistence) -> None:
    async def _run() -> None:
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, set(), job_id=job_id)

        with pytest.raises(ToolNotAllowedError):
            await executor.execute("echo", {"value": "hi"})

        entries = persistence.list_audit_entries(job_id)
        assert any("rejected: not in this job's tool allowlist" in entry["outcome"] for entry in entries)

    asyncio.run(_run())


def test_executor_rejects_an_unregistered_tool_even_if_named_in_the_allowlist(persistence: Persistence) -> None:
    async def _run() -> None:
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, {"ghost"}, job_id=job_id)

        with pytest.raises(ToolNotFoundError):
            await executor.execute("ghost", {})

    asyncio.run(_run())


def test_executor_rejects_invalid_arguments_without_calling_the_handler(persistence: Persistence) -> None:
    async def _run() -> None:
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, {"echo"}, job_id=job_id)

        with pytest.raises(ToolValidationError):
            await executor.execute("echo", {})

        assert executor.call_count == 0
        entries = persistence.list_audit_entries(job_id)
        assert any("rejected:" in entry["outcome"] for entry in entries)

    asyncio.run(_run())


def test_executor_redacts_secret_looking_arguments_in_the_audit_log(persistence: Persistence) -> None:
    async def _run() -> None:
        job_id = uuid4()
        registry = ToolRegistry()

        async def handler(arguments: dict, ctx: ToolContext) -> dict:
            del ctx
            return {"ok": True}

        registry.register(
            ToolDefinition(
                "secret_tool",
                "d",
                {
                    "type": "object",
                    "required": ["token"],
                    "properties": {"token": {"type": "string", "maxLength": 64}},
                },
                handler,
            )
        )
        executor = ToolExecutor(registry, persistence, {"secret_tool"}, job_id=job_id)

        await executor.execute("secret_tool", {"token": "super-secret-value"})

        entries = persistence.list_audit_entries(job_id)
        assert "super-secret-value" not in entries[0]["outcome"]
        assert "token=<redacted>" in entries[0]["outcome"]

    asyncio.run(_run())


def test_executor_enforces_the_default_cap_and_reports_via_a_typed_error(persistence: Persistence) -> None:
    async def _run() -> None:
        job_id = uuid4()
        executor = ToolExecutor(_echo_registry(), persistence, {"echo"}, job_id=job_id, cap=2)

        await executor.execute("echo", {"value": "a"})
        await executor.execute("echo", {"value": "b"})

        with pytest.raises(ToolCapExceededError):
            await executor.execute("echo", {"value": "c"})

        assert executor.call_count == 2
        entries = persistence.list_audit_entries(job_id)
        assert any("rejected: tool call cap" in entry["outcome"] for entry in entries)

    asyncio.run(_run())


def test_executor_default_cap_matches_prd_budget() -> None:
    assert DEFAULT_TOOL_CALL_CAP == 40


def test_executor_wraps_handler_exceptions_as_tool_execution_errors(persistence: Persistence) -> None:
    async def _run() -> None:
        registry = ToolRegistry()

        async def boom(arguments: dict, ctx: ToolContext) -> dict:
            del arguments, ctx
            raise RuntimeError("handler exploded")

        registry.register(ToolDefinition("boom", "d", {"type": "object", "properties": {}}, boom))
        executor = ToolExecutor(registry, persistence, {"boom"})

        with pytest.raises(ToolExecutionError, match="handler exploded"):
            await executor.execute("boom", {})

    asyncio.run(_run())


# -- repo tools -----------------------------------------------------------------


@pytest.fixture(autouse=True)
def configure_onboarding_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_ONBOARDING_ROOT", str(tmp_path))


def _seed_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "README.md").write_text("hello from platt")
    (repository / "main.tf").write_text('module "network" {\n  source = "./modules/network"\n}\n')
    return repository


def test_repo_tools_are_bounded_to_the_bound_onboarding_record(tmp_path: Path, persistence: Persistence) -> None:
    async def _run() -> None:
        record = inspect_repository(str(_seed_repository(tmp_path)))
        registry = build_default_registry()
        executor = ToolExecutor(
            registry,
            persistence,
            REPO_READ_TOOLS,
            resources={"onboarding_record": record},
        )

        read = await executor.execute("read_file", {"path": "README.md"})
        assert read["content"] == "hello from platt"

        listed = await executor.execute("glob", {"pattern": "*.tf"})
        assert listed["paths"] == ["main.tf"]

        found = await executor.execute("grep", {"query": "module"})
        assert found["matches"][0]["path"] == "main.tf"

    asyncio.run(_run())


def test_repo_tools_refuse_paths_outside_the_inventory(tmp_path: Path, persistence: Persistence) -> None:
    async def _run() -> None:
        record = inspect_repository(str(_seed_repository(tmp_path)))
        registry = build_default_registry()
        executor = ToolExecutor(registry, persistence, REPO_READ_TOOLS, resources={"onboarding_record": record})

        with pytest.raises(ToolExecutionError):
            await executor.execute("read_file", {"path": "../outside.txt"})

    asyncio.run(_run())


def test_repo_tools_without_a_bound_onboarding_record_raise(persistence: Persistence) -> None:
    async def _run() -> None:
        registry = build_default_registry()
        executor = ToolExecutor(registry, persistence, REPO_READ_TOOLS)

        with pytest.raises(ToolExecutionError, match="unavailable resource: onboarding_record"):
            await executor.execute("read_file", {"path": "README.md"})

    asyncio.run(_run())


# -- registered azdo read tools --------------------------------------------------


def make_azdo_client() -> AzdoClient:
    config = AzdoConfig(org_url="https://dev.azure.com/myorg", project="MyProject", pat="super-secret-pat")
    return AzdoClient(config)


def test_registered_get_pr_tool_calls_azdo_and_double_audits_agent_and_azdo(persistence: Persistence) -> None:
    async def _run() -> None:
        job_id = uuid4()
        client = make_azdo_client()
        try:
            registry = build_default_registry()
            executor = ToolExecutor(
                registry,
                persistence,
                AZDO_READ_TOOLS,
                job_id=job_id,
                resources={"azdo_client": client},
            )
            with respx.mock(base_url="https://dev.azure.com") as mock:
                mock.get("/myorg/MyProject/_apis/git/repositories/repo-1/pullrequests/42").mock(
                    return_value=httpx.Response(200, json={"pullRequestId": 42, "status": "active"})
                )
                result = await executor.execute("get_pr", {"repository_id": "repo-1", "pull_request_id": 42})
                assert result["status"] == "active"
        finally:
            await client.aclose()

        entries = persistence.list_audit_entries(job_id)
        tools = {entry["tool"] for entry in entries}
        assert "agent" in tools
        assert "azdo" in tools
        assert any(entry["tool"] == "agent" and entry["action"] == "get_pr" for entry in entries)
        assert any(entry["tool"] == "azdo" and entry["action"] == "get_pr" for entry in entries)

    asyncio.run(_run())


def test_azdo_tool_call_missing_client_resource_raises_tool_execution_error(persistence: Persistence) -> None:
    async def _run() -> None:
        registry = build_default_registry()
        executor = ToolExecutor(registry, persistence, AZDO_READ_TOOLS)

        with pytest.raises(ToolExecutionError, match="azdo_client"):
            await executor.execute("get_pr", {"repository_id": "repo-1", "pull_request_id": 1})

    asyncio.run(_run())
