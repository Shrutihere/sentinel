"""M1 — the policy stage: deterministic, declarative governance.

Loads rules from a YAML file (no code deploy needed to change policy) and applies
them as the first pipeline stage. Two responsibilities:

  1. RBAC   — is this agent's role permitted to use this tool at all?
  2. Rules  — does the action match a rule we've already decided?

If neither settles the action, the stage returns None and defers to the next
stage (the risk engine in M2). This is the deterministic, high-precision floor
that runs before we ever pay for an LLM call.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .config import settings
from .pipeline import Stage
from .schemas import ActionContext, Decision, DecisionResult


class RoleConfig(BaseModel):
    allowed_tools: list[str] = Field(default_factory=list)


class Match(BaseModel):
    tool: str | None = None
    system: str | None = None
    env: str | None = None
    action_matches: str | None = None


class Rule(BaseModel):
    name: str
    match: Match = Field(default_factory=Match)
    effect: Decision
    reason: str = ""


class Policy(BaseModel):
    roles: dict[str, RoleConfig] = Field(default_factory=dict)
    rules: list[Rule] = Field(default_factory=list)


def load_policy(path: str | None = None) -> Policy:
    """Load policy from YAML. Missing file → empty policy (defers everything)."""
    p = Path(path or settings.policy_path)
    if not p.exists():
        return Policy()
    data = yaml.safe_load(p.read_text()) or {}
    return Policy(**data)


def _matches(m: Match, ctx: ActionContext) -> bool:
    """Every field present in the match must hold (logical AND)."""
    if m.tool and not fnmatch.fnmatch(ctx.tool, m.tool):
        return False
    if m.system and (ctx.target.system or "").lower() != m.system.lower():
        return False
    if m.env and (ctx.target.env or "").lower() != m.env.lower():
        return False
    if m.action_matches and not re.search(m.action_matches, ctx.action):
        return False
    return True


class PolicyStage(Stage):
    name = "policy"

    def __init__(self, policy: Policy | None = None) -> None:
        self.policy = policy if policy is not None else load_policy()

    def evaluate(self, ctx: ActionContext) -> DecisionResult | None:
        # 1) RBAC — enforced only when the caller declares a role we know.
        if ctx.role:
            role_cfg = self.policy.roles.get(ctx.role)
            if role_cfg is None:
                return DecisionResult(
                    decision=Decision.DENY,
                    stage="policy:rbac",
                    reasons=[f"Unknown role '{ctx.role}' — denied by default"],
                )
            if role_cfg.allowed_tools and not any(
                fnmatch.fnmatch(ctx.tool, pat) for pat in role_cfg.allowed_tools
            ):
                return DecisionResult(
                    decision=Decision.DENY,
                    stage="policy:rbac",
                    reasons=[
                        f"Role '{ctx.role}' is not permitted to use tool '{ctx.tool}'"
                    ],
                )

        # 2) Rules — first match wins.
        for rule in self.policy.rules:
            if _matches(rule.match, ctx):
                return DecisionResult(
                    decision=rule.effect,
                    stage=f"policy:{rule.name}",
                    reasons=[rule.reason or rule.name],
                )

        # 3) No opinion — defer to the next stage (risk engine, M2).
        return None
