"""ORM models. For M0 this is just the append-only audit log.

Every action that flows through Sentinel — allowed, denied, or escalated —
lands here. This is the accountability boundary: a complete, queryable trail of
autonomous actions and the decision Sentinel made about each one.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
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
