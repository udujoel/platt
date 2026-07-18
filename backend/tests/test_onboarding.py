from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def configure_onboarding_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_ONBOARDING_ROOT", str(tmp_path))


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(db_path=tmp_path / "platt.sqlite3", onboarding_db_path=tmp_path / "onboarding.sqlite3"))


def test_onboarding_indexes_local_files_terraform_and_pipeline_paths(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "main.tf").write_text(
        '''module "network" {
  source = "../../modules/network"
}

module "registry" {
  source = "Azure/avm-res-containerregistry-registry/azurerm"
}
'''
    )
    (repository / "azure-pipelines.yml").write_text(
        """trigger:
  paths:
    include:
      - src/**
      - infrastructure/**
    exclude:
      - docs/**
pr:
  paths:
    include:
      - src/**
"""
    )
    (repository / "README.md").write_text("local project")

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 201
    record = response.json()
    assert record["repository_path"] == str(repository.resolve())
    assert {entry["path"] for entry in record["files"]} == {
        "README.md",
        "azure-pipelines.yml",
        "main.tf",
    }
    assert record["terraform_modules"] == [
        {"file_path": "main.tf", "name": "network", "source": "../../modules/network"},
        {
            "file_path": "main.tf",
            "name": "registry",
            "source": "Azure/avm-res-containerregistry-registry/azurerm",
        },
    ]
    assert record["pipeline_yamls"] == [
        {
            "file_path": "azure-pipelines.yml",
            "path_filters": [
                {
                    "scope": "trigger",
                    "include_paths": ["src/**", "infrastructure/**"],
                    "exclude_paths": ["docs/**"],
                },
                {
                    "scope": "pr",
                    "include_paths": ["src/**"],
                    "exclude_paths": [],
                },
            ],
        }
    ]


def test_onboarding_record_is_persisted_and_retrievable(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "app.py").write_text("print('hello')")
    client = _client(tmp_path)

    created = client.post("/onboarding", json={"repository_path": str(repository)})
    fetched = client.get(f"/onboarding/{created.json()['id']}")

    assert created.status_code == 201
    assert fetched.status_code == 200
    assert fetched.json() == created.json()


