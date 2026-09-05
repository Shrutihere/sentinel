"""M2 tests — guardrails, severity→decision mapping, fail-closed, anti-injection.

Uses the Mock provider (no network) plus a stub that lets us assert the
short-circuit and fail-safe behaviour deterministically.
"""

from sentinel.risk import (
    MockProvider,
    RiskAssessment,
    RiskDimensions,
    RiskStage,
    Severity,
    guardrail_scan,
    severity_to_decision,
)
from sentinel.schemas import ActionContext, Decision, Target


def _ctx(action: str, **kw) -> ActionContext:
    tgt = kw.pop("target", {})
    return ActionContext(agent_id="a", tool=kw.pop("tool", "shell.exec"),
                         action=action, target=Target(**tgt), **kw)


# ---- Guardrails (deterministic) ----
def test_guardrail_catches_rm_rf():
    a = guardrail_scan(_ctx("rm -rf /var/data"))
    assert a is not None and a.severity is Severity.CRITICAL and a.source == "guardrail"


def test_guardrail_catches_unbounded_delete():
    a = guardrail_scan(_ctx("DELETE FROM users"))
    assert a is not None and a.severity is Severity.HIGH


def test_guardrail_ignores_bounded_delete():
    # Has a WHERE clause -> guardrail stays silent, defers to the LLM.
    assert guardrail_scan(_ctx("DELETE FROM users WHERE id = 5")) is None


def test_guardrail_catches_force_push():
    a = guardrail_scan(_ctx("git push --force origin main"))
    assert a is not None and a.severity is Severity.HIGH


def test_guardrail_silent_on_safe_action():
    assert guardrail_scan(_ctx("ls -la")) is None


# ---- Severity -> decision mapping ----
def test_mapping_critical_denies():
    from sentinel.risk import RiskAssessment, RiskDimensions
    a = RiskAssessment(severity=Severity.CRITICAL, score=0.97, dimensions=RiskDimensions())
    assert severity_to_decision(a) is Decision.DENY


def test_mapping_high_requires_approval():
    from sentinel.risk import RiskAssessment, RiskDimensions
    a = RiskAssessment(severity=Severity.HIGH, score=0.8, dimensions=RiskDimensions())
    assert severity_to_decision(a) is Decision.REQUIRE_APPROVAL


def test_mapping_medium_irreversible_requires_approval():
    from sentinel.risk import RiskAssessment, RiskDimensions
    a = RiskAssessment(severity=Severity.MEDIUM, score=0.5,
                       dimensions=RiskDimensions(reversibility="irreversible"))
    assert severity_to_decision(a) is Decision.REQUIRE_APPROVAL


def test_mapping_medium_reversible_allows():
    from sentinel.risk import RiskAssessment, RiskDimensions
    a = RiskAssessment(severity=Severity.MEDIUM, score=0.5,
                       dimensions=RiskDimensions(reversibility="reversible"))
    assert severity_to_decision(a) is Decision.ALLOW


# ---- The stage end-to-end ----
def test_stage_short_circuits_on_guardrail_without_calling_llm():
    class ExplodingProvider:
        source = "boom"
        def score(self, ctx):
            raise AssertionError("LLM must not be called when a guardrail fires")

    stage = RiskStage(provider=ExplodingProvider())
    r = stage.evaluate(_ctx("DROP DATABASE prod"))
    assert r.decision is Decision.DENY
    assert r.stage == "risk:guardrail"


def test_stage_fails_closed_on_provider_error():
    class BrokenProvider:
        source = "broken"
        def score(self, ctx):
            raise RuntimeError("api down")

    stage = RiskStage(provider=BrokenProvider())
    r = stage.evaluate(_ctx("send marketing email to all users"))
    assert r.decision is Decision.REQUIRE_APPROVAL   # fail-closed, not allow
    assert r.stage == "risk:error"


def test_stage_uses_mock_provider_for_ambiguous_action():
    stage = RiskStage(provider=MockProvider())
    # prod state-change -> mock rates HIGH -> approval
    r = stage.evaluate(_ctx("restart the payments service",
                            tool="ci.deploy", target={"env": "prod"}))
    assert r.decision is Decision.REQUIRE_APPROVAL
    assert r.severity in ("high", "medium")
