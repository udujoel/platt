from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from app.background_tasks import create_background_task
from app.event_bus import event_bus
from app.jobs import stream_chat_job
from app.llm import create_llm_from_environment
from app.models import (
    AuditEntryEvent,
    ChatRequest,
    ChatResponse,
    JobCreatedEvent,
    OnboardingRecord,
    OnboardingRequest,
    PlanReadyEvent,
    RepositoryInspectionPlanResponse,
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
    onboarding_system_prompt,
    repository_inspection_plan,
    repository_tool_result_summary,
    repository_tool_definitions,
    trace_module,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
REPOSITORY_REVIEW_PLAN_PROMPT = "Prepare a read-only repository review plan."


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


@router.post("/{onboarding_id}/chat", response_model=ChatResponse, status_code=status.HTTP_202_ACCEPTED)
async def chat_about_onboarded_repository(
    request: Request,
    onboarding_id: UUID,
    chat_request: ChatRequest,
) -> ChatResponse:
    try:
        record = _store(request).get(onboarding_id)
    except OnboardingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record not found") from error
    job_id = uuid4()
    persistence = _persistence(request)
    persistence.record_job(job_id=job_id, prompt=chat_request.prompt)
    persistence.record_audit_entry(job_id=job_id, tool="onboarding_chat", action="create_job", outcome="accepted")
    await event_bus.publish(JobCreatedEvent(job_id=job_id, prompt=chat_request.prompt))
    create_background_task(
        request.app,
        stream_chat_job(
            job_id=job_id,
            bus=event_bus,
            llm=create_llm_from_environment(),
            prompt=chat_request.prompt,
            system_prompt=onboarding_system_prompt(record),
        ),
    )
    return ChatResponse(job_id=job_id)


@router.post(
    "/{onboarding_id}/plans/repository-review",
    response_model=RepositoryInspectionPlanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def prepare_repository_review_plan(request: Request, onboarding_id: UUID) -> RepositoryInspectionPlanResponse:
    """Persist an inspectable, read-only review plan without invoking repository tools."""
    try:
        record = _store(request).get(onboarding_id)
    except OnboardingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record not found") from error
    plan = repository_inspection_plan(record)
    job_id = uuid4()
    persistence = _persistence(request)
    persistence.record_job(job_id=job_id, prompt=REPOSITORY_REVIEW_PLAN_PROMPT, onboarding_id=record.id)
    persistence.record_audit_entry(job_id=job_id, tool="onboarding_plan", action="create_plan", outcome="accepted")
    await event_bus.publish(JobCreatedEvent(job_id=job_id, prompt=REPOSITORY_REVIEW_PLAN_PROMPT))
    await event_bus.publish(PlanReadyEvent(job_id=job_id, summary=plan.summary))
    return RepositoryInspectionPlanResponse(job_id=job_id, plan=plan)


@router.post(
    "/{onboarding_id}/plans/repository-review/{job_id}/steps/{step_id}",
    response_model=RepositoryToolResponse,
)
async def execute_repository_review_plan_step(
    request: Request,
    onboarding_id: UUID,
    job_id: UUID,
    step_id: str,
) -> RepositoryToolResponse:
    """Execute one explicit, pre-planned read-only tool step and audit its outcome."""
    try:
        record = _store(request).get(onboarding_id)
    except OnboardingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record not found") from error
    persistence = _persistence(request)
    job = persistence.get_job(job_id)
    if (
        job is None
        or job["prompt"] != REPOSITORY_REVIEW_PLAN_PROMPT
        or job["onboarding_id"] != str(record.id)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="repository review plan job not found")
    step = next((candidate for candidate in repository_inspection_plan(record).steps if candidate.id == step_id), None)
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="repository review plan step not found")
    audit_tool = f"repo.{step.tool}"
    try:
        result = execute_repository_tool(
            record,
            RepositoryToolInvocation(tool=step.tool, arguments=step.arguments),
        )
    except OnboardingNotFoundError as error:
        persistence.record_audit_entry(job_id, tool=audit_tool, action="execute_plan_step", outcome="not_found")
        await event_bus.publish(AuditEntryEvent(job_id=job_id, tool=audit_tool, action="execute_plan_step", outcome="not_found"))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="repository review inventory path not found") from error
    except OnboardingError as error:
        persistence.record_audit_entry(job_id, tool=audit_tool, action="execute_plan_step", outcome="rejected")
        await event_bus.publish(AuditEntryEvent(job_id=job_id, tool=audit_tool, action="execute_plan_step", outcome="rejected"))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    persistence.record_audit_entry(job_id, tool=audit_tool, action="execute_plan_step", outcome="succeeded")
    await event_bus.publish(
        AuditEntryEvent(
            job_id=job_id,
            tool=audit_tool,
            action="execute_plan_step",
            outcome="succeeded",
            step_id=step.id,
            summary=repository_tool_result_summary(result),
        )
    )
    return result


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
    invocation: dict[str, object],
) -> RepositoryToolResponse:
    persistence = _persistence(request)
    requested_tool = invocation.get("tool")
    audit_tool = requested_tool if isinstance(requested_tool, str) and len(requested_tool) <= 64 else "unknown"
    try:
        parsed_invocation = RepositoryToolInvocation.model_validate(invocation)
    except ValidationError as error:
        persistence.record_audit_entry(None, tool=f"repo.{audit_tool}", action="execute", outcome="rejected")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.errors()) from error
    try:
        result = execute_repository_tool(_store(request).get(onboarding_id), parsed_invocation)
    except OnboardingNotFoundError as error:
        persistence.record_audit_entry(None, tool=f"repo.{parsed_invocation.tool}", action="execute", outcome="not_found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record or inventory path not found") from error
    except OnboardingError as error:
        persistence.record_audit_entry(None, tool=f"repo.{parsed_invocation.tool}", action="execute", outcome="rejected")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    persistence.record_audit_entry(None, tool=f"repo.{parsed_invocation.tool}", action="execute", outcome="succeeded")
    return result
