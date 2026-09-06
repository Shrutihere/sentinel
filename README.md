# Sentinel

**A risk-evaluation & approval engine for autonomous AI agents.**

As AI agents move from chat into executing real operations — hitting GitHub, databases, CI/CD, cloud
infra, and internal APIs — the blast radius of a wrong or malicious action grows. Most teams have
allow/deny lists but no *judgment* layer. Sentinel is that layer: it sits between an agent and its
tools, scores the **risk of each requested action in context**, and routes high-risk actions to a
human — with a calibrated evaluation harness that **proves the scoring works.**

```
Agent → Identity → Policy → Risk Evaluation → Approval → Tool → Audit
```

Unlike off-the-shelf MCP gateways, the differentiator is the **risk brain + its eval harness**: a
hybrid scorer (deterministic guardrails + a Claude contextual risk model) measured against a labeled
benchmark of safe / risky / destructive / adversarial actions.

## Status

Built in milestones (see `../cv/agent-risk-eval-scope.md` for the full scope):

- [x] **M0 — Pass-through gateway + audit** — the intercept + append-only audit trail
- [x] **M1 — Policy layer** — RBAC + declarative allow/deny/require-approval rules
- [x] **M2 — ⭐ Risk engine** — hybrid deterministic guardrails + LLM contextual scorer (Gemini/Claude/Mock)
- [x] **M3 — Approval workflow** — durable human-in-the-loop approve/deny with attribution + idempotency
- [x] **M4 — ⭐ Eval harness + labeled dataset** — 62-case benchmark; 97.8% catch, 2.2% false-approve, 100% injection catch
- [ ] M5 — React dashboard, Docker, live deploy

## Quickstart

```bash
uv venv
uv pip install -e ".[dev]"
uv run pytest -q                    # run the tests
uv run uvicorn sentinel.main:app --reload   # start the API (http://127.0.0.1:8000/docs)
```

## Try it

```bash
curl -s http://127.0.0.1:8000/v1/tool-call \
  -H 'content-type: application/json' \
  -d '{"agent_id":"devops-bot","role":"deployer","tool":"shell.exec",
       "action":"git push --force origin main",
       "target":{"system":"github","resource":"repo/main","env":"prod"}}' | jq
```

## Evaluation

The risk engine is measured against a **62-case labeled benchmark** (`eval/dataset.jsonl`) spanning safe,
needs-approval, destructive, and **adversarial (prompt-injection)** actions. Every case runs through the
real pipeline; the harness reports catch-rate, false-approve/block rates, injection robustness, and
severity calibration.

```bash
uv run python -m sentinel.evaluate --provider gemini    # or --provider mock (offline)
```

Contextual LLM scorer vs. a naive keyword heuristic, same benchmark:

| Metric | Keyword heuristic | **LLM (Gemini) scorer** |
|---|---|---|
| Destructive-catch rate | 73.9% | **97.8%** |
| False-approve rate *(unsafe auto-allowed)* | 26.1% | **2.2%** |
| Injection catch rate *(adversarial slice)* | 64.3% | **100%** |
| False-block rate | 6.2% | 6.2% |
| Severity calibration (MAE, 0–3 scale) | 0.86 | **0.42** |
| Dangerous misses | 7 | **0** |

Note: exact-decision accuracy (~68%) trails catch-rate because the engine tends to *escalate* borderline
destructive actions to human approval rather than hard-deny — a deliberately conservative, tunable
precision/recall tradeoff (the severity→decision threshold matrix). Nothing unsafe is auto-allowed.

## Architecture

The gateway runs an ordered **decision pipeline** of stages; the first stage to object wins, otherwise
the action is allowed. Cheap deterministic stages run before the LLM, so policy short-circuits before
we ever pay for a model call. Every outcome is written to an append-only audit log.

Pipeline: **Policy** (RBAC + declarative rules) → **Guardrails** (deterministic destructive-op signatures)
→ **Risk scorer** (LLM contextual assessment) → **Approval** (human-in-the-loop) → **Audit**.

## Tech

FastAPI · SQLAlchemy (SQLite locally → Postgres in prod, via one env var) · Pydantic · Gemini/Claude/Mock
risk providers · React dashboard (M5) · Docker (M5).
