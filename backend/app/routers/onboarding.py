from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from app.models import OnboardingRecord, OnboardingRequest
from app.services.onboarding import OnboardingError, OnboardingNotFoundError, OnboardingStore, inspect_repository

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _store(request: Request) -> OnboardingStore:
    return request.app.state.onboarding_store


@router.post("", response_model=OnboardingRecord, status_code=status.HTTP_201_CREATED)
async def onboard_repository(request: Request, payload: OnboardingRequest) -> OnboardingRecord:
    """Index a pre-existing local repository; this endpoint makes no network calls."""
    try:
        record = inspect_repository(payload.repository_path)
    except OnboardingError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _store(request).save(record)


@router.get("/{onboarding_id}", response_model=OnboardingRecord)
async def get_onboarding_record(request: Request, onboarding_id: UUID) -> OnboardingRecord:
    try:
        return _store(request).get(onboarding_id)
    except OnboardingNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="onboarding record not found") from error
