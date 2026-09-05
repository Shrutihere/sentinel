"""The decision pipeline — a chain of stages.

Each stage inspects the ActionContext and either returns a DecisionResult
(short-circuiting the chain) or returns None to defer to the next stage. If no
stage objects, the action is allowed by default.

This is the extensibility seam of the whole project:
  - M0: no stages           -> everything passes through (allow)
  - M1: + PolicyStage       -> deterministic allow/deny/require-approval rules
  - M2: + RiskStage         -> hybrid guardrails + Claude contextual risk scorer

Ordering matters: cheap/deterministic stages run first so we never pay for an
LLM call on an action policy already settles.
"""

from .schemas import ActionContext, Decision, DecisionResult


class Stage:
    """Base class for a decision stage."""

    name: str = "stage"

    def evaluate(self, ctx: ActionContext) -> DecisionResult | None:
        raise NotImplementedError


class DecisionPipeline:
    def __init__(self, stages: list[Stage] | None = None) -> None:
        self.stages = stages or []

    def decide(self, ctx: ActionContext) -> DecisionResult:
        for stage in self.stages:
            result = stage.evaluate(ctx)
            if result is not None:
                return result
        # No stage objected — default allow (M0 behaviour).
        return DecisionResult(
            decision=Decision.ALLOW,
            stage="passthrough",
            reasons=["No stage objected (M0 pass-through)"],
        )


def build_pipeline() -> DecisionPipeline:
    """Assemble the active pipeline. Stages get appended here as milestones land."""
    return DecisionPipeline(stages=[])
