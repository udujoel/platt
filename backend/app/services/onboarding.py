"""Bounded, local-only repository onboarding helpers.

This module deliberately performs no git, Azure, Terraform, or network calls.
It only reads files beneath a caller-supplied, already-present directory.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
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
TRUSTED_ONBOARDING_ROOT_ENV = "PLATT_ONBOARDING_ROOT"
IGNORED_DIRECTORY_NAMES = {".git", ".terraform", "node_modules", ".venv", "venv", "__pycache__"}
TERRAFORM_MODULE_START_RE = re.compile(r'(?m)^\s*module\s+"(?P<name>[^"]+)"\s*\{')
TERRAFORM_SOURCE_RE = re.compile(r'(?m)^\s*source\s*=\s*"(?P<source>[^"]+)"')
TERRAFORM_HEREDOC_START_RE = re.compile(r"<<-?\s*(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)")
YAML_SCOPE_RE = re.compile(r"^(?P<scope>trigger|pr|schedules)\s*:\s*(?:#.*)?$")
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


def _trusted_onboarding_root() -> Path:
    configured_root = os.environ.get(TRUSTED_ONBOARDING_ROOT_ENV, "").strip()
    if not configured_root:
        raise OnboardingError(f"{TRUSTED_ONBOARDING_ROOT_ENV} must be configured before onboarding")

    supplied_root = Path(configured_root).expanduser()
    if supplied_root.is_symlink():
        raise OnboardingError(f"{TRUSTED_ONBOARDING_ROOT_ENV} must not be a symlink")
    try:
        root = supplied_root.resolve(strict=True)
    except OSError as error:
        raise OnboardingError(f"{TRUSTED_ONBOARDING_ROOT_ENV} does not exist or cannot be resolved") from error
    if not root.is_dir():
        raise OnboardingError(f"{TRUSTED_ONBOARDING_ROOT_ENV} must point to a directory")
    return root


def validate_repository_path(repository_path: str) -> Path:
    """Resolve a repository under the configured checkout root without symlink escape."""
    supplied = Path(repository_path).expanduser()
    if not supplied.is_absolute():
        raise OnboardingError("repository_path must be an absolute local directory")
    if supplied.is_symlink():
        raise OnboardingError("repository_path must not be a symlink")
    try:
        root = supplied.resolve(strict=True)
    except OSError as error:
        raise OnboardingError("repository_path does not exist or cannot be resolved") from error
    if not root.is_dir():
        raise OnboardingError("repository_path must point to a directory")
    trusted_root = _trusted_onboarding_root()
    if not _is_within(trusted_root, root):
        raise OnboardingError("repository_path must be inside the configured onboarding root")
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


def _read_bounded_text(root: Path, path: Path, file_kind: str) -> str | None:
    try:
        with path.open("rb") as file:
            contents = file.read(MAX_FILE_BYTES + 1)
    except OSError:
        return None
    if len(contents) > MAX_FILE_BYTES:
        raise OnboardingError(f"{file_kind} exceeds the {MAX_FILE_BYTES} byte onboarding limit: {_relative_path(root, path)}")
    return contents.decode("utf-8", errors="replace")


def _inventory_files(root: Path, files: list[Path]) -> list[FileInventoryEntry]:
    entries: list[FileInventoryEntry] = []
    for path in files:
        try:
            size_bytes = path.stat().st_size
        except OSError:
            continue
        entries.append(FileInventoryEntry(path=_relative_path(root, path), size_bytes=size_bytes))
    return entries


def _terraform_module_bodies(contents: str) -> Iterator[tuple[str, str]]:
    """Yield module names and balanced block bodies without treating trailing comments as syntax."""
    for match in TERRAFORM_MODULE_START_RE.finditer(contents):
        opening_brace = match.end() - 1
        depth = 0
        quote: str | None = None
        escaped = False
        heredoc_delimiter: str | None = None
        index = opening_brace
        line_start = True
        while index < len(contents):
            character = contents[index]
            if heredoc_delimiter:
                line_end = contents.find("\n", index)
                if line_end == -1:
                    line_end = len(contents)
                if line_start and contents[index:line_end].strip() == heredoc_delimiter:
                    heredoc_delimiter = None
                line_start = line_end < len(contents)
                index = line_end + 1
                continue
            if quote:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
                line_start = character == "\n"
                index += 1
                continue
            if character == "#" or contents.startswith("//", index):
                line_end = contents.find("\n", index)
                if line_end == -1:
                    break
                index = line_end + 1
                line_start = True
                continue
            if contents.startswith("/*", index):
                comment_end = contents.find("*/", index + 2)
                if comment_end == -1:
                    break
                line_start = contents[index:comment_end + 2].endswith("\n")
                index = comment_end + 2
                continue
            if character in {"\"", "'"}:
                quote = character
            else:
                heredoc_match = TERRAFORM_HEREDOC_START_RE.match(contents, index)
                if heredoc_match:
                    heredoc_delimiter = heredoc_match.group("delimiter")
                    index = heredoc_match.end()
                    line_start = False
                    continue
                if character == "{":
                    depth += 1
                elif character == "}":
                    depth -= 1
                    if depth == 0:
                        yield match.group("name"), contents[opening_brace + 1 : index]
                        break
            line_start = character == "\n"
            index += 1


def _terraform_modules(root: Path, files: list[Path]) -> list[TerraformModuleReference]:
    modules: list[TerraformModuleReference] = []
    for path in files:
        if path.suffix != ".tf":
            continue
        contents = _read_bounded_text(root, path, "Terraform file")
        if contents is None:
            continue
        for name, body in _terraform_module_bodies(contents):
            source = TERRAFORM_SOURCE_RE.search(body)
            if source:
                modules.append(
                    TerraformModuleReference(
                        file_path=_relative_path(root, path),
                        name=name,
                        source=source.group("source"),
                    )
                )
    return modules


def _yaml_path_filters(contents: str) -> list[tuple[str, list[str], list[str]]]:
    """Extract distinct trigger, PR, and schedule `paths` lists without a YAML parser."""
    filters: list[tuple[str, list[str], list[str]]] = []
    scope: str | None = None
    scope_indent: int | None = None
    includes: list[str] | None = None
    excludes: list[str] | None = None
    active: list[str] | None = None
    paths_indent: int | None = None
    for line in contents.splitlines():
        scope_match = YAML_SCOPE_RE.match(line)
        if scope_match:
            scope = scope_match.group("scope")
            scope_indent = len(line) - len(line.lstrip())
            paths_indent = None
            active = None
            continue
        indent = len(line) - len(line.lstrip())
        if scope_indent is not None and line.strip() and indent <= scope_indent:
            scope = None
            scope_indent = None
            paths_indent = None
            active = None
        if scope is None:
            continue
        if YAML_PATHS_RE.match(line):
            paths_indent = indent
            includes = []
            excludes = []
            filters.append((scope, includes, excludes))
            active = None
            continue
        if paths_indent is None:
            continue
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
    return filters


def _pipeline_yamls(root: Path, files: list[Path]) -> list[PipelineYamlInventory]:
    inventories: list[PipelineYamlInventory] = []
    for path in files:
        if path.suffix.lower() not in {".yml", ".yaml"}:
            continue
        contents = _read_bounded_text(root, path, "Pipeline YAML")
        if contents is None:
            continue
        # Conventionally named pipeline files may consist only of a template/steps,
        # while other Azure definitions usually contain one of these root-level keys.
        conventional_name = "azure-pipelines" in path.name.lower()
        azure_signature = re.search(r"(?m)^(trigger|pr|schedules|extends|pool|stages)\s*:", contents)
        if not conventional_name and not azure_signature:
            continue
        path_filters = [
            {"scope": scope, "include_paths": include_paths, "exclude_paths": exclude_paths}
            for scope, include_paths, exclude_paths in _yaml_path_filters(contents)
        ]
        inventories.append(
            PipelineYamlInventory(
                file_path=_relative_path(root, path),
                path_filters=path_filters,
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
        configured_path = os.environ.get("PLATT_ONBOARDING_DB", "").strip()
        self._uses_private_default = database_path is None and not configured_path
        if database_path is not None:
            self.database_path = database_path
        elif configured_path:
            self.database_path = Path(configured_path)
        else:
            self.database_path = self._private_default_database_path()
        self._initialize()

    @staticmethod
    def _private_default_database_path() -> Path:
        data_directory = Path.cwd() / ".platt"
        data_directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        data_directory.chmod(0o700)
        return data_directory / "onboarding.sqlite3"

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
        if self._uses_private_default:
            self.database_path.chmod(0o600)

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
