"""Comprehensive automated verification suite for Brief Meeting Requests,
Domain Classification, and Interactive Date/Time Collection Flow.
"""

from fastapi.testclient import TestClient
from api import app
from guardrails import pre_execution_guardrail, is_unanchored_meeting_request

def test_guardrail_domain_broadening():
    print("\n[TEST 1] Testing Guardrail Domain Broadening for Meeting/Scheduling Requests...")
    in_domain_samples = [
        "SETUP A MEET",
        "setup a meet",
        "schedule a call",
        "set up a call",
        "schedule a meeting",
        "set up a meeting",
        "book a meet",
        "book a call",
        "book a slot",
        "setup a sync",
        "schedule a sync",
        "set up a sync",
        "schedule an appointment",
        "book an appointment",
        "quick sync",
        "gym",
        "workout",
        "plan",
        "schedule",
    ]

    for sample in in_domain_samples:
        is_valid, err_msg = pre_execution_guardrail(sample)
        assert is_valid is True, f"Expected in-domain for '{sample}', but was rejected with: {err_msg}"
        print(f"  [PASS] '{sample}' -> IN-DOMAIN (is_valid=True)")

def test_off_topic_guardrail_retention():
    print("\n[TEST 2] Testing Off-Topic Guardrail Rejection for Genuinely Unrelated Queries...")
    off_topic_samples = [
        "what is the weather today?",
        "tell me a joke about airplanes",
        "Write me a poem about the ocean",
        "write a python script to parse json",
        "who was the first president of the united states?",
    ]

    for sample in off_topic_samples:
        is_valid, err_msg = pre_execution_guardrail(sample)
        assert is_valid is False, f"Expected off-topic rejection for '{sample}', but passed."
        assert "specialize exclusively in task scheduling" in err_msg
        print(f"  [PASS] '{sample}' -> REJECTED (off-topic guardrail active)")

def test_unanchored_meeting_request_identification():
    print("\n[TEST 3] Testing is_unanchored_meeting_request Helper Detection...")
    assert is_unanchored_meeting_request("SETUP A MEET") is True
    assert is_unanchored_meeting_request("schedule a call") is True
    assert is_unanchored_meeting_request("set up a meeting") is True
    assert is_unanchored_meeting_request("book a slot") is True
    assert is_unanchored_meeting_request("schedule an appointment") is True
    
    # Anchored or fully specified should be False
    assert is_unanchored_meeting_request("set a meeting at 12") is False
    assert is_unanchored_meeting_request("I have a meeting in 5 minutes") is False
    assert is_unanchored_meeting_request("Schedule meeting on 2026-10-15 for 30m") is False
    print("  [PASS] All unanchored vs anchored boundary conditions verified.")

def test_chat_endpoint_interactive_meeting_flow():
    print("\n[TEST 4] Testing Chat Endpoint Interactive Meeting Flow for 'SETUP A MEET'...")
    import uuid
    client = TestClient(app)
    sess_id = f"test_meet_{uuid.uuid4().hex[:8]}"

    # Turn 1: "SETUP A MEET"
    res1 = client.post("/api/chat", json={"session_id": sess_id, "message": "SETUP A MEET"})
    assert res1.status_code == 200
    data1 = res1.json()

    # 1. Does not trigger off-topic fallback
    assert "specialize exclusively in task scheduling" not in data1["reply"]
    # 2. Responds with the clarification prompt
    assert "What date and time window would you like to set?" in data1["reply"] or "target date and time below" in data1["reply"].lower()
    # 3. Includes ui_action: "show_date_time_picker"
    assert data1["ui_action"] == "show_date_time_picker"
    assert data1["requires_date_selection"] is True
    # 4. Does not pack arbitrary default times
    assert data1["schedule"] is None
    print("  [PASS] Turn 1 correctly initiated interactive date/time collection flow with ui_action: 'show_date_time_picker'.")

    # Turn 2: "schedule a call"
    res2 = client.post("/api/chat", json={"session_id": "test_meet_interactive_02", "message": "schedule a call"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert "What date and time window would you like to set?" in data2["reply"] or "target date and time below" in data2["reply"].lower()
    assert data2["ui_action"] == "show_date_time_picker"
    assert data2["requires_date_selection"] is True
    assert data2["schedule"] is None
    print("  [PASS] 'schedule a call' correctly initiated interactive date/time collection flow.")

    # Turn 3: User submits date & duration via DatePicker card
    res3 = client.post(
        "/api/chat",
        json={"session_id": sess_id, "message": "Schedule meeting on 2026-10-16 for 45m"}
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["schedule"] is not None
    assert data3["schedule"]["date"] == "2026-10-16"
    blocks = data3["schedule"]["time_blocks"]
    assert len(blocks) >= 1
    assert blocks[0]["label"] == "Meeting"
    print(f"  [PASS] Turn 3 scheduled meeting accurately on target date {data3['schedule']['date']} with label '{blocks[0]['label']}'.")

def test_persistence_and_versioning_retention():
    print("\n[TEST 5] Testing Session Persistence, Approval, and Rollback Snapshots...")
    import uuid
    client = TestClient(app)
    sess_id = f"test_persist_{uuid.uuid4().hex[:8]}"

    # Setup schedule
    r1 = client.post(
        "/api/chat",
        json={"session_id": sess_id, "message": "Schedule meeting on 2026-10-18 for 30m"}
    )
    assert r1.status_code == 200
    assert r1.json()["schedule"] is not None

    # Approve schedule (Version 1 snapshot created)
    r_app = client.post(f"/api/schedule/{sess_id}/approve")
    assert r_app.status_code == 200
    app_data = r_app.json()
    assert app_data["success"] is True
    assert app_data["current_version_id"] == 1
    assert len(app_data["version_history"]) == 1
    print("  [PASS] Session persisted and Version 1 committed successfully.")

    # Add second task (gym)
    r2 = client.post(
        "/api/chat",
        json={"session_id": sess_id, "message": "Schedule Gym Session at 18:00 for 45m"}
    )
    assert r2.status_code == 200
    r_app2 = client.post(f"/api/schedule/{sess_id}/approve")
    assert r_app2.status_code == 200
    assert r_app2.json()["current_version_id"] == 2
    assert len(r_app2.json()["version_history"]) == 2
    print("  [PASS] Version 2 committed with Gym Session.")

    # Rollback to Version 1
    r_rb = client.post(f"/api/schedule/{sess_id}/rollback", json={"target_version_id": 1})
    assert r_rb.status_code == 200
    rb_data = r_rb.json()
    assert rb_data["success"] is True
    assert rb_data["restored_version_id"] == 1
    assert rb_data["current_version_id"] == 1
    print("  [PASS] Rollback snapshot to Version 1 restored cleanly.")

if __name__ == "__main__":
    test_guardrail_domain_broadening()
    test_off_topic_guardrail_retention()
    test_unanchored_meeting_request_identification()
    test_chat_endpoint_interactive_meeting_flow()
    test_persistence_and_versioning_retention()
    print("\n" + "=" * 60)
    print("ALL BRIEF MEETING GUARDRAIL & INTERACTIVE FLOW TESTS PASSED!")
    print("=" * 60)
