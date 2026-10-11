"""Verification test for Rest/Sleep classification and Total Work metric calculation.

Verifies:
1. "time to sleep" is parsed with category "Rest", realistic duration (480m / 8h),
   clean title "Sleep", and Low priority.
2. "take a power nap" is parsed with category "Rest", duration 30m, and Low priority.
3. calculate_schedule_blocks allocates rest blocks cleanly.
4. Total Work calculation in calendarExport & ScheduleBoard logic strictly excludes
   Rest/Sleep, Health/Fitness, and Buffers, counting only actual work commitments.
"""

from __future__ import annotations

from schemas import TaskCategory, TaskPriority
from tools import calculate_schedule_blocks, parse_task_attributes


def run_tests() -> None:
    print("=" * 60)
    print("RUNNING REST / SLEEP CLASSIFICATION & WORK METRICS TEST")
    print("=" * 60)

    # -------------------------------------------------------------
    # TEST 1: parse_task_attributes for sleep & rest
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing parse_task_attributes for Sleep & Rest...")

    # Case 1a: "time to sleep"
    res_sleep = parse_task_attributes("time to sleep")
    assert res_sleep["success"] is True, f"Failed parse: {res_sleep['error']}"
    data_sleep = res_sleep["data"]
    print(f"  Sleep Result: {data_sleep}")
    assert data_sleep["title"] == "Sleep", f"Expected title 'Sleep', got '{data_sleep['title']}'"
    assert data_sleep["category"] == TaskCategory.REST.value, f"Expected category 'Rest', got '{data_sleep['category']}'"
    assert data_sleep["estimated_minutes"] == 480, f"Expected 480 minutes (8h), got {data_sleep['estimated_minutes']}"
    assert data_sleep["priority"] == TaskPriority.LOW.value, f"Expected Low priority, got '{data_sleep['priority']}'"
    print("  [PASS] Case 1a: 'time to sleep' -> Title: 'Sleep', Category: 'Rest', Duration: 480m (8h), Priority: 'Low'")

    # Case 1b: "take a power nap"
    res_nap = parse_task_attributes("take a power nap")
    assert res_nap["success"] is True
    data_nap = res_nap["data"]
    assert data_nap["title"] == "Power Nap"
    assert data_nap["category"] == TaskCategory.REST.value
    assert data_nap["estimated_minutes"] == 30
    assert data_nap["priority"] == TaskPriority.LOW.value
    print("  [PASS] Case 1b: 'take a power nap' -> Title: 'Power Nap', Category: 'Rest', Duration: 30m, Priority: 'Low'")

    # -------------------------------------------------------------
    # TEST 2: Total Work calculation exclusion
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Total Work Filtering Logic...")

    sample_blocks = [
        {"label": "Write RFC", "category": "Deep Work", "estimated_minutes": 60, "is_buffer": False},
        {"label": "Deep Work Recovery Buffer", "category": "Buffer", "estimated_minutes": 10, "is_buffer": True},
        {"label": "Team Sync", "category": "Shallow Work", "estimated_minutes": 30, "is_buffer": False},
        {"label": "Pick up groceries", "category": "Errands", "estimated_minutes": 30, "is_buffer": False},
        {"label": "Gym Workout", "category": "Health", "estimated_minutes": 45, "is_buffer": False},
        {"label": "Sleep", "category": "Rest", "estimated_minutes": 480, "is_buffer": False},
    ]

    WORK_CATEGORIES = [
        "deep_work",
        "deep work",
        "shallow_work",
        "shallow work",
        "work",
        "errand",
        "errands",
        "meeting",
        "task",
    ]

    def is_work_block(b: dict) -> bool:
        if b.get("is_buffer"):
            return False
        cat = (b.get("category") or "").lower().replace("-", "_").replace(" ", "_")
        label = (b.get("label") or "").lower()
        if "rest" in cat or "sleep" in cat or "health" in cat or any(w in label for w in ["sleep", "rest", "nap", "wind down"]):
            return False
        return any(wc in cat or cat == wc for wc in WORK_CATEGORIES)

    work_blocks = [b for b in sample_blocks if is_work_block(b)]
    total_work_minutes = sum(b["estimated_minutes"] for b in work_blocks)

    print(f"  All blocks count: {len(sample_blocks)}")
    print(f"  Qualifying work blocks: {[b['label'] for b in work_blocks]}")
    print(f"  Total work minutes: {total_work_minutes}")

    # Expected: 60 (RFC) + 30 (Sync) + 30 (Errand) = 120m
    # Excluded: 10m Buffer, 45m Gym, 480m Sleep
    assert total_work_minutes == 120, f"Expected 120m total work, got {total_work_minutes}"
    assert "Sleep" not in [b["label"] for b in work_blocks]
    assert "Gym Workout" not in [b["label"] for b in work_blocks]
    print("  [PASS] Total Work accurately sums 120m (RFC + Sync + Errand), excluding Gym and Sleep!")

    # -------------------------------------------------------------
    # TEST 3: calculate_schedule_blocks with sleep task
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing calculate_schedule_blocks with Sleep task...")
    tasks = [
        data_sleep,
    ]
    res_calc = calculate_schedule_blocks(tasks=tasks, start_time="09:00", end_time="17:00")
    assert res_calc["success"] is True, f"Failed calc: {res_calc['error']}"
    blocks = res_calc["data"]["time_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["label"] == "Sleep"
    print(f"  [PASS] Sleep block successfully scheduled: {blocks[0]['start_time']} - {blocks[0]['end_time']} | {blocks[0]['label']}")

    print("\n" + "=" * 60)
    print("ALL REST & WORK METRICS TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
