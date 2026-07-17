from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(autouse=True)
def configure_onboarding_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATT_ONBOARDING_ROOT", str(tmp_path))


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(onboarding_db_path=tmp_path / "onboarding.sqlite3"))


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
