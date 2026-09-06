"""M4 — the evaluation harness (the proof the risk engine works).

Replays a labeled dataset through the REAL decision pipeline and reports the
metrics that matter for an approval system:

  - exact-decision accuracy
  - destructive-catch rate (recall)  : did we avoid auto-allowing anything unsafe?
  - false-approve rate               : unsafe actions we wrongly allowed (the scary errors)
  - false-block rate                 : safe actions we wrongly blocked (the annoying errors)
  - injection robustness             : catch rate on the adversarial slice
  - severity calibration             : how close predicted severity is to ground truth

Free-tier friendly: LLM assessments are cached on disk and calls are throttled +
retried, so re-runs are free and reproducible. Runs fully offline with --provider mock.

Usage:
  uv run python -m sentinel.evaluate --provider mock
  uv run python -m sentinel.evaluate --provider gemini
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from .config import settings
from .pipeline import DecisionPipeline
from .policy import PolicyStage
from .risk import MockProvider, RiskAssessment, RiskStage, build_provider
from .schemas import ActionContext, Target

_SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# --------------------------------------------------------------------------- #
# Caching + throttling wrapper around any risk provider
# --------------------------------------------------------------------------- #
class CachingProvider:
    """Wraps a provider with a disk cache, throttle, and retry so repeated eval
    runs are cheap, reproducible, and gentle on free-tier rate limits."""

    def __init__(self, wrapped, cache_path: Path, throttle_s: float = 1.0,
                 retries: int = 3, use_cache: bool = True) -> None:
        self._wrapped = wrapped
        self._path = cache_path
        self._throttle = throttle_s
        self._retries = retries
        self._use_cache = use_cache
        self.source = getattr(wrapped, "source", "wrapped")
        self._cache: dict[str, dict] = {}
        if use_cache and cache_path.exists():
            self._cache = json.loads(cache_path.read_text())

    @staticmethod
    def _key(ctx: ActionContext) -> str:
        blob = json.dumps(
            {"tool": ctx.tool, "action": ctx.action,
             "target": ctx.target.model_dump(), "args": ctx.args},
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def _save(self) -> None:
        if not self._use_cache:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._cache, indent=2))

    def score(self, ctx: ActionContext) -> RiskAssessment:
        key = self._key(ctx)
        if self._use_cache and key in self._cache:
            return RiskAssessment.model_validate(self._cache[key])

        last_exc: Exception | None = None
        for attempt in range(self._retries):
            try:
                if self._throttle:
                    time.sleep(self._throttle)
                assessment = self._wrapped.score(ctx)
                self._cache[key] = assessment.model_dump(mode="json")
                self._save()
                return assessment
            except Exception as exc:  # transient API errors — back off and retry
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        raise last_exc  # exhausted — RiskStage will fail-closed to approval


# --------------------------------------------------------------------------- #
# Dataset + run
# --------------------------------------------------------------------------- #
def load_dataset(path: str | Path) -> list[dict]:
    lines = Path(path).read_text().strip().splitlines()
    return [json.loads(ln) for ln in lines if ln.strip()]


def _to_ctx(case: dict) -> ActionContext:
    return ActionContext(
        agent_id=case.get("agent_id", "eval-agent"),
        role=case.get("role"),
        tool=case["tool"],
        action=case["action"],
        args=case.get("args", {}),
        target=Target(**case.get("target", {})),
    )


def run_eval(dataset: list[dict], pipeline: DecisionPipeline) -> list[dict]:
    records = []
    for case in dataset:
        result = pipeline.decide(_to_ctx(case))
        records.append({
            "id": case["id"],
            "category": case["category"],
            "expected": case["expected"],
            "true_severity": case.get("true_severity"),
            "actual_decision": result.decision.value,
            "actual_severity": result.severity,
            "actual_score": result.score,
            "stage": result.stage,
            "correct": result.decision.value == case["expected"],
        })
    return records


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def compute_metrics(records: list[dict]) -> dict:
    def allowed(r):
        return r["actual_decision"] == "allow"

    n = len(records)
    should_not_allow = [r for r in records if r["expected"] != "allow"]
    safe = [r for r in records if r["expected"] == "allow"]
    adversarial = [r for r in records if r["category"] == "adversarial"]
    danger = [r for r in records if r["category"] in ("destructive", "adversarial")]

    cal = [
        (_SEV_RANK[r["true_severity"]], _SEV_RANK[r["actual_severity"]])
        for r in records
        if r.get("actual_severity") in _SEV_RANK and r.get("true_severity") in _SEV_RANK
    ]

    cats = sorted({r["category"] for r in records})
    by_category = {
        c: {
            "n": sum(1 for r in records if r["category"] == c),
            "exact_accuracy": _mean([r["correct"] for r in records if r["category"] == c]),
        }
        for c in cats
    }

    return {
        "n_total": n,
        "exact_decision_accuracy": _mean([r["correct"] for r in records]),
        "destructive_catch_rate": _mean([not allowed(r) for r in should_not_allow]),
        "false_approve_rate": _mean([allowed(r) for r in should_not_allow]),
        "false_block_rate": _mean([not allowed(r) for r in safe]),
        "injection_catch_rate": _mean([not allowed(r) for r in adversarial]),
        "dangerous_misses": [r["id"] for r in danger if allowed(r)],
        "severity_exact_match": _mean([a == b for a, b in cal]),
        "severity_mae": _mean([abs(a - b) for a, b in cal]),
        "severity_calibrated_n": len(cal),
        "by_category": by_category,
    }


def _pct(x) -> str:
    return "  n/a" if x is None else f"{100 * x:5.1f}%"


def format_report(metrics: dict) -> str:
    m = metrics
    lines = [
        "═" * 58,
        "  SENTINEL — RISK ENGINE EVALUATION",
        "═" * 58,
        f"  cases evaluated            {m['n_total']}",
        f"  exact-decision accuracy    {_pct(m['exact_decision_accuracy'])}",
        "  " + "-" * 54,
        f"  destructive-catch rate     {_pct(m['destructive_catch_rate'])}   (↑ better)",
        f"  false-approve rate         {_pct(m['false_approve_rate'])}   (↓ better — the dangerous errors)",
        f"  false-block rate           {_pct(m['false_block_rate'])}   (↓ better — the annoying errors)",
        f"  injection catch rate       {_pct(m['injection_catch_rate'])}   (adversarial slice)",
        "  " + "-" * 54,
        f"  severity exact-match       {_pct(m['severity_exact_match'])}   (n={m['severity_calibrated_n']})",
        f"  severity MAE (0-3 scale)   {m['severity_mae']:.2f}" if m["severity_mae"] is not None else "  severity MAE               n/a",
        "  " + "-" * 54,
        "  by category:",
    ]
    for c, cm in m["by_category"].items():
        lines.append(f"    {c:16} n={cm['n']:<3} exact-acc {_pct(cm['exact_accuracy'])}")
    if m["dangerous_misses"]:
        lines.append("  " + "-" * 54)
        lines.append(f"  ⚠ DANGEROUS MISSES (unsafe auto-allowed): {', '.join(m['dangerous_misses'])}")
    lines.append("═" * 58)
    return "\n".join(lines)


def build_eval_pipeline(provider) -> DecisionPipeline:
    return DecisionPipeline(stages=[PolicyStage(), RiskStage(provider=provider)])


def main() -> None:
    ap = argparse.ArgumentParser(description="Sentinel risk-engine evaluation")
    ap.add_argument("--provider", default="auto", choices=["auto", "mock", "gemini", "anthropic"])
    ap.add_argument("--dataset", default="eval/dataset.jsonl")
    ap.add_argument("--out", default="eval/results.json")
    ap.add_argument("--throttle", type=float, default=1.0, help="seconds between real LLM calls")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    if args.provider == "mock":
        provider = MockProvider()
    else:
        settings.risk_provider = args.provider
        provider = CachingProvider(
            build_provider(),
            cache_path=Path("eval/.cache/llm_cache.json"),
            throttle_s=args.throttle,
            use_cache=not args.no_cache,
        )

    dataset = load_dataset(args.dataset)
    print(f"Running {len(dataset)} cases through provider={getattr(provider, 'source', args.provider)} …")
    records = run_eval(dataset, build_eval_pipeline(provider))
    metrics = compute_metrics(records)

    print(format_report(metrics))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"metrics": metrics, "records": records}, indent=2))
    print(f"\nWrote detailed results → {out}")


if __name__ == "__main__":
    main()
