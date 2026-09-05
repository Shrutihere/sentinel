"""ORM models. For M0 this is just the append-only audit log.

Every action that flows through Sentinel — allowed, denied, or escalated —
lands here. This is the accountability boundary: a complete, queryable trail of
autonomous actions and the decision Sentinel made about each one.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    # Who + what (mirrors ActionContext)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(2048))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    target: Mapped[dict] = mapped_column(JSON, default=dict)

    # The decision Sentinel reached
    decision: Mapped[str] = mapped_column(String(32), index=True)
    stage: Mapped[str] = mapped_column(String(48))
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    # Risk-engine output (M2); null when a deterministic stage decided.
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)


class ApprovalRequest(Base):
    """A high-risk action parked for human review (M3).

    Durable source of truth for the human-in-the-loop workflow: it snapshots the
    full action so it can be executed verbatim on approval, and records who
    decided and when.
    """

    __tablename__ = "approval_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)

    # Snapshot of the action (so we can execute it verbatim once approved)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(2048))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    target: Mapped[dict] = mapped_column(JSON, default=dict)

    # Why it needs approval
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    request_audit_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Resolution
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
