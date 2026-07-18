import sqlite3

from fastapi import APIRouter, HTTPException, Request, status

from app.models import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process liveness without checking a downstream dependency."""

    return HealthResponse()


@router.get("/ready", response_model=ReadinessResponse)
def readiness(request: Request) -> ReadinessResponse:
    """Report readiness after a threadpool-executed persistence read."""

    try:
        request.app.state.persistence.check_ready()
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Persistence is unavailable",
        ) from error
    return ReadinessResponse()
