import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.approvals import ApprovalAlreadyConsumedError, ApprovalNotFoundError, BlastRadiusError
from app.llm import LLMTurn
from app.models import (
    AgentStateEvent,
    ApplyResultEvent,
    ApprovalRequiredEvent,
    Event,
    JobCreatedEvent,
    PlanReadyEvent,
    PlattState,
    WorkItemMovedEvent,
)
from app.persistence import Persistence
from app.provision import (
    ClarificationNeededError,
    ProvisionConfig,
    SelfRepairExhaustedError,
    TerraformPlanResult,
    run_provision_apply,
    run_provision_plan,
)
from app.tools.context import ToolContext, ToolExecutionError
from app.tools.executor import ToolCapExceededError, ToolExecutor
from app.tools.registry import ToolDefinition, ToolRegistry


class CapturingBus:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def publish(self, event: Event) -> None:
        self.events.append(event)


class ScriptedJsonLLM:
    """Plays back pre-scripted JSON-content turns for the tool-free JSON calls provision.py makes."""

    def __init__(self, replies: list[dict[str, Any]]) -> None:
        self._replies = list(replies)
        self.calls = 0

    async def complete_turn(self, messages: list[dict], tools: list[dict]) -> LLMTurn:
        assert tools == []
        self.calls += 1
        return LLMTurn(content=json.dumps(self._replies.pop(0)), tool_calls=())


REQUIREMENT_REPLY = {
    "resource_type": "storage_account",
    "name": "platt-logs",
    "region": "eastus",
    "tags": {"owner": "platt"},
    "clarifying_question": None,
}
CHILDREN_REPLY = {"children": ["Write module", "Wire variables", "Add outputs", "Update docs"]}
TERRAFORM_REPLY = {
    "file_path": "modules/storage-account/platt-logs.tf",
    "content": 'resource "azurerm_storage_account" "platt_logs" {\n  name = "plattlogs"\n}\n',
}


def _happy_llm() -> ScriptedJsonLLM:
    return ScriptedJsonLLM([dict(REQUIREMENT_REPLY), dict(CHILDREN_REPLY), dict(TERRAFORM_REPLY)])


# -- fake provision tool registry (mock-friendly: no AzdoClient/network needed) -----


def _next_id_factory():
    counter = {"n": 100}

    def _next() -> int:
        counter["n"] += 1
        return counter["n"]

    return _next


def make_fake_provision_registry(
    *, pipeline_result: str = "succeeded", wiki_exists: bool = False
) -> ToolRegistry:
    registry = ToolRegistry()
    next_id = _next_id_factory()

    async def create_work_item(arguments: dict, ctx: ToolContext) -> dict:
        del ctx
        return {"id": next_id(), "fields": {"System.Title": arguments["title"]}}

    async def update_work_item_state(arguments: dict, ctx: ToolContext) -> dict:
        del ctx
        return {"id": arguments["work_item_id"], "fields": {"System.State": arguments["state"]}}

    async def create_pr(arguments: dict, ctx: ToolContext) -> dict:
        del ctx, arguments
        return {"pullRequestId": next_id()}

    async def run_pipeline(arguments: dict, ctx: ToolContext) -> dict:
        del ctx, arguments
        return {"id": next_id(), "state": "inProgress"}

    async def get_pipeline_run(arguments: dict, ctx: ToolContext) -> dict:
        del ctx, arguments
        return {"result": pipeline_result}

    async def get_wiki_page(arguments: dict, ctx: ToolContext) -> dict:
        del arguments, ctx
        if not wiki_exists:
            raise ToolExecutionError("wiki page not found")
        return {"content": "existing log\n", "eTag": "etag-1"}

    async def update_wiki_page(arguments: dict, ctx: ToolContext) -> dict:
        del ctx, arguments
        return {"id": 1}

    schema = {"type": "object"}
    for name, handler in [
        ("create_work_item", create_work_item),
        ("update_work_item_state", update_work_item_state),
        ("create_pr", create_pr),
        ("run_pipeline", run_pipeline),
        ("get_pipeline_run", get_pipeline_run),
        ("get_wiki_page", get_wiki_page),
        ("update_wiki_page", update_wiki_page),
    ]:
        registry.register(ToolDefinition(name, name, schema, handler))
    return registry


