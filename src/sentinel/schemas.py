"""Pydantic schemas — the API/domain contract.

ActionContext is the heart of the system: every pipeline stage reads it, and the
audit log persists it. Keeping it stable across milestones is what lets policy
(M1) and the risk engine (M2) slot in without touching the gateway.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Decision(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class Target(BaseModel):
    """What the action touches."""

    system: str = "unknown"          # e.g. "github", "postgres", "aws"
    resource: str | None = None       # e.g. "repo/main", "table:users"
    env: str = "unknown"              # e.g. "prod", "staging", "dev"


class ActionContext(BaseModel):
    """A single tool-call an agent wants to make."""

    agent_id: str
    role: str | None = None
    tool: str                         # e.g. "shell.exec", "db.query"
    action: str                       # human-readable, e.g. "git push --force origin main"
    args: dict = Field(default_factory=dict)
    target: Target = Field(default_factory=Target)


class DecisionResult(BaseModel):
    """The outcome of the decision pipeline for one action."""

    decision: Decision
    stage: str                        # which stage decided (or "passthrough")
    reasons: list[str] = Field(default_factory=list)
    # Populated by the risk stage (M2); None when a deterministic stage decided.
    severity: str | None = None
    score: float | None = None


class ToolCallResponse(BaseModel):
    """What the gateway returns to the calling agent."""

    decision: Decision
    stage: str
    reasons: list[str]
    audit_id: int
    executed: bool
    severity: str | None = None
    score: float | None = None
    # M3: when decision is require_approval, the id of the parked request.
    status: str = "executed"          # executed | pending_approval | denied
    approval_id: int | None = None


class AuditEntry(BaseModel):
    """Read model for the audit trail."""

    id: int
    created_at: str
    agent_id: str
    role: str | None
    tool: str
    action: str
    target: dict
    decision: Decision
    stage: str
    reasons: list[str]
    executed: bool
    severity: str | None = None
    score: float | None = None


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ApprovalView(BaseModel):
    """Read model for a parked approval request."""

    id: int
    created_at: str
    status: ApprovalStatus
    agent_id: str
    role: str | None
    tool: str
    action: str
    target: dict
    severity: str | None
    score: float | None
    reasons: list[str]
    decided_at: str | None
    decided_by: str | None
    note: str | None
    executed: bool


class ApprovalDecisionRequest(BaseModel):
    """Body for approve/deny — who is deciding, and an optional note."""

    decided_by: str
    note: str | None = None
