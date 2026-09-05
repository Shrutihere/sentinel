"""M3 tests — the human-in-the-loop approval lifecycle."""

from fastapi.testclient import TestClient

from sentinel.main import create_app

client = TestClient(create_app())

# A prod state-change with no matching policy rule -> risk stage (mock) rates it
# HIGH -> require_approval. Keeps this test independent of policy wording.
NEEDS_APPROVAL = {
    "agent_id": "ops-bot",
    "tool": "email.send",
    "action": "send a password-reset email to all users",
    "target": {"system": "sendgrid", "env": "prod"},
}


def _submit(payload=NEEDS_APPROVAL) -> dict:
    r = client.post("/v1/tool-call", json=payload)
    assert r.status_code == 200
    return r.json()


def test_high_risk_action_is_parked_not_executed():
    body = _submit()
    assert body["decision"] == "require_approval"
    assert body["executed"] is False
    assert body["status"] == "pending_approval"
    assert isinstance(body["approval_id"], int)


def test_pending_shows_in_list_then_approve_executes():
    body = _submit()
    aid = body["approval_id"]

    pend = client.get("/v1/approvals", params={"status": "pending"}).json()
    assert any(a["id"] == aid for a in pend)

    r = client.post(f"/v1/approvals/{aid}/approve", json={"decided_by": "shruti", "note": "ok"})
    assert r.status_code == 200
    view = r.json()
    assert view["status"] == "approved"
    assert view["executed"] is True
    assert view["decided_by"] == "shruti"


def test_deny_does_not_execute():
    aid = _submit()["approval_id"]
    r = client.post(f"/v1/approvals/{aid}/deny", json={"decided_by": "shruti"})
    assert r.status_code == 200
    view = r.json()
    assert view["status"] == "denied"
    assert view["executed"] is False


def test_decisions_are_idempotent():
    aid = _submit()["approval_id"]
    first = client.post(f"/v1/approvals/{aid}/approve", json={"decided_by": "a"})
    assert first.status_code == 200
    # Second decision on the same request must be rejected, never double-execute.
    second = client.post(f"/v1/approvals/{aid}/deny", json={"decided_by": "b"})
    assert second.status_code == 409


def test_approval_writes_a_second_audit_row():
    aid = _submit()["approval_id"]
    client.post(f"/v1/approvals/{aid}/approve", json={"decided_by": "shruti"})
    stages = [e["stage"] for e in client.get("/v1/audit").json()]
    # both the escalation and the human approval are in the trail
    assert any(s.startswith("risk:") for s in stages)
    assert any(s.startswith("approval:approved:") for s in stages)


def test_missing_approval_is_404():
    assert client.get("/v1/approvals/999999").status_code == 404
    assert client.post("/v1/approvals/999999/approve",
                       json={"decided_by": "x"}).status_code == 404