def make_executor(persistence: Persistence, bus: CapturingBus, job_id: UUID, **kwargs) -> ToolExecutor:
    cap = kwargs.pop("cap", 40)
    registry = kwargs.pop("registry", None) or make_fake_provision_registry(**kwargs)
    return ToolExecutor(registry, persistence, set(registry.names()), job_id=job_id, event_bus=bus, cap=cap)


@pytest.fixture
def persistence(tmp_path):
    instance = Persistence(db_path=tmp_path / "platt-provision-test.db")
    try:
        yield instance
    finally:
        instance.close()


def make_config(*, has_live_credentials: bool = False, apply_pipeline_id: int | None = None) -> ProvisionConfig:
    return ProvisionConfig(
        repository_id="repo-1",
        seed_infra_path=Path(__file__).resolve().parents[2] / "seed-infra",
        has_live_credentials=has_live_credentials,
        apply_pipeline_id=apply_pipeline_id,
    )


def fake_plan(*, addresses: list[str] | None = None, sandbox_rg: str = "sandbox-rg", destroys: int = 0):
    def _runner(file_path: str, content: str, config: ProvisionConfig) -> TerraformPlanResult:
        del file_path, content
        changes = []
        for address in addresses or [f"azurerm_storage_account.{sandbox_rg}.logs"]:
            changes.append({"address": address, "change": {"actions": ["create"]}})
        for i in range(destroys):
            changes.append(
                {"address": f"azurerm_storage_account.{sandbox_rg}.old{i}", "change": {"actions": ["delete"]}}
            )
        plan_json = {"resource_changes": changes}
        return TerraformPlanResult(plan_json=plan_json, plan_hash=f"hash-{config.sandbox_resource_group}", commit_sha="sha-1", simulated=True)

    return _runner


# -- plan phase: happy path, event ordering -----------------------------------------


