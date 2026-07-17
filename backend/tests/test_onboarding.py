from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


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
            "include_paths": ["src/**", "infrastructure/**", "src/**"],
            "exclude_paths": ["docs/**"],
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

    assert relative_response.status_code == 400
    assert "absolute" in relative_response.json()["detail"]
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
        {"file_path": "azure-pipelines.release.yaml", "include_paths": [], "exclude_paths": []}
    ]


def test_onboarding_returns_not_found_for_unknown_record(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/onboarding/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
