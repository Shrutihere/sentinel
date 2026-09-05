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
- [ ] M1 — Policy layer (deterministic allow/deny/require-approval)
- [ ] M2 — ⭐ Risk engine (hybrid guardrails + Claude scorer)
- [ ] M3 — Approval workflow (human-in-the-loop)
- [ ] M4 — ⭐ Eval harness + labeled dataset (the proof)
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

## Architecture

The gateway runs an ordered **decision pipeline** of stages; the first stage to object wins, otherwise
the action is allowed. Cheap deterministic stages run before the LLM, so policy short-circuits before
we ever pay for a model call. Every outcome is written to an append-only audit log.

## Tech

FastAPI · SQLAlchemy (SQLite locally → Postgres in prod, via one env var) · Pydantic · Claude (M2) ·
React dashboard (M5) · Docker (M5).
