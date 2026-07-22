import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.llm import LLMTurn
from app.models import (
    AgentStateEvent,
    Event,
    JobCreatedEvent,
    PlanReadyEvent,
    PlattState,
    ReleaseDetectedEvent,
    SignificanceAssessedEvent,
)
from app.persistence import Persistence
from app.provision import TerraformPlanResult
from app.tools.context import ToolContext
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolDefinition, ToolRegistry
from app.version_bump import (
    VersionBumpConfig,
    VersionBumpError,
    _bump_constraint,
    _pessimistic_constraint_allows,
    _read_versions_file,
    run_version_bump_check,
)

SEED_INFRA_PATH = Path(__file__).resolve().parents[2] / "seed-infra"


class CapturingBus:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)


class ScriptedTurnLLM:
    """Plays back one pre-scripted JSON-content turn for the significance assessment call."""

    def __init__(self, reply: dict[str, Any]) -> None:
        self._reply = reply
        self.calls = 0

    async def complete_turn(self, messages: list[dict], tools: list[dict]) -> LLMTurn:
        assert tools == []
        self.calls += 1
        return LLMTurn(content=json.dumps(self._reply), tool_calls=())


ASSESSMENT_REPLY = {
    "recommendation": "merge with caution",
    "reasoning": "Major version bump; review breaking changes before merging.",
}


def _next_id_factory():
    counter = {"n": 100}

    def _next() -> int:
        counter["n"] += 1
        return counter["n"]

    return _next


def make_fake_version_bump_registry(*, target_branch: str = "main") -> ToolRegistry:
    registry = ToolRegistry()
    next_id = _next_id_factory()
    state: dict[str, Any] = {
        "branches": {target_branch: {"objectId": "base-commit-0"}},
        "push_calls": [],
        "pr_calls": [],
    }

    async def get_branch(arguments: dict, ctx: ToolContext) -> dict | None:
        del ctx
        return state["branches"].get(arguments["branch_name"])

    async def push_file(arguments: dict, ctx: ToolContext) -> dict:
        del ctx
        state["push_calls"].append(dict(arguments))
        push_id = len(state["push_calls"])
        state["branches"][arguments["branch_name"]] = {"objectId": f"commit-{push_id}"}
        return {"pushId": push_id}

    async def create_pr(arguments: dict, ctx: ToolContext) -> dict:
        del ctx
        state["pr_calls"].append(dict(arguments))
        return {"pullRequestId": next_id()}

    async def get_pr(arguments: dict, ctx: ToolContext) -> dict:
        del ctx, arguments
        return {"status": "active"}

    schema = {"type": "object"}
    for name, handler in [
        ("get_branch", get_branch),
        ("push_file", push_file),
        ("create_pr", create_pr),
        ("get_pr", get_pr),
    ]:
        registry.register(ToolDefinition(name, name, schema, handler))
    registry.test_state = state
    return registry


def make_executor(persistence: Persistence, bus: CapturingBus, job_id: UUID, **kwargs) -> ToolExecutor:
    registry = kwargs.pop("registry", None) or make_fake_version_bump_registry(**kwargs)
    return ToolExecutor(registry, persistence, set(registry.names()), job_id=job_id, event_bus=bus)


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-version-bump-test.db")
    try:
        yield instance
    finally:
        instance.close()


def make_config() -> VersionBumpConfig:
    return VersionBumpConfig(repository_id="repo-1", seed_infra_path=SEED_INFRA_PATH)


def make_fetcher(latest_version: str, *, release_notes: str = "Some release notes."):
    async def _fetch(url: str) -> dict[str, Any]:
        if url.endswith("/versions"):
            return {"versions": [{"version": latest_version}]}
        return {"body": release_notes}

    return _fetch


def fake_plan(*, resource_changes: int = 0):
    def _runner(file_path: str, content: str, config) -> TerraformPlanResult:
        del config
        changes = [{"address": f"azurerm_provider.{i}", "change": {"actions": ["update"]}} for i in range(resource_changes)]
        plan_json = {"resource_changes": changes}
        return TerraformPlanResult(
            plan_json=plan_json, plan_hash="hash-1", commit_sha="sha-1", simulated=True, raw_output=f"plan for {file_path}"
        )

    return _runner


# -- constraint math -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "constraint", "allowed"),
    [
        ("4.0.0", "~> 4.0", True),
        ("4.9.9", "~> 4.0", True),
        ("5.0.0", "~> 4.0", False),
        ("3.9.9", "~> 4.0", False),
        ("4.0.5", "~> 4.0.0", True),
        ("4.1.0", "~> 4.0.0", False),
    ],
)
def test_pessimistic_constraint_allows(version: str, constraint: str, allowed: bool) -> None:
    assert _pessimistic_constraint_allows(version, constraint) is allowed


def test_bump_constraint_preserves_two_component_precision() -> None:
    assert _bump_constraint("5.3.1", "~> 4.0") == "~> 5.0"


def test_bump_constraint_preserves_three_component_precision() -> None:
    assert _bump_constraint("4.2.7", "~> 4.1.0") == "~> 4.2.0"


def test_read_versions_file_extracts_the_azurerm_constraint() -> None:
    _, constraint = _read_versions_file(SEED_INFRA_PATH)
    assert constraint == "~> 4.0"


def test_read_versions_file_raises_when_constraint_missing(tmp_path: Path) -> None:
    (tmp_path / "versions.tf").write_text("terraform {}\n", encoding="utf-8")
    with pytest.raises(VersionBumpError, match="no azurerm provider version constraint"):
        _read_versions_file(tmp_path)


