"""Automated verification suite for Title Normalization, Unanchored Habit Clarification Chips,
and Inline Generative UI Date-Picker Request intents.
"""

from fastapi.testclient import TestClient
from api import app
from tools import parse_task_attributes

def test_title_normalization():
    print("\n[TEST 1] Testing Title Normalization...")
    gym_res = parse_task_attributes("i wanna go to gym")
    assert gym_res["success"] is True
    assert gym_res["data"]["title"] == "Gym Session", f"Expected 'Gym Session', got {gym_res['data']['title']}"
    print("  [PASS] 'i wanna go to gym' -> 'Gym Session'")

    lunch_res = parse_task_attributes("need to cook lunch")
    assert lunch_res["success"] is True
    assert lunch_res["data"]["title"] == "Lunch Preparation", f"Expected 'Lunch Preparation', got {lunch_res['data']['title']}"
    print("  [PASS] 'need to cook lunch' -> 'Lunch Preparation'")

    groceries_res = parse_task_attributes("buy groceries")
    assert groceries_res["success"] is True
    assert groceries_res["data"]["title"] == "Grocery Shopping"
    print("  [PASS] 'buy groceries' -> 'Grocery Shopping'")

def test_unanchored_habit_chips_and_flow():
    print("\n[TEST 2] Testing Unanchored Habit Clarification & Action Chips...")
    client = TestClient(app)
    sess_id = "test_unanchored_flow_01"

    # Turn 1: Unanchored habit query
    res1 = client.post("/api/chat", json={"session_id": sess_id, "message": "i wanna go to gym"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert "What time would you prefer to schedule your Gym Session?" in data1["reply"]
    assert data1["action_chips"] == ["Morning (07:00)", "Noon (12:30)", "Evening (18:00)", "Specify Time"]
    assert data1["requires_date_selection"] is False
    print("  [PASS] Turn 1 emitted consultative question with action chips")

    # Turn 2: User clicks/submits "Evening (18:00)"
    res2 = client.post("/api/chat", json={"session_id": sess_id, "message": "Evening (18:00)"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["schedule"] is not None
    blocks = data2["schedule"]["time_blocks"]
    assert len(blocks) >= 1
    assert blocks[0]["label"] == "Gym Session"
    assert blocks[0]["start_time"] == "18:00:00"
    assert blocks[0]["end_time"] == "18:45:00"
    print(f"  [PASS] Turn 2 placed block accurately at: {blocks[0]['start_time']} - {blocks[0]['end_time']} | {blocks[0]['label']}")

def test_future_date_intent_detection():
    print("\n[TEST 3] Testing Future Date Intent Detection...")
    client = TestClient(app)
    
    # Check "schedule a meeting"
    res1 = client.post("/api/chat", json={"session_id": "test_future_01", "message": "schedule a meeting"})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["requires_date_selection"] is True
    print("  [PASS] 'schedule a meeting' flagged requires_date_selection: True")

    # Check "plan tomorrow"
    res2 = client.post("/api/chat", json={"session_id": "test_future_02", "message": "plan tomorrow"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["requires_date_selection"] is True
    print("  [PASS] 'plan tomorrow' flagged requires_date_selection: True")

    # Check "next week"
    res3 = client.post("/api/chat", json={"session_id": "test_future_03", "message": "next week"})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["requires_date_selection"] is True
    print("  [PASS] 'next week' flagged requires_date_selection: True")

    # Check inline date card confirmation payload
    res_confirm = client.post(
        "/api/chat",
        json={"session_id": "test_future_01", "message": "Schedule meeting on 2026-10-15 for 30m"}
    )
    assert res_confirm.status_code == 200
    data_confirm = res_confirm.json()
    assert data_confirm["schedule"] is not None
    assert data_confirm["schedule"]["date"] == "2026-10-15"
    blocks = data_confirm["schedule"]["time_blocks"]
    assert len(blocks) >= 1
    assert blocks[0]["label"] == "Meeting"
    print(f"  [PASS] DatePicker confirmation scheduled on target date: {data_confirm['schedule']['date']} | {blocks[0]['label']}")

if __name__ == "__main__":
    test_title_normalization()
    test_unanchored_habit_chips_and_flow()
    test_future_date_intent_detection()
    print("\n" + "=" * 60)
    print("ALL GENERATIVE UI & TITLE NORMALIZATION TESTS PASSED!")
    print("=" * 60)
