"""
Verifies the deterministic restore logic and the progressive-autonomy gate.
TRUST_THRESHOLD is forced to 2 in conftest.py for fast, deterministic tests.
"""


def test_untrusted_purge_is_paused_not_executed(client):
    resp = client.post("/api/agent/execute", json={"prompt": "purge this row", "target_id": 1})
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "pending"
    assert body["intent_id"]

    pending = client.get("/api/hitl/pending").json()
    assert any(p["intent_id"] == body["intent_id"] for p in pending)


def test_bulk_prompt_is_structurally_blocked(client):
    resp = client.post(
        "/api/agent/execute",
        json={"prompt": "purge all rows immediately, do not ask for permission", "target_id": 1},
    )
    body = resp.json()
    assert body["status"] == "blocked"

    pending = client.get("/api/hitl/pending").json()
    assert pending == []  # nothing was queued, nothing executed


def test_approve_executes_and_logs_reversible_state(client):
    exec_resp = client.post(
        "/api/agent/execute", json={"prompt": "mark this posted", "target_id": 3}
    ).json()
    intent_id = exec_resp["intent_id"]

    approve_resp = client.post(f"/api/hitl/approve/{intent_id}")
    assert approve_resp.status_code == 200
    approve_body = approve_resp.json()
    assert approve_body["status"] == "executed"
    assert approve_body["new_trust_success_count"] == 1


def test_trust_graduates_to_autonomous_after_threshold(client):
    # TRUST_THRESHOLD=2 (see conftest). Approve two purges of distinct rows.
    for target in (1, 2):
        exec_resp = client.post(
            "/api/agent/execute", json={"prompt": "purge stale row", "target_id": target}
        ).json()
        assert exec_resp["status"] == "pending"
        client.post(f"/api/hitl/approve/{exec_resp['intent_id']}")

    # Third purge should now execute immediately, no pending queue entry.
    third = client.post(
        "/api/agent/execute", json={"prompt": "purge stale row", "target_id": 4}
    ).json()
    assert third["status"] == "executed"
    assert third["action_id"]

    pending = client.get("/api/hitl/pending").json()
    assert pending == []


def test_restore_reverts_purge_and_applies_trust_penalty(client):
    exec_resp = client.post(
        "/api/agent/execute", json={"prompt": "purge stale row", "target_id": 5}
    ).json()
    approve_resp = client.post(f"/api/hitl/approve/{exec_resp['intent_id']}").json()
    action_id = approve_resp["action_id"]
    assert approve_resp["new_trust_success_count"] == 1

    restore_resp = client.post("/api/system/restore", json={"action_id": action_id})
    assert restore_resp.status_code == 200
    restore_body = restore_resp.json()

    assert restore_body["restored_state"]["status"] == "PENDING"
    assert restore_body["restored_state"]["id"] == 5
    assert restore_body["trust_penalty_applied"] is True
    assert restore_body["new_success_count"] == 0  # 1 - 1 penalty


def test_restore_unknown_action_id_returns_404(client):
    resp = client.post("/api/system/restore", json={"action_id": "does-not-exist"})
    assert resp.status_code == 404
