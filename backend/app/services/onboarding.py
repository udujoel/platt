"""Bounded, local-only repository onboarding helpers.

This module deliberately performs no git, Azure, Terraform, or network calls.
It only reads files beneath a caller-supplied, already-present directory.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from app.models import (
    FileInventoryEntry,
    OnboardingRecord,
    PipelineYamlInventory,
    TerraformModuleReference,
)

MAX_FILES = 5_000
MAX_DIRECTORIES = 2_000
MAX_FILE_BYTES = 1_000_000
IGNORED_DIRECTORY_NAMES = {".git", ".terraform", "node_modules", ".venv", "venv", "__pycache__"}
TERRAFORM_MODULE_RE = re.compile(
    r'(?ms)^\s*module\s+"(?P<name>[^"]+)"\s*\{(?P<body>.*?)^\s*\}'
)
TERRAFORM_SOURCE_RE = re.compile(r'(?m)^\s*source\s*=\s*"(?P<source>[^"]+)"')
YAML_PATHS_RE = re.compile(r"^\s*paths\s*:\s*(?:#.*)?$")
YAML_LIST_ITEM_RE = re.compile(r"^\s*-\s*(?P<path>[^#\s][^#]*?)\s*(?:#.*)?$")


class OnboardingError(ValueError):
    """A request cannot be indexed safely."""


class OnboardingNotFoundError(LookupError):
    """The requested persisted onboarding run does not exist."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def validate_repository_path(repository_path: str) -> Path:
    """Resolve an absolute local directory without allowing symlink escape."""
    supplied = Path(repository_path).expanduser()
    if not supplied.is_absolute():
        raise OnboardingError("repository_path must be an absolute local directory")
    try:
        root = supplied.resolve(strict=True)
    except OSError as error:
        raise OnboardingError("repository_path does not exist or cannot be resolved") from error
    if not root.is_dir():
        raise OnboardingError("repository_path must point to a directory")
    return root


def _walk_files(root: Path) -> Iterator[Path]:
    """Walk a repository without following symlinks or unbounded directory trees."""
    file_count = 0
    directory_count = 0
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = sorted(
            name
            for name in directories
            if name not in IGNORED_DIRECTORY_NAMES
            and not (current_path / name).is_symlink()
        )
        directory_count += 1
        if directory_count > MAX_DIRECTORIES:
            raise OnboardingError(f"repository exceeds the {MAX_DIRECTORIES} directory onboarding limit")
        for name in sorted(filenames):
            path = current_path / name
            try:
                resolved_path = path.resolve(strict=True)
                is_regular_file = path.is_file()
            except OSError:
                continue
            if path.is_symlink() or not is_regular_file or not _is_within(root, resolved_path):
                continue
            file_count += 1
            if file_count > MAX_FILES:
                raise OnboardingError(f"repository exceeds the {MAX_FILES} file onboarding limit")
            yield path


def _read_text(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _inventory_files(root: Path, files: list[Path]) -> list[FileInventoryEntry]:
    entries: list[FileInventoryEntry] = []
    for path in files:
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue
        entries.append(FileInventoryEntry(path=_relative_path(root, path), size_bytes=size_bytes))
    return entries


def _terraform_modules(root: Path, files: list[Path]) -> list[TerraformModuleReference]:
    modules: list[TerraformModuleReference] = []
    for path in files:
        if path.suffix != ".tf":
            continue
        contents = _read_text(path)
        if contents is None:
            continue
        for match in TERRAFORM_MODULE_RE.finditer(contents):
            source = TERRAFORM_SOURCE_RE.search(match.group("body"))
            if source:
                modules.append(
                    TerraformModuleReference(
                        file_path=_relative_path(root, path),
                        name=match.group("name"),
                        source=source.group("source"),
                    )
                )
    return modules


def _yaml_path_filters(contents: str) -> tuple[list[str], list[str]]:
    """Extract simple Azure Pipelines `paths` include/exclude lists without a YAML parser."""
    includes: list[str] = []
    excludes: list[str] = []
    active: list[str] | None = None
    paths_indent: int | None = None
    for line in contents.splitlines():
        if YAML_PATHS_RE.match(line):
            paths_indent = len(line) - len(line.lstrip())
            active = None
            continue
        if paths_indent is None:
            continue
        indent = len(line) - len(line.lstrip())
        if line.strip() and indent <= paths_indent:
            paths_indent = None
            active = None
            continue
        key = line.strip().rstrip(":")
        if indent > paths_indent and key == "include":
            active = includes
            continue
        if indent > paths_indent and key == "exclude":
            active = excludes
            continue
        item = YAML_LIST_ITEM_RE.match(line)
        if item and active is not None:
            active.append(item.group("path").strip().strip('"\''))
    return includes, excludes


def _pipeline_yamls(root: Path, files: list[Path]) -> list[PipelineYamlInventory]:
    inventories: list[PipelineYamlInventory] = []
    for path in files:
        if path.suffix.lower() not in {".yml", ".yaml"}:
            continue
        contents = _read_text(path)
        if contents is None:
            continue
        # Conventionally named pipeline files may consist only of a template/steps,
        # while other Azure definitions usually contain one of these root-level keys.
        conventional_name = "azure-pipelines" in path.name.lower()
        azure_signature = re.search(
            r"(?m)^\s*(trigger|pr|schedules|extends|pool|stages|resources)\s*:", contents
        )
        if not conventional_name and not azure_signature:
            continue
        include_paths, exclude_paths = _yaml_path_filters(contents)
        inventories.append(
            PipelineYamlInventory(
                file_path=_relative_path(root, path),
                include_paths=include_paths,
                exclude_paths=exclude_paths,
            )
        )
    return inventories


def inspect_repository(repository_path: str) -> OnboardingRecord:
    root = validate_repository_path(repository_path)
    files = list(_walk_files(root))
    return OnboardingRecord(
        id=uuid4(),
        repository_path=str(root),
        created_at=_utc_now(),
        files=_inventory_files(root, files),
        terraform_modules=_terraform_modules(root, files),
        pipeline_yamls=_pipeline_yamls(root, files),
    )


class OnboardingStore:
    """Small SQLite store for completed local onboarding records."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path or Path(
            os.environ.get("PLATT_ONBOARDING_DB", str(Path(tempfile.gettempdir()) / "platt-onboarding.sqlite3"))
        )
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS onboarding_records (
                    id TEXT PRIMARY KEY,
                    repository_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    record_json TEXT NOT NULL
                )
                """
            )

    def save(self, record: OnboardingRecord) -> OnboardingRecord:
        payload = record.model_dump_json()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO onboarding_records (id, repository_path, created_at, record_json) VALUES (?, ?, ?, ?)",
                (str(record.id), record.repository_path, record.created_at.isoformat(), payload),
            )
        return record

    def get(self, onboarding_id: UUID) -> OnboardingRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM onboarding_records WHERE id = ?", (str(onboarding_id),)
            ).fetchone()
        if row is None:
            raise OnboardingNotFoundError(str(onboarding_id))
        return OnboardingRecord.model_validate(json.loads(row[0]))
