"""Structural approval gate: apply must be impossible without a matching, durable record.

Approval is never inferred from chat text or agent judgment. A record is only usable
by ``require_approval`` when it is decided ``approved``, still unexpired, unconsumed,
and bound to the *exact* ``job_id``/``plan_hash``/``commit_sha`` triple presented at
apply time. ``consume_approval`` then flips it to spent exactly once via an atomic
conditional update (see ``Persistence.consume_approval``), so two concurrent apply
attempts can never both proceed on the same approval.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.persistence import Persistence

DEFAULT_APPROVAL_TTL_SECONDS = 900
MAX_BLAST_RADIUS_DESTROYS = 3


class ApprovalError(Exception):
    """Base class for every reason the approval gate can refuse to authorize an apply."""


class ApprovalNotFoundError(ApprovalError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ApprovalNotDecidedError(ApprovalError):
    def __init__(self, approval_id: str, status: str) -> None:
        super().__init__(f"approval {approval_id} is not approved (status={status})")


class ApprovalExpiredError(ApprovalError):
    def __init__(self, approval_id: str) -> None:
        super().__init__(f"approval {approval_id} has expired")


class ApprovalAlreadyConsumedError(ApprovalError):
    def __init__(self, approval_id: str) -> None:
        super().__init__(f"approval {approval_id} has already been consumed")


class ApprovalAlreadyDecidedError(ApprovalError):
    def __init__(self, approval_id: str, status: str) -> None:
        super().__init__(f"approval {approval_id} was already decided (status={status})")


class BlastRadiusError(ApprovalError):
    pass


@dataclass(frozen=True)
class ApprovalRecord:
    id: str
    job_id: str
    plan_hash: str
    commit_sha: str
    scope: str | None
    approver: str | None
    status: str
    created_at: Any
    decided_at: Any
    expires_at: Any
    consumed_at: Any

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ApprovalRecord":
        return cls(
            id=row["id"],
            job_id=row["job_id"],
            plan_hash=row["plan_hash"],
            commit_sha=row["commit_sha"],
            scope=row["scope"],
            approver=row["approver"],
            status=row["status"],
            created_at=row["created_at"],
            decided_at=row["decided_at"],
            expires_at=row["expires_at"],
            consumed_at=row["consumed_at"],
        )


def _now() -> datetime:
    return datetime.utcnow()


def require_approval(
    persistence: Persistence, job_id: UUID, plan_hash: str, commit_sha: str
) -> ApprovalRecord:
    """Return the approval authorizing this exact apply, or raise.

    The match is exact: a different plan hash or commit on the same job (a stale plan
    re-run, a rebased branch) never satisfies an approval minted for a prior plan.
    """
    row = persistence.find_matching_approval(job_id, plan_hash, commit_sha)
    if row is None:
        raise ApprovalNotFoundError(
            f"no approval found for job={job_id} plan_hash={plan_hash} commit_sha={commit_sha}"
        )
    if row["status"] != "approved":
        raise ApprovalNotDecidedError(row["id"], row["status"])
    if row["consumed_at"] is not None:
        raise ApprovalAlreadyConsumedError(row["id"])
    expires_at = row["expires_at"]
    if expires_at is not None and _coerce_datetime(expires_at) <= _now():
        raise ApprovalExpiredError(row["id"])
    return ApprovalRecord.from_row(row)


def consume_approval(persistence: Persistence, approval_id: UUID) -> None:
    """Mark an approval spent, one time only. Raises if it cannot be consumed."""
    rows_affected = persistence.consume_approval(approval_id)
    if rows_affected == 0:
        row = persistence.get_approval(approval_id)
        if row is None:
            raise ApprovalNotFoundError(f"no approval found with id={approval_id}")
        if row["consumed_at"] is not None:
            raise ApprovalAlreadyConsumedError(str(approval_id))
        if row["status"] != "approved":
            raise ApprovalNotDecidedError(str(approval_id), row["status"])
        raise ApprovalExpiredError(str(approval_id))


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def check_blast_radius(plan_json: dict[str, Any], sandbox_rg: str) -> None:
    """Block an apply whose Terraform plan reaches outside the sandbox or destroys too much.

    ``plan_json`` is a Terraform ``show -json`` plan document: resource changes carry
    an ``address`` and a ``change.actions`` list (e.g. ``["delete"]``, ``["create"]``).
    Any address that doesn't reference the sandbox resource group is out of bounds,
    and more than ``MAX_BLAST_RADIUS_DESTROYS`` destroys is refused outright even
    when every address is in-sandbox.
    """
    resource_changes = plan_json.get("resource_changes", [])
    destroy_count = 0
    for change in resource_changes:
        address = change.get("address", "")
        if sandbox_rg not in address:
            raise BlastRadiusError(
                f"resource '{address}' is outside the sandbox resource group '{sandbox_rg}'"
            )
        actions = change.get("change", {}).get("actions", [])
        if "delete" in actions:
            destroy_count += 1
    if destroy_count > MAX_BLAST_RADIUS_DESTROYS:
        raise BlastRadiusError(
            f"plan destroys {destroy_count} resources, exceeding the cap of {MAX_BLAST_RADIUS_DESTROYS}"
        )
