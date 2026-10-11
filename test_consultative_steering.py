"""Automated verification suite for Executive Routine Concierge Steering Persona,
Casual Talk Handling, Confirmation Gate, and Frontend Guard.
"""

from uuid import uuid4
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_casual_steering_inputs():
    print("\n--- Test 1: Casual & Ambiguous Inputs (No UI Card, No Premature Task) ---")
    test_cases = [
        ("yo", "focus blocks for today", "workout or meeting"),
        ("hey", "focus blocks for today", "workout or meeting"),
        ("what's up", "focus blocks for today", "workout or meeting"),
        ("feeling tired", "recovery buffer now", "remaining tasks early"),
        ("exhausted", "recovery buffer now", "remaining tasks early"),
        ("just had lunch", "shallow work block", "deep work"),
        ("just finished lunch", "shallow work block", "deep work"),
        ("feeling overwhelmed", "reset buffer now", "top three must-do items"),
        ("im bored", "deep focus sprint", "operational errands"),
    ]

    for user_input, expected_choice_1, expected_choice_2 in test_cases:
        sess_id = f"test_casual_{uuid4().hex[:8]}"
        res = client.post("/api/chat", json={"session_id": sess_id, "message": user_input})
        assert res.status_code == 200, f"Failed for '{user_input}': {res.text}"
        data = res.json()
        reply = data["reply"]
        print(f"\nUser: '{user_input}'")
        print(f"Reply: {reply}")
        print(f"UI Action: {data.get('ui_action')}")
        print(f"Default Task: {data.get('default_task')}")

        # Rule 1: NEVER trigger pack_schedule or ui_action: show_date_time_picker
        assert data.get("ui_action") is None, f"Expected ui_action to be None for '{user_input}', got {data.get('ui_action')}"
        assert data.get("requires_date_selection") is False
        assert data.get("schedule") is None, f"Expected no schedule for '{user_input}', got {data.get('schedule')}"

        # Rule 2: NEVER treat conversational phrases as task titles
        assert data.get("default_task") is None, f"Expected default_task to be None, got {data.get('default_task')}"
        assert not any(f"schedule {user_input.lower()}" in reply.lower() for _ in [1]), f"Conversational phrase treated as task in reply: {reply}"

        # Rule 3: Engage conversationally and present 2 concrete choices
        assert expected_choice_1.lower() in reply.lower(), f"Expected choice '{expected_choice_1}' in reply: {reply}"
        assert expected_choice_2.lower() in reply.lower(), f"Expected choice '{expected_choice_2}' in reply: {reply}"

        # Constraint: Under 3 sentences
        sentences = [s.strip() for s in reply.split(".") if s.strip()]
        # Some sentences might end with '?'
        q_sentences = [s.strip() for s in reply.replace("?", ".").replace("!", ".").split(".") if s.strip()]
        print(f"Sentence count: {len(q_sentences)}")
        assert len(q_sentences) <= 3, f"Expected <= 3 sentences, got {len(q_sentences)}: {reply}"

    print("\nTest 1 Passed: All casual inputs handled with natural banter and 2 steering options!")

def test_confirmation_gate():
    print("\n--- Test 2: Confirmation Gate (Transition from Steering to Action) ---")
    sess_id = f"test_gate_{uuid4().hex[:8]}"

    # Turn 1: User vents fatigue
    res1 = client.post("/api/chat", json={"session_id": sess_id, "message": "feeling tired"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["ui_action"] is None
    assert "recovery buffer now" in data1["reply"].lower()

    # Turn 2: User accepts steering choice: "schedule a 20-minute recovery buffer now"
    res2 = client.post("/api/chat", json={"session_id": sess_id, "message": "schedule a 20-minute recovery buffer now"})
    assert res2.status_code == 200
    data2 = res2.json()
    print("Turn 2 Reply:", data2["reply"])
    sched = data2.get("schedule")
    assert sched is not None, "Expected schedule to be populated after accepting steering option"
    time_blocks = sched.get("time_blocks", [])
    assert len(time_blocks) >= 1
    assert "Recovery Buffer" in time_blocks[0].get("label")
    print(f"Scheduled Block: {time_blocks[0].get('label')} [{time_blocks[0].get('start_time')} - {time_blocks[0].get('end_time')}]")
    print("Test 2 Passed: Successfully transitioned from steering to scheduling!")

def test_unanchored_and_chained_preserved():
    print("\n--- Test 3: Verify Concrete Tasks and Chained Sequences Remain Intact ---")
    # Concrete unanchored task should still elicit via date-time picker
    sess_id = f"test_concrete_{uuid4().hex[:8]}"
    res_gym = client.post("/api/chat", json={"session_id": sess_id, "message": "i wanna go to gym"})
    assert res_gym.status_code == 200
    data_gym = res_gym.json()
    assert data_gym["ui_action"] == "show_date_time_picker"
    assert data_gym["default_task"] == "Gym Session"

    # Chained sequence should still pack in one pass
    res_chain = client.post(
        "/api/chat",
        json={"session_id": f"test_chain_{uuid4().hex[:8]}", "message": "setup meeting now, then gym and after that rest and then again meeting"}
    )
    assert res_chain.status_code == 200
    data_chain = res_chain.json()
    assert data_chain["ui_action"] is None
    assert len(data_chain["schedule"]["time_blocks"]) >= 4
    print("Test 3 Passed: Concrete tasks and chained multi-task sequences work seamlessly!")

if __name__ == "__main__":
    test_casual_steering_inputs()
    test_confirmation_gate()
    test_unanchored_and_chained_preserved()
    print("\nALL CONSULTATIVE CONCIERGE STEERING TESTS PASSED SUCCESSFULLY!")
