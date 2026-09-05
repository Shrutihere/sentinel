"""The gateway — the single choke point every agent tool-call flows through.

An agent asks Sentinel "may I run this action?" The gateway runs the decision
pipeline, records the outcome in the audit log, and (in M0) executes a mock tool
when the action is allowed. Real/sandboxed execution arrives in later milestones.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from . import audit
from .db import get_session
from .pipeline import build_pipeline
from .schemas import ActionContext, AuditEntry, Decision, ToolCallResponse

router = APIRouter()
pipeline = build_pipeline()


@router.post("/v1/tool-call", response_model=ToolCallResponse)
def tool_call(
    ctx: ActionContext,
    session: Session = Depends(get_session),
) -> ToolCallResponse:
    result = pipeline.decide(ctx)

    # M0: if allowed, we "execute" (a mock — real sandboxed execution comes later).
    executed = result.decision == Decision.ALLOW

    entry = audit.record(session, ctx, result, executed=executed)

    return ToolCallResponse(
        decision=result.decision,
        stage=result.stage,
        reasons=result.reasons,
        audit_id=entry.id,
        executed=executed,
        severity=result.severity,
        score=result.score,
    )


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
