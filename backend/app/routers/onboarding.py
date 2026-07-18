from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from app.models import (
    OnboardingRecord,
    OnboardingRequest,
    RepositoryToolDefinition,
    RepositoryToolInvocation,
    RepositoryToolResponse,
    TerraformModuleTrace,
)
from app.persistence import Persistence
from app.services.onboarding import (
    OnboardingError,
    OnboardingNotFoundError,
    OnboardingStore,
    execute_repository_tool,
    inspect_repository,
    repository_tool_definitions,
    trace_module,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _store(request: Request) -> OnboardingStore:
    store = getattr(request.app.state, "onboarding_store", None)
    if not isinstance(store, OnboardingStore):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="onboarding store is unavailable")
    return store


def _persistence(request: Request) -> Persistence:
    persistence = getattr(request.app.state, "persistence", None)
    if not isinstance(persistence, Persistence):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="audit persistence is unavailable")
    return persistence


@router.post("", response_model=OnboardingRecord, status_code=status.HTTP_201_CREATED)
def onboard_repository(request: Request, payload: OnboardingRequest) -> OnboardingRecord:
    """Index a pre-existing local repository; this endpoint makes no network calls."""
    try:
        record = inspect_repository(payload.repository_path)
    except OnboardingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _store(request).save(record)


@router.get("/{onboarding_id}", response_model=OnboardingRecord)
def get_onboarding_record(request: Request, onboarding_id: UUID) -> OnboardingRecord:
    try:
        return _store(request).get(onboarding_id)
    except OnboardingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record not found") from error


@router.get("/{onboarding_id}/module-trace", response_model=TerraformModuleTrace)
def get_module_trace(request: Request, onboarding_id: UUID, module_path: str) -> TerraformModuleTrace:
    try:
        return trace_module(_store(request).get(onboarding_id), module_path)
    except OnboardingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record or module not found") from error


@router.get("/{onboarding_id}/tools", response_model=list[RepositoryToolDefinition])
def list_repository_tools(request: Request, onboarding_id: UUID) -> list[RepositoryToolDefinition]:
    try:
        _store(request).get(onboarding_id)
    except OnboardingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record not found") from error
    return repository_tool_definitions()


@router.post("/{onboarding_id}/tools/invoke", response_model=RepositoryToolResponse)
def invoke_repository_tool(
    request: Request,
    onboarding_id: UUID,
    invocation: RepositoryToolInvocation,
) -> RepositoryToolResponse:
    persistence = _persistence(request)
    try:
        result = execute_repository_tool(_store(request).get(onboarding_id), invocation)
    except OnboardingNotFoundError as error:
        persistence.record_audit_entry(None, tool=f"repo.{invocation.tool}", action="execute", outcome="not_found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record or inventory path not found") from error
    except OnboardingError as error:
        persistence.record_audit_entry(None, tool=f"repo.{invocation.tool}", action="execute", outcome="rejected")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    persistence.record_audit_entry(None, tool=f"repo.{invocation.tool}", action="execute", outcome="succeeded")
    return result