def test_onboarding_builds_a_local_module_graph_and_traces_to_root(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    application_module = repository / "modules" / "application"
    logging_module = repository / "modules" / "logging"
    application_module.mkdir(parents=True)
    logging_module.mkdir(parents=True)
    (repository / "main.tf").write_text(
        '''variable "environment" { type = string }
module "application" {
  source = "./modules/application"
}
output "application_id" { value = module.application.id }
'''
    )
    (application_module / "main.tf").write_text(
        '''variable "name" { type = string }
module "logging" {
  source = "../logging"
}
'''
    )
    (logging_module / "main.tf").write_text('output "workspace_id" { value = "example" }\n')
    client = _client(tmp_path)

    created = client.post("/onboarding", json={"repository_path": str(repository)})

    assert created.status_code == 201
    record = created.json()
    assert record["terraform_module_nodes"] == [
        {"path": ".", "variables": ["environment"], "outputs": ["application_id"]},
        {"path": "modules/application", "variables": ["name"], "outputs": []},
        {"path": "modules/logging", "variables": [], "outputs": ["workspace_id"]},
    ]
    assert record["terraform_module_edges"] == [
        {
            "caller_path": ".",
            "module_name": "application",
            "source": "./modules/application",
            "target_path": "modules/application",
        },
        {
            "caller_path": "modules/application",
            "module_name": "logging",
            "source": "../logging",
            "target_path": "modules/logging",
        },
    ]

    trace = client.get(f"/onboarding/{record['id']}/module-trace", params={"module_path": "modules/logging"})

    assert trace.status_code == 200
    assert trace.json()["path_to_root"] == [".", "modules/application", "modules/logging"]
    assert [edge["module_name"] for edge in trace.json()["edges"]] == ["application", "logging"]


def test_module_trace_rejects_an_unknown_module(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "main.tf").write_text('variable "environment" { type = string }\n')
    client = _client(tmp_path)
    created = client.post("/onboarding", json={"repository_path": str(repository)})

    response = client.get(f"/onboarding/{created.json()['id']}/module-trace", params={"module_path": "missing"})

    assert response.status_code == 404


def test_module_trace_uses_a_root_connected_parent_when_the_first_parent_is_orphaned(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    for module_path in ("a", "b", "shared"):
        (repository / module_path).mkdir(parents=True)
    (repository / "main.tf").write_text('module "b" { source = "./b" }\n')
    (repository / "a" / "main.tf").write_text('module "shared" { source = "../shared" }\n')
    (repository / "b" / "main.tf").write_text('module "shared" { source = "../shared" }\n')
    (repository / "shared" / "main.tf").write_text('variable "name" { type = string }\n')
    client = _client(tmp_path)

    created = client.post("/onboarding", json={"repository_path": str(repository)})
    assert created.status_code == 201
    trace = client.get(f"/onboarding/{created.json()['id']}/module-trace", params={"module_path": "shared"})

    assert trace.status_code == 200
    assert trace.json()["path_to_root"] == [".", "b", "shared"]
    assert [edge["caller_path"] for edge in trace.json()["edges"]] == [".", "b"]


def test_repository_tools_read_glob_grep_and_audit_a_persisted_inventory(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    (repository / "modules").mkdir(parents=True)
    (repository / "README.md").write_text("Platt indexes Terraform safely.\n")
    (repository / "main.tf").write_text('module "network" { source = "./modules/network" }\n')
    (repository / "modules" / "network.tf").write_text('resource "azurerm_virtual_network" "main" {}\n')

    with _client(tmp_path) as client:
        created = client.post("/onboarding", json={"repository_path": str(repository)})
        assert created.status_code == 201
        onboarding_id = created.json()["id"]

        definitions = client.get(f"/onboarding/{onboarding_id}/tools")
        read = client.post(
            f"/onboarding/{onboarding_id}/tools/invoke",
            json={"tool": "read_file", "arguments": {"path": "README.md"}},
        )
        glob = client.post(
            f"/onboarding/{onboarding_id}/tools/invoke",
            json={"tool": "glob", "arguments": {"pattern": "**/*.tf"}},
        )
        grep = client.post(
            f"/onboarding/{onboarding_id}/tools/invoke",
            json={"tool": "grep", "arguments": {"query": "azurerm_virtual_network"}},
        )
        audit = client.get("/audit")

    assert definitions.status_code == 200
    assert [definition["name"] for definition in definitions.json()] == ["read_file", "glob", "grep"]
    assert read.json()["result"] == {"path": "README.md", "content": "Platt indexes Terraform safely.\n"}
    assert glob.json()["result"] == {"paths": ["main.tf", "modules/network.tf"], "truncated": False}
    assert grep.json()["result"] == {
        "matches": [{"path": "modules/network.tf", "line_number": 1, "line": 'resource "azurerm_virtual_network" "main" {}'}],
        "scanned_files": 3,
        "truncated": False,
    }
    assert {(entry["tool"], entry["outcome"]) for entry in audit.json()["entries"]} >= {
        ("repo.read_file", "succeeded"),
        ("repo.glob", "succeeded"),
        ("repo.grep", "succeeded"),
    }


def test_repository_tools_refuse_paths_that_were_not_in_the_inventory(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    visible = repository / "visible.txt"
    outside = tmp_path / "outside.txt"
    visible.write_text("visible")
    outside.write_text("outside")

    with _client(tmp_path) as client:
        created = client.post("/onboarding", json={"repository_path": str(repository)})
        assert created.status_code == 201
        visible.unlink()
        visible.symlink_to(outside)
        rejected = client.post(
            f"/onboarding/{created.json()['id']}/tools/invoke",
            json={"tool": "read_file", "arguments": {"path": "visible.txt"}},
        )
        audit = client.get("/audit")

    assert rejected.status_code == 400
    assert "regular file" in rejected.json()["detail"]
    assert any(entry["tool"] == "repo.read_file" and entry["outcome"] == "rejected" for entry in audit.json()["entries"])


def test_repository_grep_marks_results_truncated_at_its_read_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "a.txt").write_text("needle\n")
    (repository / "b.txt").write_text("needle\n")
    monkeypatch.setattr("app.services.onboarding.MAX_GREP_BYTES", 10)

    with _client(tmp_path) as client:
        created = client.post("/onboarding", json={"repository_path": str(repository)})
        assert created.status_code == 201
        response = client.post(
            f"/onboarding/{created.json()['id']}/tools/invoke",
            json={"tool": "grep", "arguments": {"query": "needle"}},
        )

    assert response.status_code == 200
    assert response.json()["result"] == {
        "matches": [{"path": "a.txt", "line_number": 1, "line": "needle"}],
        "scanned_files": 1,
        "truncated": True,
    }


def test_repository_glob_marks_results_truncated_at_its_path_budget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "a.tf").write_text("")
    (repository / "b.tf").write_text("")
    monkeypatch.setattr("app.services.onboarding.MAX_GLOB_RESULTS", 1)

    with _client(tmp_path) as client:
        created = client.post("/onboarding", json={"repository_path": str(repository)})
        assert created.status_code == 201
        response = client.post(
            f"/onboarding/{created.json()['id']}/tools/invoke",
            json={"tool": "glob", "arguments": {"pattern": "*.tf"}},
        )

    assert response.status_code == 200
    assert response.json()["result"] == {"paths": ["a.tf"], "truncated": True}


def test_onboarding_rejects_non_absolute_or_missing_paths(tmp_path: Path) -> None:
    client = _client(tmp_path)

    relative_response = client.post("/onboarding", json={"repository_path": "relative/repository"})
    missing_response = client.post("/onboarding", json={"repository_path": str(tmp_path / "missing")})

    assert relative_response.status_code == 422
    assert "absolute" in relative_response.json()["detail"][0]["msg"]
    assert missing_response.status_code == 400


def test_onboarding_does_not_follow_symlinks_or_inventory_git_metadata(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    outside = tmp_path / "outside.txt"
    repository.mkdir()
    (repository / ".git").mkdir()
    (repository / ".git" / "config").write_text("sensitive")
    (repository / "visible.txt").write_text("visible")
    outside.write_text("outside")
    (repository / "outside-link.txt").symlink_to(outside)

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 201
    assert [entry["path"] for entry in response.json()["files"]] == ["visible.txt"]


def test_onboarding_rejects_symlinked_repository_root(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    linked_repository = tmp_path / "repository-link"
    repository.mkdir()
    linked_repository.symlink_to(repository, target_is_directory=True)

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(linked_repository)})

    assert response.status_code == 400
    assert "must not be a symlink" in response.json()["detail"]


def test_onboarding_rejects_repositories_outside_trusted_root(tmp_path: Path) -> None:
    outside_repository = tmp_path.parent / f"{tmp_path.name}-outside-repository"
    outside_repository.mkdir()

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(outside_repository)})

    assert response.status_code == 400
    assert "configured onboarding root" in response.json()["detail"]


