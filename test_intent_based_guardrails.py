"""Comprehensive verification suite for Intent-Based Guardrails and Proactive Elicitation.
Verifies elimination of false-positive domain errors for shorthand and conversational scheduling inputs.
"""

from uuid import uuid4
from fastapi.testclient import TestClient
from api import app
from guardrails import pre_execution_guardrail, is_incomplete_scheduling_request

def test_intent_based_in_domain_classification():
    print("\n[TEST 1] Testing Intent-Based In-Domain Classification (Zero False-Positives)...")
    conversational_inputs = [
        "setup a meet",
        "SETUP A MEET",
        "i wanna go to gym",
        "quick call",
        "gym tomorrow",
        "dinner with team",
        "coffee with sarah",
        "dentist appointment",
        "doctor appointment",
        "dentist next week",
        "workout",
        "schedule a call",
        "set up a meeting",
        "book a slot",
        "walk with dog",
        "catchup with alex",
        "1:1 with manager",
        "have lunch",
        "need to cook dinner",
        "clean the apartment",
        "grocery run",
    ]

    for user_input in conversational_inputs:
        is_valid, err_msg = pre_execution_guardrail(user_input)
        assert is_valid is True, f"False-positive rejection on '{user_input}': {err_msg}"
        print(f"  [PASS] '{user_input}' -> IN-DOMAIN (is_valid=True)")

def test_purely_out_of_domain_rejection():
    print("\n[TEST 2] Testing Out-of-Domain Guardrail Retention (Strictly Irrelevant Queries)...")
    out_of_domain_inputs = [
        "what is the weather today?",
        "what is the capital of Australia?",
        "who was the first president of the united states?",
        "tell me a joke about airplanes",
        "Write me a poem about the ocean",
        "write a python script to parse json",
        "how to program in typescript",
        "explain quantum physics",
    ]

    for user_input in out_of_domain_inputs:
        is_valid, err_msg = pre_execution_guardrail(user_input)
        assert is_valid is False, f"Expected rejection for out-of-domain query '{user_input}', but passed."
        assert "specialize exclusively in task scheduling" in err_msg
        print(f"  [PASS] '{user_input}' -> REJECTED (off-topic guardrail active)")

def test_proactive_elicitation_for_incomplete_requests():
    print("\n[TEST 3] Testing Proactive Conversational Elicitation for Incomplete Inputs...")
    client = TestClient(app)

    test_queries = [
        "setup a meet",
        "SETUP A MEET",
        "i wanna go to gym",
        "quick call",
        "gym tomorrow",
        "dinner with team",
        "schedule a call",
        "coffee with sarah",
    ]

    expected_elicitation = "I'll help you schedule that. What date and time window would you like to set?"

    for i, q in enumerate(test_queries):
        sess_id = f"test_elicitation_{i}"
        res = client.post("/api/chat", json={"session_id": sess_id, "message": q})
        assert res.status_code == 200
        data = res.json()

        # 1. No off-topic error
        assert "specialize exclusively in task scheduling" not in data["reply"]
        # 2. Exact proactive elicitation response
        assert "target date and time below" in data["reply"] or "what date and time window" in data["reply"].lower(), (
            f"For '{q}', expected elicitation prompt, got '{data['reply']}'"
        )
        # 3. UI action attached
        assert data["ui_action"] == "show_date_time_picker"
        assert data["requires_date_selection"] is True
        # 4. No premature schedule with arbitrary default times
        assert data["schedule"] is None
        print(f"  [PASS] '{q}' -> Proactively elicited date/time window with ui_action: 'show_date_time_picker'")

def test_full_interactive_lifecycle():
    print("\n[TEST 4] Testing Full Interactive Lifecycle: Elicitation -> Parameter Confirmation -> Schedule Packing...")
    client = TestClient(app)
    sess_id = f"test_lifecycle_{uuid4().hex[:8]}"

    # Turn 1: Conversational incomplete request
    res1 = client.post("/api/chat", json={"session_id": sess_id, "message": "dinner with team"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert "target date and time below" in data1["reply"].lower() or "what date and time window" in data1["reply"].lower()
    assert data1["ui_action"] == "show_date_time_picker"
    assert data1["schedule"] is None

    # Turn 2: User confirms via DatePicker card
    res2 = client.post(
        "/api/chat",
        json={"session_id": sess_id, "message": "Schedule Dinner on 2026-10-15 for 60m"}
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["schedule"] is not None
    assert data2["schedule"]["date"] == "2026-10-15"
    blocks = data2["schedule"]["time_blocks"]
    assert len(blocks) >= 1
    assert blocks[0]["label"] == "Dinner Preparation" or "Dinner" in blocks[0]["label"]
    assert blocks[0]["end_time"] == "10:00:00"  # 60m duration from 09:00
    print(f"  [PASS] Interactive lifecycle successfully placed commitment on {data2['schedule']['date']} with label '{blocks[0]['label']}'")

def test_anchored_and_complete_requests_remain_unaffected():
    print("\n[TEST 5] Testing Anchored & Multi-Task Requests Continue Operating Normally...")
    client = TestClient(app)

    # 1. Anchored time prompt -> anchor clarification
    sess_anchor = f"test_anchor_{uuid4().hex[:8]}"
    res_anchor = client.post("/api/chat", json={"session_id": sess_anchor, "message": "set a meeting at 12"})
    assert res_anchor.status_code == 200
    assert "I have noted the start time at 12:00" in res_anchor.json()["reply"]
    print("  [PASS] 'set a meeting at 12' correctly entered anchor duration clarification.")

    # 2. Multi-task brain dump with explicit durations -> immediate packing
    sess_multi = f"test_multi_{uuid4().hex[:8]}"
    res_multi = client.post(
        "/api/chat",
        json={"session_id": sess_multi, "message": "Draft Architecture RFC 90m high priority, gym 45m"}
    )
    assert res_multi.status_code == 200
    assert res_multi.json()["schedule"] is not None
    assert len(res_multi.json()["schedule"]["time_blocks"]) >= 2
    print("  [PASS] Multi-task brain dump with durations immediately packed into schedule timeline.")

if __name__ == "__main__":
    test_intent_based_in_domain_classification()
    test_purely_out_of_domain_rejection()
    test_proactive_elicitation_for_incomplete_requests()
    test_full_interactive_lifecycle()
    test_anchored_and_complete_requests_remain_unaffected()
    print("\n" + "=" * 60)
    print("ALL INTENT-BASED GUARDRAIL & PROACTIVE ELICITATION TESTS PASSED!")
    print("=" * 60)
