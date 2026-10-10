"""Integration test suite for api.py FastAPI endpoints."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import date, time
from uuid import uuid4

# Set test database path before importing app
temp_dir = tempfile.mkdtemp()
os.environ["CONCIERGE_DB_PATH"] = os.path.join(temp_dir, "test_api_sessions.db")

from fastapi.testclient import TestClient
from api import app, session_store
from schemas import AgentState, DailySchedule, TaskCategory, TaskItem, TimeBlock
from tools import bind_agent_state, save_schedule_to_storage


def run_api_tests():
    print("=" * 60)
    print("RUNNING FASTAPI BRIDGE SERVER INTEGRATION TESTS")
    print("=" * 60)

    # 1. Install httpx if needed for TestClient
    try:
        client = TestClient(app)
    except Exception as e:
        print(f"TestClient creation error: {e}")
        return

    # Test 1: Health check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("[PASS] Test 1: GET /api/health returns 200 OK")

    # Test 2: GET /api/schedule/{session_id} on non-existent session returns empty schedule
    test_sess_id = f"sess_{uuid4().hex[:8]}"
    res = client.get(f"/api/schedule/{test_sess_id}")
    assert res.status_code == 200, f"Expected 200 empty envelope: {res.text}"
    data = res.json()
    assert data["session_id"] == test_sess_id
    assert data["schedule"] is None
    assert data["current_version_id"] == 0
    assert data["version_history"] == []
    print("[PASS] Test 2: GET /api/schedule/{session_id} for new session returns empty envelope")

    # Test 3: POST /api/chat with ambiguous input
    res = client.post(
        "/api/chat",
        json={"session_id": test_sess_id, "message": "Help me plan my morning activities sometime later"},
    )
    assert res.status_code == 200, f"Chat endpoint failed: {res.text}"
    chat_data = res.json()
    assert "reply" in chat_data
    assert "thought" in chat_data
    assert chat_data["current_version_id"] == 0
    assert chat_data["pending_approval"] is False
    print(f"[PASS] Test 3: POST /api/chat returns clean response and isolated thoughts")

    # Test 4: Seed schedule in state and test approve endpoint
    seed_state = session_store.load(test_sess_id)
    assert seed_state is not None
    seed_schedule = DailySchedule(
        date=date(2026, 10, 10),
        time_blocks=[
            TimeBlock(start_time=time(9, 0), end_time=time(10, 30), label="Write Proposal"),
            TimeBlock(start_time=time(10, 30), end_time=time(10, 40), label="Recovery Buffer", is_buffer=True),
        ],
        tasks_allocated=[
            TaskItem(title="Write Proposal", category=TaskCategory.DEEP_WORK, estimated_minutes=90)
        ],
        buffer_time_minutes=10,
    )
    seed_state.active_schedule = seed_schedule
    session_store.save(seed_state)

    # Test approve endpoint
    res = client.post(f"/api/schedule/{test_sess_id}/approve")
    assert res.status_code == 200, f"Approve failed: {res.text}"
    appr_data = res.json()
    assert appr_data["success"] is True
    assert appr_data["current_version_id"] == 1
    assert appr_data["pending_approval"] is False
    assert len(appr_data["version_history"]) == 1
    print("[PASS] Test 4: POST /api/schedule/{session_id}/approve commits schedule (v1)")

    # Test 5: Mutate and commit v2, then test rollback
    seed_state = session_store.load(test_sess_id)
    bind_agent_state(seed_state)
    seed_schedule_v2 = DailySchedule(
        date=date(2026, 10, 10),
        time_blocks=[
            TimeBlock(start_time=time(9, 0), end_time=time(10, 0), label="Team Sync"),
            TimeBlock(start_time=time(10, 0), end_time=time(11, 30), label="Write Proposal"),
            TimeBlock(start_time=time(11, 30), end_time=time(11, 40), label="Recovery Buffer", is_buffer=True),
        ],
        tasks_allocated=[
            TaskItem(title="Team Sync", category=TaskCategory.SHALLOW_WORK, estimated_minutes=60),
            TaskItem(title="Write Proposal", category=TaskCategory.DEEP_WORK, estimated_minutes=90),
        ],
        buffer_time_minutes=10,
    )
    seed_state.active_schedule = seed_schedule_v2
    save_schedule_to_storage(
        schedule=seed_schedule_v2,
        filepath=os.path.join(temp_dir, "v2.json"),
        change_summary="Added team sync before proposal",
        agent_state=seed_state,
    )
    session_store.save(seed_state)

    # Verify v2 is now active
    res = client.get(f"/api/schedule/{test_sess_id}")
    assert res.json()["current_version_id"] == 2
    assert len(res.json()["version_history"]) == 2
    print("[PASS] Test 5: Successfully saved version 2 snapshot")

    # Test rollback to v1
    res = client.post(
        f"/api/schedule/{test_sess_id}/rollback",
        json={"target_version_id": 1},
    )
    assert res.status_code == 200, f"Rollback failed: {res.text}"
    rb_data = res.json()
    assert rb_data["success"] is True
    assert rb_data["restored_version_id"] == 1
    assert rb_data["current_version_id"] == 1
    assert rb_data["schedule"]["time_blocks"][0]["label"] == "Write Proposal"
    print("[PASS] Test 6: POST /api/schedule/{session_id}/rollback restored version 1")

    # Clean up
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("\nALL FASTAPI INTEGRATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    run_api_tests()
