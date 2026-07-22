"""Repo read tools, bound to whatever onboarded checkout a job's context provides.

These are thin adapters over :mod:`app.services.onboarding`'s bounded
repository tool execution: no new file-system access is introduced here, this
module only exposes ``read_file``/``glob``/``grep`` through the shared tool
framework (registry + executor) so the Groq agent loop can call them like any
other registered tool. The onboarding module still owns every path-safety
check; broadening that behavior is explicitly out of scope.
"""

from __future__ import annotations

from typing import Any

from app.models import OnboardingRecord, RepositoryToolInvocation
from app.services.onboarding import (
    OnboardingError,
    OnboardingNotFoundError,
    execute_repository_tool,
    repository_tool_definitions,
)
from app.tools.context import ToolContext, ToolExecutionError

ONBOARDING_RECORD_RESOURCE = "onboarding_record"


async def _run(tool_name: str, arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    record = ctx.resource(ONBOARDING_RECORD_RESOURCE)
    if not isinstance(record, OnboardingRecord):
        raise ToolExecutionError("no onboarded repository is bound to this job")
    try:
        response = execute_repository_tool(record, RepositoryToolInvocation(tool=tool_name, arguments=arguments))
    except (OnboardingError, OnboardingNotFoundError) as error:
        raise ToolExecutionError(str(error)) from error
    return response.result.model_dump()


async def read_file(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    return await _run("read_file", arguments, ctx)


async def glob(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    return await _run("glob", arguments, ctx)


async def grep(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    return await _run("grep", arguments, ctx)


def repo_tool_schemas() -> dict[str, dict[str, Any]]:
    """Return each repo tool's JSON schema, sourced from the onboarding definitions."""
    return {definition.name: definition.input_schema for definition in repository_tool_definitions()}
