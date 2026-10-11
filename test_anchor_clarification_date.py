"""Validation test suite for anchor-time scheduling, professional boundary clarification, and future date resolution."""

import datetime
from agent_config import AgentConfig
from api import SmartFallbackLLM, CapturingLLMClient
from runner import ConciergeRunner
from schemas import AgentState
from tools import parse_task_attributes, calculate_schedule_blocks


def run_tests():
    print("=" * 60)
    print("RUNNING ANCHOR-TIME, CLARIFICATION & FUTURE DATE TEST SUITE")
    print("=" * 60)

    # -------------------------------------------------------------
    # 1. Exact Anchor Time Extraction
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing parse_task_attributes anchor times...")
    t1 = parse_task_attributes("set a meeting at 12")
    assert t1["success"] is True
    assert t1["data"]["title"] == "Meeting"
    assert t1["data"]["target_start_time"] == "12:00"
    assert t1["data"]["has_explicit_start"] is True
    assert t1["data"]["has_explicit_duration"] is False
    print("  [PASS] 'set a meeting at 12' -> Start: 12:00, Explicit Start: True, Explicit Dur: False")

    t2 = parse_task_attributes("sync at 3pm for 45m")
    assert t2["success"] is True
    assert t2["data"]["target_start_time"] == "15:00"
    assert t2["data"]["estimated_minutes"] == 45
    assert t2["data"]["has_explicit_duration"] is True
    print("  [PASS] 'sync at 3pm for 45m' -> Start: 15:00, Duration: 45m, Explicit Dur: True")

    t3 = parse_task_attributes("standup at 9:30 am for 15 mins")
    assert t3["success"] is True
    assert t3["data"]["target_start_time"] == "09:30"
    assert t3["data"]["estimated_minutes"] == 15
    print("  [PASS] 'standup at 9:30 am for 15 mins' -> Start: 09:30, Duration: 15m")

    # -------------------------------------------------------------
    # 2. Future Date Resolution
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing Future Date Resolution...")
    today = datetime.date.today()
    tomorrow_expected = (today + datetime.timedelta(days=1)).isoformat()
    next_week_expected = (today + datetime.timedelta(days=7)).isoformat()

    t_tomorrow = parse_task_attributes("focus block tomorrow at 10 for 1 hour")
    assert t_tomorrow["data"]["target_date"] == tomorrow_expected
    assert t_tomorrow["data"]["target_start_time"] == "10:00"
    print(f"  [PASS] 'tomorrow' resolved to {tomorrow_expected}")

    t_next_week = parse_task_attributes("architecture review next week at 14:00 for 90m")
    assert t_next_week["data"]["target_date"] == next_week_expected
    assert t_next_week["data"]["target_start_time"] == "14:00"
    assert t_next_week["data"]["estimated_minutes"] == 90
    print(f"  [PASS] 'next week' resolved to {next_week_expected}")

    # -------------------------------------------------------------
    # 3. Schedule Blocks Calculation with Anchor Time Honoring
    # -------------------------------------------------------------
    print("\n[TEST 3] Testing calculate_schedule_blocks honors anchor start time...")
    sched_res = calculate_schedule_blocks(tasks=[t2["data"]])
    assert sched_res["success"] is True
    blocks = sched_res["data"]["time_blocks"]
    assert len(blocks) >= 1
    assert blocks[0]["start_time"] == "15:00:00"
    assert blocks[0]["end_time"] == "15:45:00"
    print(f"  [PASS] Schedule block strictly anchored at: {blocks[0]['start_time']} - {blocks[0]['end_time']}")

    # -------------------------------------------------------------
    # 4. Multi-Turn Clarification Flow: "set a meeting at 12" -> "30 mins"
    # -------------------------------------------------------------
    print("\n[TEST 4] Testing Professional Clarification & Multi-Turn Resolution...")
    state = AgentState()
    base_llm = SmartFallbackLLM()
    capturing_llm = CapturingLLMClient(base_llm)
    runner = ConciergeRunner(
        config=AgentConfig.create_default(),
        state=state,
        llm_client=capturing_llm,
    )

    turn1_reply = runner.run("set a meeting at 12")
    assert "I have noted the start time at 12:00" in turn1_reply
    assert "specify the target end time or duration" in turn1_reply
    assert runner.state.active_schedule is None
    print(f"  [PASS] Turn 1 prompted consultative clarification:\n    '{turn1_reply}'")

    turn2_reply = runner.run("30 mins")
    assert runner.state.active_schedule is not None
    active_blocks = runner.state.active_schedule.time_blocks
    assert len(active_blocks) == 1
    assert active_blocks[0].start_time == datetime.time(12, 0)
    assert active_blocks[0].end_time == datetime.time(12, 30)
    assert active_blocks[0].label == "Meeting"
    print(f"  [PASS] Turn 2 committed schedule anchored at: {active_blocks[0].start_time} - {active_blocks[0].end_time} | {active_blocks[0].label}")

    print("\n" + "=" * 60)
    print("ALL ANCHOR-TIME, CLARIFICATION & FUTURE DATE TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
