"""M1 tests — the deterministic policy stage.

We test PolicyStage directly against a small in-test policy (no reliance on the
repo's policy.yaml), so the rules under test are explicit and stable.
"""

import pytest

from sentinel.policy import Policy, PolicyStage
from sentinel.schemas import ActionContext, Decision, Target

POLICY = Policy.model_validate(
    {
        "roles": {
            "deployer": {"allowed_tools": ["shell.exec", "git.*", "db.query"]},
            "analyst": {"allowed_tools": ["db.query"]},
        },
        "rules": [
            {"name": "deny-secrets", "match": {"system": "secrets"}, "effect": "deny",
             "reason": "no secrets"},
            {"name": "deny-prod-drop", "match": {"tool": "db.*", "env": "prod",
             "action_matches": r"(?i)\b(drop|truncate)\b"}, "effect": "deny",
             "reason": "no prod drop"},
            {"name": "approve-prod-write", "match": {"tool": "db.*", "env": "prod",
             "action_matches": r"(?i)\b(delete|update|insert)\b"},
             "effect": "require_approval", "reason": "prod write"},
            {"name": "approve-force-push", "match":
             {"action_matches": r"(?i)git\s+push\b.*(--force|-f)\b.*\b(main|master)\b"},
             "effect": "require_approval", "reason": "force push"},
            {"name": "allow-select", "match": {"tool": "db.query",
             "action_matches": r"(?i)^\s*select\b"}, "effect": "allow",
             "reason": "read only"},
        ],
    }
)
stage = PolicyStage(policy=POLICY)


def _ctx(**kw) -> ActionContext:
    base = {"agent_id": "a", "tool": "shell.exec", "action": "noop"}
    tgt = kw.pop("target", None)
    base.update(kw)
    if tgt:
        base["target"] = Target(**tgt)
    return ActionContext(**base)


def test_rbac_denies_tool_outside_role():
    r = stage.evaluate(_ctx(role="analyst", tool="shell.exec", action="rm -rf /"))
    assert r is not None and r.decision is Decision.DENY
    assert r.stage == "policy:rbac"


def test_rbac_denies_unknown_role():
    r = stage.evaluate(_ctx(role="ghost", tool="db.query", action="select 1"))
    assert r is not None and r.decision is Decision.DENY


def test_rbac_allows_tool_within_role_then_defers():
    # deployer may use shell.exec; no rule matches "echo hi" -> defer (None)
    r = stage.evaluate(_ctx(role="deployer", tool="shell.exec", action="echo hi"))
    assert r is None


def test_deny_secrets_access():
    r = stage.evaluate(_ctx(tool="http.get", action="read token",
                            target={"system": "secrets", "env": "prod"}))
    assert r is not None and r.decision is Decision.DENY
    assert "deny-secrets" in r.stage


def test_deny_beats_approval_for_prod_drop():
    # DROP must hit the deny rule (ordered first), not the write-approval rule.
    r = stage.evaluate(_ctx(tool="db.query", action="DROP TABLE users",
                            target={"system": "postgres", "env": "prod"}))
    assert r is not None and r.decision is Decision.DENY


def test_prod_write_requires_approval():
    r = stage.evaluate(_ctx(tool="db.query", action="DELETE FROM sessions WHERE id=1",
                            target={"system": "postgres", "env": "prod"}))
    assert r is not None and r.decision is Decision.REQUIRE_APPROVAL


def test_force_push_requires_approval():
    r = stage.evaluate(_ctx(tool="shell.exec", action="git push --force origin main",
                            target={"system": "github", "env": "prod"}))
    assert r is not None and r.decision is Decision.REQUIRE_APPROVAL


def test_readonly_select_allowed():
    r = stage.evaluate(_ctx(tool="db.query", action="SELECT * FROM orders",
                            target={"system": "postgres", "env": "prod"}))
    assert r is not None and r.decision is Decision.ALLOW


def test_no_role_skips_rbac_but_rules_still_apply():
    # No role provided: RBAC skipped, but the DROP deny rule still fires.
    r = stage.evaluate(_ctx(tool="db.query", action="TRUNCATE users",
                            target={"system": "postgres", "env": "prod"}))
    assert r is not None and r.decision is Decision.DENY
