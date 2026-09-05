"""M0 tests — prove the intercept works and every action is audited."""

from fastapi.testclient import TestClient

from sentinel.main import create_app

client = TestClient(create_app())


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_tool_call_passes_through_and_is_audited():
    payload = {
        "agent_id": "devops-bot",
        "role": "deployer",
        "tool": "shell.exec",
        "action": "ls -la",
        "target": {"system": "shell", "env": "staging"},
    }
    r = client.post("/v1/tool-call", json=payload)
    assert r.status_code == 200

    body = r.json()
    # A benign action: guardrails stay silent, the risk scorer rates it low -> allow.
    assert body["decision"] == "allow"
    assert body["executed"] is True
    assert body["stage"].startswith("risk:")   # the risk stage now decides low-risk actions
    assert body["audit_id"] >= 1


def test_audit_trail_records_the_action():
    payload = {
        "agent_id": "data-bot",
        "tool": "db.query",
        "action": "SELECT * FROM orders LIMIT 5",
        "target": {"system": "postgres", "resource": "table:orders", "env": "prod"},
    }
    client.post("/v1/tool-call", json=payload)

    r = client.get("/v1/audit")
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()]
    assert "SELECT * FROM orders LIMIT 5" in actions
