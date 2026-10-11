"""Comprehensive verification test for lifestyle tasks and relative-time parsing.

Verifies:
1. Pre-execution guardrail permits lifestyle tasks (gym, dinner, breaks) and blocks true off-topic queries.
2. parse_task_attributes correctly parses relative time offsets, extracts clean titles, and applies sensible default durations.
3. calculate_schedule_blocks correctly aligns time blocks with target_start_time.
4. End-to-end ConciergeRunner flow with SmartFallbackLLM.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from api import SmartFallbackLLM
from guardrails import pre_execution_guardrail
from runner import ConciergeRunner
from schemas import AgentState, TaskCategory
from tools import calculate_schedule_blocks, parse_task_attributes


def run_tests() -> None:
    print("=" * 60)
    print("RUNNING LIFESTYLE TASKS & RELATIVE TIME PARSING VERIFICATION")
    print("=" * 60)

    # -------------------------------------------------------------
    # TEST 1: Guardrail allowance for lifestyle activities
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing Guardrail Domain Rules for Lifestyle Tasks...")
    lifestyle_inputs = [
        "I want to go to gym",
        "need to cook dinner",
        "lunch break",
        "gym in 1 hour",
        "I have a meeting in 5 minutes",
        "take a quick rest",
        "do laundry and dishes",
        "evening walk and meditation",
    ]

    for inp in lifestyle_inputs:
        is_valid, err_msg = pre_execution_guardrail(inp)
        assert is_valid is True, f"Guardrail falsely rejected lifestyle input '{inp}': {err_msg}"
        print(f"  [PASS] Allowed: '{inp}'")

    off_topic_inputs = [
        "What is the capital of France?",
        "Tell me a joke about robots",
        "Write a poem about winter",
    ]
    for inp in off_topic_inputs:
        is_valid, err_msg = pre_execution_guardrail(inp)
        assert is_valid is False, f"Guardrail failed to intercept off-topic '{inp}'"
        assert "specialize exclusively in task scheduling" in err_msg
        print(f"  [PASS] Intercepted off-topic: '{inp}'")

    # -------------------------------------------------------------
    # TEST 2: parse_task_attributes title cleaning & sensible defaults
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing parse_task_attributes Relative Time & Clean Titles...")

    ref_time = "14:00"

    # Case 2a: "I have a meeting in 5 minutes"
    res_meeting = parse_task_attributes("I have a meeting in 5 minutes", reference_time=ref_time)
    assert res_meeting["success"] is True, f"Failed parse: {res_meeting['error']}"
    data_meeting = res_meeting["data"]
    print(f"  Meeting Result: {data_meeting}")
    assert data_meeting["title"] == "Meeting", f"Expected title 'Meeting', got '{data_meeting['title']}'"
    assert data_meeting["estimated_minutes"] == 30, f"Expected default 30 min duration for meeting, got {data_meeting['estimated_minutes']}"
    assert data_meeting["target_start_time"] == "14:05", f"Expected target_start_time '14:05', got '{data_meeting['target_start_time']}'"
    print("  [PASS] Case 2a: 'I have a meeting in 5 minutes' -> Title: 'Meeting', Duration: 30m, Start: 14:05")

    # Case 2b: "I want to go to gym"
    res_gym = parse_task_attributes("I want to go to gym", reference_time=ref_time)
    assert res_gym["success"] is True, f"Failed parse: {res_gym['error']}"
    data_gym = res_gym["data"]
    print(f"  Gym Result: {data_gym}")
    assert data_gym["title"] in ["Gym", "Gym Session"], f"Expected title 'Gym Session', got '{data_gym['title']}'"
    assert data_gym["estimated_minutes"] == 45, f"Expected default 45 min duration for gym, got {data_gym['estimated_minutes']}"
    assert data_gym["category"] == TaskCategory.HEALTH.value
    print("  [PASS] Case 2b: 'I want to go to gym' -> Title: 'Gym Session', Duration: 45m, Category: Health")

    # Case 2c: "need to cook dinner"
    res_dinner = parse_task_attributes("need to cook dinner", reference_time=ref_time)
    assert res_dinner["success"] is True, f"Failed parse: {res_dinner['error']}"
    data_dinner = res_dinner["data"]
    assert data_dinner["title"] in ["Cook Dinner", "Dinner Preparation", "Dinner"], f"Expected 'Dinner Preparation' or 'Cook Dinner', got '{data_dinner['title']}'"
    assert data_dinner["estimated_minutes"] == 45
    assert data_dinner["category"] == TaskCategory.HEALTH.value
    print("  [PASS] Case 2c: 'need to cook dinner' -> Title: 'Dinner Preparation' / 'Cook Dinner', Duration: 45m")

    # Case 2d: "gym in 1 hour"
    res_gym_offset = parse_task_attributes("gym in 1 hour", reference_time=ref_time)
    assert res_gym_offset["success"] is True
    data_gym_offset = res_gym_offset["data"]
    assert data_gym_offset["title"] in ["Gym", "Gym Session"]
    assert data_gym_offset["estimated_minutes"] == 45
    assert data_gym_offset["target_start_time"] == "15:00"
    print("  [PASS] Case 2d: 'gym in 1 hour' -> Title: 'Gym', Duration: 45m, Start: 15:00")

    # Case 2e: "meeting for 45 mins in 10 minutes"
    res_explicit = parse_task_attributes("meeting for 45 mins in 10 minutes", reference_time=ref_time)
    assert res_explicit["success"] is True
    data_explicit = res_explicit["data"]
    assert data_explicit["title"] == "Meeting"
    assert data_explicit["estimated_minutes"] == 45
    assert data_explicit["target_start_time"] == "14:10"
    print("  [PASS] Case 2e: 'meeting for 45 mins in 10 minutes' -> Title: 'Meeting', Duration: 45m, Start: 14:10")

    # -------------------------------------------------------------
    # TEST 3: calculate_schedule_blocks with target_start_time
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing calculate_schedule_blocks with target_start_time...")
    task_with_start = {
        "title": "Meeting",
        "category": "Shallow Work",
        "estimated_minutes": 30,
        "priority": "Medium",
        "target_start_time": "14:05",
    }
    calc_res = calculate_schedule_blocks(tasks=[task_with_start])
    assert calc_res["success"] is True, f"Failed calc: {calc_res['error']}"
    blocks = calc_res["data"]["time_blocks"]
    assert len(blocks) == 1
    assert blocks[0]["label"] == "Meeting"
    assert blocks[0]["start_time"] == "14:05:00"
    assert blocks[0]["end_time"] == "14:35:00"
    print("  [PASS] Block allocated correctly: 14:05:00 - 14:35:00 (Meeting)")

    # -------------------------------------------------------------
    # TEST 4: End-to-End Runner Execution with SmartFallbackLLM
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing End-to-End Runner with SmartFallbackLLM...")

    # Case 4a: "I have a meeting in 5 minutes" triggers clarification, then "30 mins" schedules
    runner = ConciergeRunner(llm_client=SmartFallbackLLM(), max_iterations=5)
    output = runner.run("I have a meeting in 5 minutes")
    print(f"  Runner Output (Meeting in 5 mins): {output[:80]}...")
    assert "noted the start time" in output and "specify the target end time or duration" in output
    print("  [PASS] Successfully triggered professional anchor-time clarification")
    output_turn2 = runner.run("30 mins")
    assert "Please review the interactive timeline" in output_turn2 or "organized your day" in output_turn2
    assert runner.state.active_schedule is not None
    active_blocks = runner.state.active_schedule.time_blocks
    assert len(active_blocks) >= 1
    assert active_blocks[0].label == "Meeting"
    print(f"  [PASS] Scheduled block after clarification: {active_blocks[0].start_time} - {active_blocks[0].end_time} | {active_blocks[0].label}")

    # Case 4b: "I want to go to gym" (Unanchored Habit / Proactive Elicitation Protocol)
    runner_gym = ConciergeRunner(llm_client=SmartFallbackLLM(), max_iterations=5)
    output_gym = runner_gym.run("I want to go to gym")
    print(f"  Runner Output (Gym Turn 1): {output_gym[:80]}...")
    assert (
        "What time would you prefer to schedule your Gym Session" in output_gym
        or "I'll help you schedule that" in output_gym
        or "I'll help you schedule Gym Session" in output_gym
        or "target date and time below" in output_gym.lower()
    )
    print("  [PASS] Turn 1 prompted consultative elicitation/clarification for unanchored gym request")

    output_gym_turn2 = runner_gym.run("Schedule Gym Session at 18:00 for 45m")
    assert runner_gym.state.active_schedule is not None
    gym_blocks = runner_gym.state.active_schedule.time_blocks
    assert len(gym_blocks) >= 1
    assert "Gym" in gym_blocks[0].label
    assert str(gym_blocks[0].start_time).startswith("18:00")
    print(f"  [PASS] Scheduled block after confirmation: {gym_blocks[0].start_time} - {gym_blocks[0].end_time} | {gym_blocks[0].label}")

    print("\n" + "=" * 60)
    print("ALL LIFESTYLE & RELATIVE TIME TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