# -- job: no bump needed ----------------------------------------------------------------


def test_no_bump_needed_when_latest_satisfies_current_constraint(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        llm = ScriptedTurnLLM(ASSESSMENT_REPLY)

        result = await run_version_bump_check(
            job_id=job_id,
            bus=bus,
            persistence=persistence,
            tool_executor=executor,
            llm=llm,
            config=make_config(),
            http_fetcher=make_fetcher("4.5.0"),
            terraform_runner=fake_plan(),
        )

        assert result.bumped is False
        assert result.current_constraint == "~> 4.0"
        assert result.latest_version == "4.5.0"
        assert result.new_constraint is None
        assert result.pull_request_id is None
        assert llm.calls == 0

        state = executor.registry.test_state
        assert state["push_calls"] == []
        assert state["pr_calls"] == []

        release_event = next(e for e in bus.events if isinstance(e, ReleaseDetectedEvent))
        assert release_event.bump_needed is False
        assert release_event.dependency == "hashicorp/azurerm"
        assert not any(isinstance(e, SignificanceAssessedEvent) for e in bus.events)
        assert not any(isinstance(e, PlanReadyEvent) for e in bus.events)

    asyncio.run(_run())


# -- job: happy path bump + PR -----------------------------------------------------------


def test_bump_flow_opens_a_pr_with_recommendation_and_plan_summary(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        llm = ScriptedTurnLLM(ASSESSMENT_REPLY)

        result = await run_version_bump_check(
            job_id=job_id,
            bus=bus,
            persistence=persistence,
            tool_executor=executor,
            llm=llm,
            config=make_config(),
            http_fetcher=make_fetcher("5.2.0", release_notes="Breaking: renamed resource."),
            terraform_runner=fake_plan(resource_changes=2),
        )

        assert result.bumped is True
        assert result.current_constraint == "~> 4.0"
        assert result.latest_version == "5.2.0"
        assert result.new_constraint == "~> 5.0"
        assert result.pull_request_id is not None
        assert result.assessment is not None
        assert result.assessment.recommendation == "merge with caution"
        assert llm.calls == 1

        state = executor.registry.test_state
        assert len(state["push_calls"]) == 1
        push_call = state["push_calls"][0]
        assert push_call["file_path"] == "versions.tf"
        assert push_call["change_type"] == "edit"
        assert '"~> 5.0"' in push_call["content"]
        assert 'source  = "hashicorp/azurerm"' in push_call["content"] or "hashicorp/azurerm" in push_call["content"]

        assert len(state["pr_calls"]) == 1
        pr_call = state["pr_calls"][0]
        assert pr_call["source_branch"].endswith(f"platt/version-bump-{job_id}")
        assert "~> 4.0" in pr_call["description"]
        assert "~> 5.0" in pr_call["description"]
        assert "merge with caution" in pr_call["description"]
        assert "renamed resource" not in pr_call["description"]  # notes feed the LLM, not the PR body verbatim
        assert "plan-only" in pr_call["description"].lower()

        event_types = [event.type for event in bus.events if event.type != "audit_entry"]
        assert event_types == [
            "job_created",
            "agent_state",  # working: checking registry
            "release_detected",
            "agent_state",  # thinking: assessing significance
            "significance_assessed",
            "agent_state",  # working: pushing version bump
            "agent_state",  # working: running local terraform plan
            "plan_ready",
            "agent_state",  # working: opening PR
            "agent_state",  # celebrating
        ]
        assert bus.events[-1].state == PlattState.CELEBRATING

        plan_ready = next(e for e in bus.events if isinstance(e, PlanReadyEvent))
        assert "2 resource change(s)" in plan_ready.summary

    asyncio.run(_run())


def test_significance_assessment_rejects_an_invalid_recommendation(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        llm = ScriptedTurnLLM({"recommendation": "do it now", "reasoning": "because"})

        with pytest.raises(VersionBumpError, match="unexpected recommendation value"):
            await run_version_bump_check(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                tool_executor=executor,
                llm=llm,
                config=make_config(),
                http_fetcher=make_fetcher("5.2.0"),
                terraform_runner=fake_plan(),
            )

        state = executor.registry.test_state
        assert state["push_calls"] == []
        assert state["pr_calls"] == []

    asyncio.run(_run())


def test_significance_assessment_requires_reasoning(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        llm = ScriptedTurnLLM({"recommendation": "merge now", "reasoning": ""})

        with pytest.raises(VersionBumpError, match="did not include reasoning"):
            await run_version_bump_check(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                tool_executor=executor,
                llm=llm,
                config=make_config(),
                http_fetcher=make_fetcher("5.2.0"),
                terraform_runner=fake_plan(),
            )

    asyncio.run(_run())


def test_bump_flow_raises_when_target_branch_is_missing(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        registry = make_fake_version_bump_registry()
        registry.test_state["branches"].clear()
        executor = make_executor(persistence, bus, job_id, registry=registry)
        llm = ScriptedTurnLLM(ASSESSMENT_REPLY)

        with pytest.raises(VersionBumpError, match="base branch not found"):
            await run_version_bump_check(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                tool_executor=executor,
                llm=llm,
                config=make_config(),
                http_fetcher=make_fetcher("5.2.0"),
                terraform_runner=fake_plan(),
            )

    asyncio.run(_run())
