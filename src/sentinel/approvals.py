"""M3 — approval service: park high-risk actions, then approve/deny them.

The ApprovalRequest row is the durable source of truth. On approval we execute
the snapshotted action (a mock in this MVP) and write a second audit row, so the
trail shows both "escalated" and "approved by <human> then executed".
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ApprovalRequest
from .schemas import (
    ActionContext,
    ApprovalStatus,
    ApprovalView,
    DecisionResult,
    Decision,
    Target,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_pending(
    session: Session,
    ctx: ActionContext,
    result: DecisionResult,
    request_audit_id: int | None,
) -> ApprovalRequest:
    ar = ApprovalRequest(
        status=ApprovalStatus.PENDING.value,
        agent_id=ctx.agent_id,
        role=ctx.role,
        tool=ctx.tool,
        action=ctx.action,
        args=ctx.args,
        target=ctx.target.model_dump(),
        severity=result.severity,
        score=result.score,
        reasons=result.reasons,
        request_audit_id=request_audit_id,
    )
    session.add(ar)
    session.commit()
    session.refresh(ar)
    return ar


def get(session: Session, approval_id: int) -> ApprovalRequest | None:
    return session.get(ApprovalRequest, approval_id)


def list_requests(
    session: Session, status: str | None = None, limit: int = 50
) -> list[ApprovalRequest]:
    stmt = select(ApprovalRequest)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    stmt = stmt.order_by(ApprovalRequest.id.desc()).limit(limit)
    return list(session.scalars(stmt).all())


def to_context(ar: ApprovalRequest) -> ActionContext:
    """Rebuild the ActionContext from a parked request (for audit/execution)."""
    return ActionContext(
        agent_id=ar.agent_id,
        role=ar.role,
        tool=ar.tool,
        action=ar.action,
        args=ar.args,
        target=Target(**ar.target),
    )


def resolve(
    session: Session,
    ar: ApprovalRequest,
    *,
    approved: bool,
    decided_by: str,
    note: str | None,
) -> ApprovalRequest:
    ar.status = (ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED).value
    ar.decided_at = _utcnow()
    ar.decided_by = decided_by
    ar.note = note
    ar.executed = approved  # MVP: approval executes the (mock) action
    session.commit()
    session.refresh(ar)
    return ar


def audit_result_for(ar: ApprovalRequest, approved: bool) -> DecisionResult:
    """The DecisionResult to log for the human's approve/deny action."""
    verb = "approved" if approved else "denied"
    reasons = [f"{verb.capitalize()} by {ar.decided_by} after risk review"]
    if ar.note:
        reasons.append(f"note: {ar.note}")
    return DecisionResult(
        decision=Decision.ALLOW if approved else Decision.DENY,
        stage=f"approval:{verb}:{ar.decided_by}",
        reasons=reasons,
        severity=ar.severity,
        score=ar.score,
    )


def to_view(ar: ApprovalRequest) -> ApprovalView:
    return ApprovalView(
        id=ar.id,
        created_at=ar.created_at.isoformat(),
        status=ApprovalStatus(ar.status),
        agent_id=ar.agent_id,
        role=ar.role,
        tool=ar.tool,
        action=ar.action,
        target=ar.target,
        severity=ar.severity,
        score=ar.score,
        reasons=ar.reasons,
        decided_at=ar.decided_at.isoformat() if ar.decided_at else None,
        decided_by=ar.decided_by,
        note=ar.note,
        executed=ar.executed,
    )
