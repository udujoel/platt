from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


SEED_REPOSITORY = Path(__file__).resolve().parents[2] / "seed-infra"


@pytest.fixture
def onboarded_seed_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    monkeypatch.setenv("PLATT_ONBOARDING_ROOT", str(SEED_REPOSITORY.parent))
    with TestClient(
        create_app(db_path=tmp_path / "platt.sqlite3")
    ) as client:
        created = client.post("/onboarding", json={"repository_path": str(SEED_REPOSITORY)})
        assert created.status_code == 201
        yield client, created.json()["id"]


def invoke_tool(client: TestClient, onboarding_id: str, tool: str, arguments: dict[str, str]) -> dict:
    response = client.post(f"/onboarding/{onboarding_id}/tools/invoke", json={"tool": tool, "arguments": arguments})
    assert response.status_code == 200
    return response.json()["result"]


def test_seed_question_1_lists_the_three_root_modules(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    record = client.get(f"/onboarding/{onboarding_id}").json()

    assert [edge["module_name"] for edge in record["terraform_module_edges"]] == [
        "log_analytics_workspace",
        "naming",
        "storage_account",
    ]


def test_seed_question_2_traces_storage_to_root(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    trace = client.get(f"/onboarding/{onboarding_id}/module-trace", params={"module_path": "modules/storage-account"})

    assert trace.json()["path_to_root"] == [".", "modules/storage-account"]


def test_seed_question_3_traces_log_analytics_to_root(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    trace = client.get(f"/onboarding/{onboarding_id}/module-trace", params={"module_path": "modules/log-analytics-workspace"})

    assert trace.json()["path_to_root"] == [".", "modules/log-analytics-workspace"]


def test_seed_question_4_finds_the_storage_account_resource(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    result = invoke_tool(client, onboarding_id, "grep", {"query": "azurerm_storage_account"})

    assert result["matches"][0]["path"] == "modules/storage-account/main.tf"


def test_seed_question_5_finds_the_log_analytics_resource(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    result = invoke_tool(client, onboarding_id, "grep", {"query": "azurerm_log_analytics_workspace"})

    assert result["matches"][0]["path"] == "modules/log-analytics-workspace/main.tf"


def test_seed_question_6_finds_plan_and_apply_pipelines(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    result = invoke_tool(client, onboarding_id, "glob", {"pattern": "pipelines/*.yml"})

    assert result["paths"] == ["pipelines/platt-apply.yml", "pipelines/platt-plan.yml"]


def test_seed_question_7_reads_the_azurerm_provider_constraint(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    result = invoke_tool(client, onboarding_id, "read_file", {"path": "versions.tf"})

    assert re.search(
        r'required_providers\s*\{.*?azurerm\s*=\s*\{.*?source\s*=\s*"hashicorp/azurerm".*?version\s*=\s*"~> 4\.0"',
        result["content"],
        re.DOTALL,
    )


def test_seed_question_8_reads_storage_network_default_deny(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    result = invoke_tool(client, onboarding_id, "read_file", {"path": "modules/storage-account/main.tf"})

    assert re.search(
        r'resource\s+"azurerm_storage_account"\s+"this"\s*\{.*?network_rules\s*\{.*?default_action\s*=\s*"Deny"',
        result["content"],
        re.DOTALL,
    )


def test_seed_question_9_finds_required_governance_tags(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    result = invoke_tool(client, onboarding_id, "read_file", {"path": "main.tf"})

    assert re.search(
        r'mandatory_tag_keys\s*=\s*\{.*?CostCenter\s*=\s*"costcenter"',
        result["content"],
        re.DOTALL,
    )
    assert re.search(
        r'module\s+"storage_account"\s*\{.*?tags\s*=\s*local\.common_tags',
        result["content"],
        re.DOTALL,
    )


def test_seed_question_10_finds_the_dev_only_environment_guard(onboarded_seed_repository: tuple[TestClient, str]) -> None:
    client, onboarding_id = onboarded_seed_repository
    result = invoke_tool(client, onboarding_id, "grep", {"query": 'contains(["dev"], var.environment)'})

    assert result["matches"][0]["path"] == "variables.tf"
