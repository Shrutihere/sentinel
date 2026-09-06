"""The gateway — the single choke point every agent tool-call flows through.

An agent asks Sentinel "may I run this action?" The gateway runs the decision
pipeline, records the outcome in the audit log, and (in M0) executes a mock tool
when the action is allowed. Real/sandboxed execution arrives in later milestones.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import approvals, audit, notify
from .config import settings
from .db import get_session
from .pipeline import build_pipeline
from .schemas import (
    ActionContext,
    ApprovalDecisionRequest,
    ApprovalStatus,
    ApprovalView,
    AuditEntry,
    Decision,
    ToolCallResponse,
)

router = APIRouter()
pipeline = build_pipeline()


@router.post("/v1/tool-call", response_model=ToolCallResponse)
def tool_call(
    ctx: ActionContext,
    session: Session = Depends(get_session),
) -> ToolCallResponse:
    result = pipeline.decide(ctx)

    # Only ALLOW executes immediately (mock). DENY is dropped; REQUIRE_APPROVAL
    # is parked for a human and executes later, on approval.
    executed = result.decision == Decision.ALLOW
    entry = audit.record(session, ctx, result, executed=executed)

    approval_id: int | None = None
    if result.decision == Decision.ALLOW:
        status = "executed"
    elif result.decision == Decision.DENY:
        status = "denied"
    else:  # REQUIRE_APPROVAL — park it and notify a human
        ar = approvals.create_pending(session, ctx, result, entry.id)
        approval_id = ar.id
        notify.notify_pending(ar)
        status = "pending_approval"

    return ToolCallResponse(
        decision=result.decision,
        stage=result.stage,
        reasons=result.reasons,
        audit_id=entry.id,
        executed=executed,
        severity=result.severity,
        score=result.score,
        status=status,
        approval_id=approval_id,
    )


# --------------------------------------------------------------------------- #
# M3 — human-in-the-loop approval endpoints
# --------------------------------------------------------------------------- #
@router.get("/v1/approvals", response_model=list[ApprovalView])
def list_approvals(
    status: str | None = None,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[ApprovalView]:
    return [approvals.to_view(a) for a in approvals.list_requests(session, status, limit)]


@router.get("/v1/approvals/{approval_id}", response_model=ApprovalView)
def get_approval(
    approval_id: int,
    session: Session = Depends(get_session),
) -> ApprovalView:
    ar = approvals.get(session, approval_id)
    if ar is None:
        raise HTTPException(status_code=404, detail="approval not found")
    return approvals.to_view(ar)


def _decide(
    approval_id: int,
    body: ApprovalDecisionRequest,
    approved: bool,
    session: Session,
) -> ApprovalView:
    ar = approvals.get(session, approval_id)
    if ar is None:
        raise HTTPException(status_code=404, detail="approval not found")
    if ar.status != ApprovalStatus.PENDING.value:
        raise HTTPException(
            status_code=409, detail=f"approval already {ar.status}"
        )  # idempotent: never double-decide/execute

    ar = approvals.resolve(
        session, ar, approved=approved, decided_by=body.decided_by, note=body.note
    )
    # Record the human's decision (and the resulting mock execution) in the trail.
    ctx = approvals.to_context(ar)
    result = approvals.audit_result_for(ar, approved)
    audit.record(session, ctx, result, executed=ar.executed)
    return approvals.to_view(ar)


@router.post("/v1/approvals/{approval_id}/approve", response_model=ApprovalView)
def approve(
    approval_id: int,
    body: ApprovalDecisionRequest,
    session: Session = Depends(get_session),
) -> ApprovalView:
    return _decide(approval_id, body, approved=True, session=session)


@router.post("/v1/approvals/{approval_id}/deny", response_model=ApprovalView)
def deny(
    approval_id: int,
    body: ApprovalDecisionRequest,
    session: Session = Depends(get_session),
) -> ApprovalView:
    return _decide(approval_id, body, approved=False, session=session)


# --------------------------------------------------------------------------- #
# M5 — serve the latest evaluation results to the dashboard
# --------------------------------------------------------------------------- #
@router.get("/v1/eval/results")
def eval_results() -> dict:
    p = Path(settings.eval_results_path)
    if not p.exists():
        raise HTTPException(
            status_code=404,
            detail="no eval results yet — run: python -m sentinel.evaluate",
        )
    return json.loads(p.read_text())


@router.get("/v1/audit", response_model=list[AuditEntry])
def get_audit(
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[AuditEntry]:
    entries = audit.list_recent(session, limit=limit)
    return [
        AuditEntry(
            id=e.id,
            created_at=e.created_at.isoformat(),
            agent_id=e.agent_id,
            role=e.role,
            tool=e.tool,
            action=e.action,
            target=e.target,
            decision=Decision(e.decision),
            stage=e.stage,
            reasons=e.reasons,
            executed=e.executed,
            severity=e.severity,
            score=e.score,
        )
        for e in entries
    ]
