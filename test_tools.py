"""Comprehensive unit and mock tests for deterministic tools.

Verifies functionality, schema adherence, buffer insertion, and error handling.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import date, time

from schemas import TaskCategory, TaskItem, TaskPriority
from tools import (
    OPENAI_TOOL_SCHEMAS,
    calculate_schedule_blocks,
    parse_task_attributes,
    save_schedule_to_storage,
)


def run_all_tests() -> None:
    print("=" * 60)
    print("RUNNING DETERMINISTIC TOOLS TEST SUITE")
    print("=" * 60)

    # ---------------------------------------------------------
    # TEST 1: parse_task_attributes
    # ---------------------------------------------------------
    print("\n[TEST 1] Testing parse_task_attributes...")
    
    # 1.a: Deep work with duration & priority
    res1 = parse_task_attributes("Draft distributed systems RFC 90 mins high priority")
    assert res1["success"] is True, f"Failed res1: {res1['error']}"
    assert res1["data"]["category"] == TaskCategory.DEEP_WORK.value
    assert res1["data"]["estimated_minutes"] == 90
    assert res1["data"]["priority"] == TaskPriority.HIGH.value
    print("  [PASS] Case 1.a (Deep work, 90m, High): Passed")

    # 1.b: Errands with hours notation & urgent priority
    res2 = parse_task_attributes("Pick up groceries and dry cleaning 1.5 hours urgent")
    assert res2["success"] is True, f"Failed res2: {res2['error']}"
    assert res2["data"]["category"] == TaskCategory.ERRANDS.value
    assert res2["data"]["estimated_minutes"] == 90
    assert res2["data"]["priority"] == TaskPriority.CRITICAL.value
    print("  [PASS] Case 1.b (Errands, 1.5h, Critical): Passed")

    # 1.c: Health activity
    res3 = parse_task_attributes("Gym session workout 45m")
    assert res3["success"] is True, f"Failed res3: {res3['error']}"
    assert res3["data"]["category"] == TaskCategory.HEALTH.value
    assert res3["data"]["estimated_minutes"] == 45
    print("  [PASS] Case 1.c (Health, 45m, Medium): Passed")

    # 1.d: Error handling for empty input
    res_err = parse_task_attributes("   ")
    assert res_err["success"] is False
    assert "cannot be empty" in res_err["error"]
    print("  [PASS] Case 1.d (Empty input error handling): Passed")

    # ---------------------------------------------------------
    # TEST 2: calculate_schedule_blocks & buffer logic
    # ---------------------------------------------------------
    print("\n[TEST 2] Testing calculate_schedule_blocks...")

    tasks = [
        TaskItem(
            title="Deep Code Review",
            category=TaskCategory.DEEP_WORK,
            estimated_minutes=60,
            priority=TaskPriority.CRITICAL,
        ),
        TaskItem(
            title="Team Standup",
            category=TaskCategory.SHALLOW_WORK,
            estimated_minutes=30,
            priority=TaskPriority.HIGH,
        ),
        TaskItem(
            title="Gym Workout",
            category=TaskCategory.HEALTH,
            estimated_minutes=45,
            priority=TaskPriority.MEDIUM,
        ),
        TaskItem(
            title="Draft API Spec",
            category=TaskCategory.DEEP_WORK,
            estimated_minutes=90,
            priority=TaskPriority.HIGH,
        ),
    ]

    calc_res = calculate_schedule_blocks(
        tasks=tasks,
        start_time="09:00",
        end_time="14:00",
        schedule_date="2026-10-10",
    )
    assert calc_res["success"] is True, f"Failed calc: {calc_res['error']}"
    sched = calc_res["data"]
    blocks = sched["time_blocks"]
    
    print(f"  Generated {len(blocks)} blocks:")
    for b in blocks:
        prefix = "[BUFFER]" if b["is_buffer"] else "[TASK]  "
        print(f"    {prefix} {b['start_time']} - {b['end_time']} | {b['label']}")

    # Verify buffer inserted after Deep Work
    buffer_blocks = [b for b in blocks if b["is_buffer"]]
    assert len(buffer_blocks) >= 1, "Expected at least one recovery buffer after Deep Work"
    assert sched["buffer_time_minutes"] > 0
    print(f"  [PASS] Verified {len(buffer_blocks)} Deep Work recovery buffers ({sched['buffer_time_minutes']} min total)")

    # 2.b: Error handling for invalid time bounds
    err_calc = calculate_schedule_blocks(tasks=tasks, start_time="17:00", end_time="09:00")
    assert err_calc["success"] is False
    assert "must be strictly after start time" in err_calc["error"]
    print("  [PASS] Case 2.b (End time before start time error handling): Passed")

    # ---------------------------------------------------------
    # TEST 3: save_schedule_to_storage
    # ---------------------------------------------------------
    print("\n[TEST 3] Testing save_schedule_to_storage...")
    temp_dir = tempfile.mkdtemp()
    temp_file = os.path.join(temp_dir, "daily_schedule_test.json")
    try:
        save_res = save_schedule_to_storage(schedule=sched, filepath=temp_file)
        assert save_res["success"] is True, f"Failed save: {save_res['error']}"
        assert os.path.exists(temp_file), "File was not written"
        assert save_res["data"]["size_bytes"] > 0
        
        # Verify JSON contents can be loaded
        with open(temp_file, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        assert loaded_data["date"] == "2026-10-10"
        assert len(loaded_data["time_blocks"]) == len(blocks)
        print(f"  [PASS] Case 3.a (Saved {save_res['data']['size_bytes']} bytes to JSON): Passed")

        # 3.b: Error handling for invalid path
        save_err = save_schedule_to_storage(schedule=sched, filepath="")
        assert save_err["success"] is False
        assert "cannot be empty" in save_err["error"]
        print("  [PASS] Case 3.b (Empty filepath error handling): Passed")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    # ---------------------------------------------------------
    # TEST 4: OpenAI Tool Schemas Structure
    # ---------------------------------------------------------
    print("\n[TEST 4] Testing OpenAI Tool Schemas export...")
    assert len(OPENAI_TOOL_SCHEMAS) == 4
    tool_names = [t["function"]["name"] for t in OPENAI_TOOL_SCHEMAS]
    assert "parse_task_attributes" in tool_names
    assert "calculate_schedule_blocks" in tool_names
    assert "save_schedule_to_storage" in tool_names
    assert "revert_schedule_to_version" in tool_names
    for schema in OPENAI_TOOL_SCHEMAS:
        assert schema["type"] == "function"
        assert "parameters" in schema["function"]
        assert "properties" in schema["function"]["parameters"]
    print(f"  [PASS] Case 4.a (OpenAI schemas verified for: {', '.join(tool_names)}): Passed")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
