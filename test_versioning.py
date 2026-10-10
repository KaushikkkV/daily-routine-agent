"""Tests for schedule version control, event sourcing snapshots, and rollback capability."""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import date, time

from agent_config import AgentConfig
from schemas import AgentState, DailySchedule, ScheduleVersion, TaskCategory, TaskItem, TimeBlock
from tools import (
    OPENAI_TOOL_SCHEMAS,
    bind_agent_state,
    revert_schedule_to_version,
    save_schedule_to_storage,
)


def run_versioning_tests() -> None:
    print("=" * 60)
    print("RUNNING SCHEDULE VERSION CONTROL & ROLLBACK TEST SUITE")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "versioned_schedule.json")

    try:
        # Create initial agent state
        state = AgentState(session_id="test_versioning_sess")
        bind_agent_state(state)

        # -------------------------------------------------------------
        # TEST 1: Save Version 1
        # -------------------------------------------------------------
        sched_v1 = DailySchedule(
            date=date(2026, 10, 10),
            time_blocks=[
                TimeBlock(start_time=time(9, 0), end_time=time(10, 30), label="Draft Proposal"),
                TimeBlock(start_time=time(10, 30), end_time=time(10, 40), label="Recovery Buffer", is_buffer=True),
            ],
            tasks_allocated=[
                TaskItem(title="Draft Proposal", category=TaskCategory.DEEP_WORK, estimated_minutes=90)
            ],
            buffer_time_minutes=10,
        )

        res_v1 = save_schedule_to_storage(
            schedule=sched_v1,
            filepath=storage_path,
            change_summary="Initial morning plan with proposal",
            agent_state=state,
        )
        assert res_v1["success"] is True, f"Failed v1 save: {res_v1['error']}"
        assert state.current_version_id == 1
        assert len(state.version_history) == 1
        assert state.version_history[0].version_id == 1
        assert state.version_history[0].change_summary == "Initial morning plan with proposal"
        print("  [PASS] Test 1: Version 1 committed successfully.")

        # -------------------------------------------------------------
        # TEST 2: Save Version 2 (Mutated schedule with gym added)
        # -------------------------------------------------------------
        sched_v2 = DailySchedule(
            date=date(2026, 10, 10),
            time_blocks=[
                TimeBlock(start_time=time(9, 0), end_time=time(10, 30), label="Draft Proposal"),
                TimeBlock(start_time=time(10, 30), end_time=time(10, 40), label="Recovery Buffer", is_buffer=True),
                TimeBlock(start_time=time(10, 40), end_time=time(11, 25), label="Gym Workout"),
            ],
            tasks_allocated=[
                TaskItem(title="Draft Proposal", category=TaskCategory.DEEP_WORK, estimated_minutes=90),
                TaskItem(title="Gym Workout", category=TaskCategory.HEALTH, estimated_minutes=45),
            ],
            buffer_time_minutes=10,
        )

        res_v2 = save_schedule_to_storage(
            schedule=sched_v2,
            filepath=storage_path,
            change_summary="Added gym workout block",
            agent_state=state,
        )
        assert res_v2["success"] is True
        assert state.current_version_id == 2
        assert len(state.version_history) == 2
        assert len(state.active_schedule.time_blocks) == 3
        print("  [PASS] Test 2: Version 2 committed with 3 time blocks.")

        # -------------------------------------------------------------
        # TEST 3: Rollback / Revert to Version 1
        # -------------------------------------------------------------
        revert_res = revert_schedule_to_version(target_version_id=1, agent_state=state)
        assert revert_res["success"] is True, f"Failed revert: {revert_res['error']}"
        assert state.current_version_id == 1
        assert len(state.active_schedule.time_blocks) == 2
        assert state.active_schedule.time_blocks[-1].label == "Recovery Buffer"
        print("  [PASS] Test 3: Successfully rolled back to Version 1 (reset active schedule).")

        # -------------------------------------------------------------
        # TEST 4: Invalid Version Rollback Handling
        # -------------------------------------------------------------
        invalid_revert = revert_schedule_to_version(target_version_id=99, agent_state=state)
        assert invalid_revert["success"] is False
        assert "Version ID 99 not found" in invalid_revert["error"]
        print("  [PASS] Test 4: Caught non-existent version rollback with helpful error envelope.")

        # -------------------------------------------------------------
        # TEST 5: Verify Tool Registry and OpenAI Schema
        # -------------------------------------------------------------
        cfg = AgentConfig.create_default()
        tool_names = [s["function"]["name"] for s in cfg.tool_registry.get_all_schemas()]
        assert "revert_schedule_to_version" in tool_names
        print(f"  [PASS] Test 5: revert_schedule_to_version registered in default config tools: {tool_names}")

        print("\n" + "=" * 60)
        print("ALL VERSIONING & ROLLBACK TESTS PASSED!")
        print("=" * 60)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_versioning_tests()