def test_onboarding_inventories_conventional_pipeline_file_without_a_trigger(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "azure-pipelines.release.yaml").write_text(
        """steps:
  - script: echo deploy
"""
    )

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 201
    assert response.json()["pipeline_yamls"] == [
        {"file_path": "azure-pipelines.release.yaml", "path_filters": []}
    ]


def test_onboarding_ignores_non_pipeline_yaml_with_nested_azure_keys(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "application.yaml").write_text(
        """service:
  pool:
    size: 4
  resources:
    cache: enabled
"""
    )

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 201
    assert response.json()["pipeline_yamls"] == []


def test_onboarding_ignores_kustomize_resources_manifest(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "kustomization.yaml").write_text(
        """resources:
  - deployment.yaml
"""
    )

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 201
    assert response.json()["pipeline_yamls"] == []


def test_onboarding_indexes_resource_only_azure_pipeline(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "release.yml").write_text(
        """resources:
  repositories:
    - repository: shared
      type: git
      name: platform/shared-pipeline
"""
    )

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 201
    assert response.json()["pipeline_yamls"] == [{"file_path": "release.yml", "path_filters": []}]


def test_onboarding_parses_terraform_blocks_with_trailing_comments(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "main.tf").write_text(
        '''module "network" {
  source = "../../modules/network"
  providers = {
    azurerm = azurerm.shared
  }
  description = <<-EOT
    A literal with braces: { and }
  EOT
  # This comment contains a closing brace: }
} # network module
'''
    )

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 201
    assert response.json()["terraform_modules"] == [
        {"file_path": "main.tf", "name": "network", "source": "../../modules/network"}
    ]


def test_onboarding_rejects_oversized_parseable_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.onboarding.MAX_FILE_BYTES", 32)
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "main.tf").write_text('module "network" {\n  source = "../../modules/network"\n}\n')

    response = _client(tmp_path).post("/onboarding", json={"repository_path": str(repository)})

    assert response.status_code == 400
    assert "exceeds" in response.json()["detail"]


def test_onboarding_returns_not_found_for_unknown_record(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/onboarding/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
