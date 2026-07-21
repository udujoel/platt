"""Tool registry: named, schema-described handlers exposed to the agent loop.

Tools are registered once (``DEFAULT_REGISTRY``); ``app.tools.executor``
enforces per-job allowlists, schema validation, the audit log, and the call
cap before ever invoking a handler, so registration here carries no trust by
itself.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.tools import azdo as azdo_tools
from app.tools import repo as repo_tools
from app.tools.context import ToolContext

if TYPE_CHECKING:
    from app.clients.azdo import AzdoClient

ToolHandler = Callable[[dict[str, Any], ToolContext], Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def schema(self) -> dict[str, Any]:
        """Render this tool in the OpenAI/Groq ``tools`` function-calling shape."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def schemas_for(self, names: Iterable[str]) -> list[dict[str, Any]]:
        """The LLM ``tools`` payload for a given set of tool names, in registry-defined form."""
        schemas = []
        for name in names:
            tool = self._tools.get(name)
            if tool is None:
                raise KeyError(f"unknown tool: {name}")
            schemas.append(tool.schema())
        return schemas


REPO_READ_TOOLS: frozenset[str] = frozenset({"read_file", "glob", "grep"})
AZDO_READ_TOOLS: frozenset[str] = frozenset(
    {"get_pr", "list_work_items", "get_wiki_page", "list_pipeline_runs", "get_pipeline_run"}
)

# Named per-job allowlists (PRD 7.4): a Q&A/onboarding-chat job gets read-only
# tools only. Add a new entry here rather than broadening an existing one.
JOB_ALLOWLISTS: dict[str, frozenset[str]] = {
    "onboarding_chat": REPO_READ_TOOLS,
    "chat": AZDO_READ_TOOLS,
}


def _azdo_handler(fn: Callable[..., Awaitable[Any]]) -> ToolHandler:
    async def handler(arguments: dict[str, Any], ctx: ToolContext) -> Any:
        client: AzdoClient = ctx.resource("azdo_client")
        return await fn(client, ctx.persistence, job_id=ctx.job_id, event_bus=ctx.event_bus, **arguments)

    return handler


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    repo_schemas = repo_tools.repo_tool_schemas()

    registry.register(
        ToolDefinition(
            "read_file",
            "Read one file from the onboarded repository checkout.",
            repo_schemas["read_file"],
            repo_tools.read_file,
        )
    )
    registry.register(
        ToolDefinition(
            "glob",
            "List onboarded repository paths matching a relative POSIX glob.",
            repo_schemas["glob"],
            repo_tools.glob,
        )
    )
    registry.register(
        ToolDefinition(
            "grep",
            "Find literal text across the onboarded repository checkout.",
            repo_schemas["grep"],
            repo_tools.grep,
        )
    )

    registry.register(
        ToolDefinition(
            "get_pr",
            "Get an Azure DevOps pull request by repository and id.",
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["repository_id", "pull_request_id"],
                "properties": {
                    "repository_id": {"type": "string", "minLength": 1, "maxLength": 256},
                    "pull_request_id": {"type": "integer", "minimum": 1},
                },
            },
            _azdo_handler(azdo_tools.get_pr),
        )
    )
    registry.register(
        ToolDefinition(
            "list_work_items",
            "Run a WIQL query against Azure Boards work items.",
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["wiql_query"],
                "properties": {"wiql_query": {"type": "string", "minLength": 1, "maxLength": 4000}},
            },
            _azdo_handler(azdo_tools.list_work_items),
        )
    )
    registry.register(
        ToolDefinition(
            "get_wiki_page",
            "Read one Azure DevOps wiki page by path.",
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["wiki_identifier", "path"],
                "properties": {
                    "wiki_identifier": {"type": "string", "minLength": 1, "maxLength": 256},
                    "path": {"type": "string", "minLength": 1, "maxLength": 1024},
                },
            },
            _azdo_handler(azdo_tools.get_wiki_page),
        )
    )
    registry.register(
        ToolDefinition(
            "list_pipeline_runs",
            "List recent runs for an Azure DevOps pipeline.",
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["pipeline_id"],
                "properties": {"pipeline_id": {"type": "integer", "minimum": 1}},
            },
            _azdo_handler(azdo_tools.list_pipeline_runs),
        )
    )
    registry.register(
        ToolDefinition(
            "get_pipeline_run",
            "Get one Azure DevOps pipeline run by pipeline and run id.",
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["pipeline_id", "run_id"],
                "properties": {
                    "pipeline_id": {"type": "integer", "minimum": 1},
                    "run_id": {"type": "integer", "minimum": 1},
                },
            },
            _azdo_handler(azdo_tools.get_pipeline_run),
        )
    )
    return registry


DEFAULT_REGISTRY = build_default_registry()