def test_plan_phase_emits_the_full_event_sequence_and_requests_approval(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        llm = _happy_llm()

        result = await run_provision_plan(
            job_id=job_id,
            bus=bus,
            persistence=persistence,
            llm=llm,
            tool_executor=executor,
            prompt="Provision a storage account for logs",
            config=make_config(),
            terraform_runner=fake_plan(),
        )

        assert result.parent_work_item_id
        assert len(result.child_work_item_ids) == 4
        assert result.terraform_file_path == TERRAFORM_REPLY["file_path"]
        assert result.repair_attempts == 0

        event_types = [event.type for event in bus.events if event.type != "audit_entry"]
        assert event_types == [
            "job_created",
            "agent_state",  # thinking (requirement extraction)
            "agent_state",  # working (boards decomposition)
            "work_item_moved",  # parent
            "work_item_moved",  # child 1
            "work_item_moved",  # child 2
            "work_item_moved",  # child 3
            "work_item_moved",  # child 4
            "agent_state",  # working (terraform codegen)
            "agent_state",  # working (local terraform plan)
            "plan_ready",
            "agent_state",  # awaiting_approval
            "approval_required",
        ]

        job_created = bus.events[0]
        assert isinstance(job_created, JobCreatedEvent)
        assert job_created.prompt == "Provision a storage account for logs"

        approval_required = bus.events[-1]
        assert isinstance(approval_required, ApprovalRequiredEvent)
        assert approval_required.approval_id == result.approval_id

        plan_ready = next(e for e in bus.events if isinstance(e, PlanReadyEvent))
        assert plan_ready.has_blocking_changes is False

        approval = persistence.get_approval(result.approval_id)
        assert approval is not None
        assert approval["status"] == "pending"
        assert approval["plan_hash"] == result.plan.plan_hash

    asyncio.run(_run())


# -- clarification -------------------------------------------------------------------


def test_clarifying_question_stops_the_job_before_any_tool_calls(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        llm = ScriptedJsonLLM(
            [{"resource_type": "", "name": "", "region": "", "tags": {}, "clarifying_question": "Which region?"}]
        )

        with pytest.raises(ClarificationNeededError, match="Which region"):
            await run_provision_plan(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                llm=llm,
                tool_executor=executor,
                prompt="Provision a storage account",
                config=make_config(),
                terraform_runner=fake_plan(),
            )

        assert executor.call_count == 0

    asyncio.run(_run())


# -- blast radius blocks apply --------------------------------------------------------


def test_blast_radius_out_of_sandbox_triggers_self_repair_then_exhausts(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        # requirement + children + 4 terraform-codegen retries (initial + 3 repairs)
        llm = ScriptedJsonLLM(
            [dict(REQUIREMENT_REPLY), dict(CHILDREN_REPLY)] + [dict(TERRAFORM_REPLY) for _ in range(4)]
        )
        out_of_sandbox_plan = fake_plan(addresses=["azurerm_storage_account.prod-rg.logs"])

        with pytest.raises(SelfRepairExhaustedError):
            await run_provision_plan(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                llm=llm,
                tool_executor=executor,
                prompt="Provision a storage account",
                config=make_config(),
                terraform_runner=out_of_sandbox_plan,
            )

        concerned_states = [
            event for event in bus.events if isinstance(event, AgentStateEvent) and event.state == PlattState.CONCERNED
        ]
        # 3 "attempt N" events plus the final "self-repair exhausted" event.
        assert len(concerned_states) == 4
        assert not any(isinstance(event, ApprovalRequiredEvent) for event in bus.events)

    asyncio.run(_run())


def test_blast_radius_destroy_cap_blocks_the_plan(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        llm = ScriptedJsonLLM(
            [dict(REQUIREMENT_REPLY), dict(CHILDREN_REPLY)] + [dict(TERRAFORM_REPLY) for _ in range(4)]
        )
        too_many_destroys = fake_plan(destroys=4)

        with pytest.raises(SelfRepairExhaustedError) as excinfo:
            await run_provision_plan(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                llm=llm,
                tool_executor=executor,
                prompt="Provision a storage account",
                config=make_config(),
                terraform_runner=too_many_destroys,
            )
        assert isinstance(excinfo.value.__cause__, BlastRadiusError)

    asyncio.run(_run())


# -- caps -------------------------------------------------------------------------------


def test_tool_call_cap_propagates_uncaught_out_of_the_plan_phase(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        # 1 parent + up to 6 children could be created; cap at 1 forces failure on the first child.
        executor = make_executor(persistence, bus, job_id, cap=1)
        llm = _happy_llm()

        with pytest.raises(ToolCapExceededError):
            await run_provision_plan(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                llm=llm,
                tool_executor=executor,
                prompt="Provision a storage account",
                config=make_config(),
                terraform_runner=fake_plan(),
            )

    asyncio.run(_run())


# -- apply phase: structural gate ------------------------------------------------------


def test_apply_is_impossible_without_an_approval(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)

        with pytest.raises(ApprovalNotFoundError):
            await run_provision_apply(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                tool_executor=executor,
                config=make_config(has_live_credentials=True, apply_pipeline_id=7),
                plan_hash="hash-a",
                commit_sha="sha-a",
                parent_work_item_id="1",
                child_work_item_ids=["2", "3"],
            )

        assert executor.call_count == 0
        assert not any(isinstance(event, ApplyResultEvent) for event in bus.events)

    asyncio.run(_run())


def test_apply_blocked_without_live_credentials_even_when_approved(persistence: Persistence) -> None:
    async def _run() -> None:
        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)

        approval_id = uuid4()
        persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
        from datetime import datetime, timedelta

        persistence.decide_approval(
            approval_id, approver="alice", status="approved", expires_at=datetime.utcnow() + timedelta(seconds=900)
        )

        result = await run_provision_apply(
            job_id=job_id,
            bus=bus,
            persistence=persistence,
            tool_executor=executor,
            config=make_config(has_live_credentials=False, apply_pipeline_id=None),
            plan_hash="hash-a",
            commit_sha="sha-a",
            parent_work_item_id="1",
            child_work_item_ids=["2", "3"],
        )

        assert result.status == "apply_blocked"
        # No run_pipeline/apply-only tool ever ran.
        assert executor.call_count == 0
        apply_result = next(event for event in bus.events if isinstance(event, ApplyResultEvent))
        assert apply_result.success is False
        assert "live Azure credentials" in apply_result.summary

        # The approval was still consumed by the attempt (one-time, even though apply itself was gated off).
        approval = persistence.get_approval(approval_id)
        assert approval["consumed_at"] is not None

    asyncio.run(_run())


def test_apply_cannot_reuse_an_already_consumed_approval(persistence: Persistence) -> None:
    async def _run() -> None:
        from datetime import datetime, timedelta

        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id)
        approval_id = uuid4()
        persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
        persistence.decide_approval(
            approval_id, approver="alice", status="approved", expires_at=datetime.utcnow() + timedelta(seconds=900)
        )

        config = make_config(has_live_credentials=False)
        await run_provision_apply(
            job_id=job_id,
            bus=bus,
            persistence=persistence,
            tool_executor=executor,
            config=config,
            plan_hash="hash-a",
            commit_sha="sha-a",
            parent_work_item_id="1",
            child_work_item_ids=[],
        )

        with pytest.raises(ApprovalAlreadyConsumedError):
            await run_provision_apply(
                job_id=job_id,
                bus=bus,
                persistence=persistence,
                tool_executor=executor,
                config=config,
                plan_hash="hash-a",
                commit_sha="sha-a",
                parent_work_item_id="1",
                child_work_item_ids=[],
            )

    asyncio.run(_run())


# -- apply phase: full gated happy path -------------------------------------------------


def test_apply_full_happy_path_with_live_creds_reaches_celebrating(persistence: Persistence) -> None:
    async def _run() -> None:
        from datetime import datetime, timedelta

        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id, pipeline_result="succeeded", wiki_exists=True)

        approval_id = uuid4()
        persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
        persistence.decide_approval(
            approval_id, approver="alice", status="approved", expires_at=datetime.utcnow() + timedelta(seconds=900)
        )

        result = await run_provision_apply(
            job_id=job_id,
            bus=bus,
            persistence=persistence,
            tool_executor=executor,
            config=make_config(has_live_credentials=True, apply_pipeline_id=42),
            plan_hash="hash-a",
            commit_sha="sha-a",
            parent_work_item_id="1",
            child_work_item_ids=["2", "3"],
        )

        assert result.status == "applied"
        event_types = [event.type for event in bus.events if event.type != "audit_entry"]
        assert event_types == [
            "agent_state",  # working: triggering apply pipeline
            "apply_result",
            "agent_state",  # working: verifying apply
            "work_item_moved",  # parent -> Done
            "work_item_moved",  # child 2 -> Done
            "work_item_moved",  # child 3 -> Done
            "agent_state",  # celebrating
        ]
        assert bus.events[-1].state == PlattState.CELEBRATING
        apply_result = next(event for event in bus.events if isinstance(event, ApplyResultEvent))
        assert apply_result.success is True

        approval = persistence.get_approval(approval_id)
        assert approval["consumed_at"] is not None

    asyncio.run(_run())


def test_apply_pipeline_failure_stops_before_wiki_and_work_items(persistence: Persistence) -> None:
    async def _run() -> None:
        from datetime import datetime, timedelta

        bus = CapturingBus()
        job_id = uuid4()
        executor = make_executor(persistence, bus, job_id, pipeline_result="failed")

        approval_id = uuid4()
        persistence.create_approval(approval_id, job_id, "hash-a", "sha-a", scope="sandbox-rg")
        persistence.decide_approval(
            approval_id, approver="alice", status="approved", expires_at=datetime.utcnow() + timedelta(seconds=900)
        )

        result = await run_provision_apply(
            job_id=job_id,
            bus=bus,
            persistence=persistence,
            tool_executor=executor,
            config=make_config(has_live_credentials=True, apply_pipeline_id=42),
            plan_hash="hash-a",
            commit_sha="sha-a",
            parent_work_item_id="1",
            child_work_item_ids=["2"],
        )

        assert result.status == "apply_failed"
        assert not any(isinstance(event, WorkItemMovedEvent) for event in bus.events)
        assert bus.events[-1].state == PlattState.CONCERNED

    asyncio.run(_run())
