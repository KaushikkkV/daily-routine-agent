import uuid
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

def test_chained_multi_task():
    print("\n--- Test 1: Chained Multi-Task Sequence ---")
    prompt = "setup meeting now, then gym and after that rest and then again meeting"
    sess_id = f"test_chain_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/chat", json={"session_id": sess_id, "message": prompt})
    assert resp.status_code == 200, f"Status: {resp.status_code}, text: {resp.text}"
    data = resp.json()
    print("Reply:", data.get("reply"))
    print("UI Action:", data.get("ui_action"))
    sched = data.get("schedule")
    blocks = sched.get("time_blocks", []) if sched else []
    print("Schedule blocks count:", len(blocks))
    for b in blocks:
        print(f"  Block: {b.get('label')} [{b.get('start_time')} - {b.get('end_time')}]")

    # Assertions
    assert data.get("ui_action") is None, f"Expected ui_action to be None, got {data.get('ui_action')}"
    assert len(blocks) >= 4, f"Expected at least 4 blocks, got {len(blocks)}"
    labels = [b.get("label") for b in blocks]
    assert any("Meeting" in l for l in labels), f"Expected Meeting in labels: {labels}"
    assert any("Gym" in l for l in labels), f"Expected Gym in labels: {labels}"
    assert any("Rest" in l for l in labels), f"Expected Rest in labels: {labels}"
    print("Test 1 Passed!")

def test_isolated_unanchored_tasks():
    print("\n--- Test 2: Isolated Unanchored Tasks ---")
    test_cases = [
        ("i wanna go to gym", "Gym Session"),
        ("setup a meet", "Meeting"),
    ]
    for prompt, expected_default in test_cases:
        sess_id = f"test_iso_{uuid.uuid4().hex[:8]}"
        resp = client.post("/api/chat", json={"session_id": sess_id, "message": prompt})
        assert resp.status_code == 200, f"Status: {resp.status_code}, text: {resp.text}"
        data = resp.json()
        print(f"Prompt '{prompt}':")
        print("  Reply:", data.get("reply"))
        print("  UI Action:", data.get("ui_action"))
        print("  Default Task:", data.get("default_task"))
        
        assert data.get("ui_action") == "show_date_time_picker", f"Expected show_date_time_picker, got {data.get('ui_action')}"
        assert data.get("default_task") is not None, "Expected default_task to be populated"
        assert expected_default.lower() in data.get("default_task", "").lower(), f"Expected {expected_default} in {data.get('default_task')}"
        assert "target date and time below" in data.get("reply", "").lower() or "please select" in data.get("reply", "").lower(), f"Expected elicitation prompt, got {data.get('reply')}"
        assert data.get("schedule") is None, "Should not prematurely commit schedule"
    print("Test 2 Passed!")

def test_ampm_scheduling():
    print("\n--- Test 3: 12-Hour AM/PM Scheduling ---")
    prompt = "Schedule Gym Session on 2026-10-15 at 02:30 PM for 45m"
    sess_id = f"test_ampm_{uuid.uuid4().hex[:8]}"
    resp = client.post("/api/chat", json={"session_id": sess_id, "message": prompt})
    assert resp.status_code == 200, f"Status: {resp.status_code}, text: {resp.text}"
    data = resp.json()
    print("Reply:", data.get("reply"))
    sched = data.get("schedule")
    blocks = sched.get("time_blocks", []) if sched else []
    print("Schedule blocks count:", len(blocks))
    assert len(blocks) >= 1, "Expected scheduled block"
    block = blocks[0]
    print(f"Scheduled block: {block.get('label')} start: {block.get('start_time')}")
    assert "14:30" in block.get("start_time", ""), f"Expected 14:30 start time, got {block.get('start_time')}"
    print("Test 3 Passed!")

if __name__ == "__main__":
    test_chained_multi_task()
    test_isolated_unanchored_tasks()
    test_ampm_scheduling()
    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")
