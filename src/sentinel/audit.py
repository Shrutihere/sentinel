"""Audit store — append-only writes and read queries over the audit log."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditLog
from .schemas import ActionContext, DecisionResult


def record(
    session: Session,
    ctx: ActionContext,
    result: DecisionResult,
    executed: bool,
) -> AuditLog:
    """Persist one decision. Append-only: we never update or delete rows."""
    entry = AuditLog(
        agent_id=ctx.agent_id,
        role=ctx.role,
        tool=ctx.tool,
        action=ctx.action,
        args=ctx.args,
        target=ctx.target.model_dump(),
        decision=result.decision.value,
        stage=result.stage,
        reasons=result.reasons,
        executed=executed,
        severity=result.severity,
        score=result.score,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def list_recent(session: Session, limit: int = 50) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    return list(session.scalars(stmt).all())
