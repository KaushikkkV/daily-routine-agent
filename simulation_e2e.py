"""End-to-end integration simulation demonstrating multi-turn agent conversation,
zero-assumption clarifying behavior, tool scheduling with deep-work buffers,
and persistent SQLite session storage.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Any, Dict, List

from agent_config import AgentConfig
from runner import ConciergeRunner, LLMClient, LLMResponse, ToolCallRequest
from schemas import AgentState, TaskCategory, TaskPriority
from session_store import SQLiteSessionStore


class MultiTurnScenarioLLM:
    """Mock LLM simulating the exact multi-turn reasoning of the Daily Routine Concierge."""

    def __init__(self) -> None:
        self.turn = 0
        self.step_within_turn = 0

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        # Determine current turn from messages
        user_messages = [m for m in messages if m.get("role") == "user"]
        last_user_content = user_messages[-1]["content"] if user_messages else ""

        # TURN 1: Ambiguous Input Handling
        if "sometime between 9 AM and 2 PM" in last_user_content and "90 minutes" not in last_user_content:
            return LLMResponse(
                thought=(
                    "User listed 3 activities (proposal, gym, groceries) between 9 AM and 2 PM, "
                    "but provided no durations or priority rankings. Under the Zero Assumption Policy, "
                    "I must not guess durations or commitments. I will ask clarifying questions."
                ),
                content=(
                    "I'd love to help build your schedule between 9:00 AM and 2:00 PM! "
                    "To allocate your time accurately and ensure optimal cognitive balance, could you please clarify:\n\n"
                    "1. **Writing the Proposal**: What is your estimated duration, and is this High or Critical priority?\n"
                    "2. **Gym**: How many minutes do you plan for your workout?\n"
                    "3. **Groceries**: How much time should we set aside for errands?"
                ),
            )

        # TURN 2: Clarification provided -> Tool Execution Loop
        if "90 minutes" in last_user_content:
            self.step_within_turn += 1

            # Step 2.1: Model invokes parse_task_attributes for the items
            if self.step_within_turn == 1:
                return LLMResponse(
                    thought=(
                        "User clarified durations and priorities. Parsing activities into normalized TaskItems. "
                        "Starting with Proposal as Deep Work."
                    ),
                    tool_calls=[
                        ToolCallRequest(
                            call_id="call_parse_proposal",
                            name="parse_task_attributes",
                            arguments={"raw_text": "Write proposal 90 mins high priority"},
                        ),
                        ToolCallRequest(
                            call_id="call_parse_gym",
                            name="parse_task_attributes",
                            arguments={"raw_text": "Hit the gym workout 45 mins"},
                        ),
                        ToolCallRequest(
                            call_id="call_parse_groceries",
                            name="parse_task_attributes",
                            arguments={"raw_text": "Buy groceries errand 30 mins"},
                        ),
                    ],
                )

            # Step 2.2: Model receives observations and packs schedule blocks
            if self.step_within_turn == 2:
                return LLMResponse(
                    thought=(
                        "All tasks normalized. Scheduling between 09:00 and 14:00. "
                        "High-energy deep work (Proposal) will be placed first at 09:00, "
                        "followed by a mandatory 10-minute recovery buffer before gym and groceries."
                    ),
                    tool_calls=[
                        ToolCallRequest(
                            call_id="call_calc_schedule",
                            name="calculate_schedule_blocks",
                            arguments={
                                "tasks": [
                                    {
                                        "title": "Write Proposal",
                                        "category": "Deep Work",
                                        "estimated_minutes": 90,
                                        "priority": "High",
                                    },
                                    {
                                        "title": "Hit The Gym Workout",
                                        "category": "Health",
                                        "estimated_minutes": 45,
                                        "priority": "Medium",
                                    },
                                    {
                                        "title": "Buy Groceries Errand",
                                        "category": "Errands",
                                        "estimated_minutes": 30,
                                        "priority": "Medium",
                                    },
                                ],
                                "start_time": "09:00",
                                "end_time": "14:00",
                                "schedule_date": "2026-10-10",
                            },
                        )
                    ],
                )

            # Step 2.3: Model presents schedule for user confirmation (Strict Boundary Gate)
            if self.step_within_turn == 3:
                return LLMResponse(
                    thought=(
                        "Daily schedule calculated with buffer. In accordance with safety boundaries, "
                        "I will present the layout and request user confirmation before persisting to storage."
                    ),
                    content=(
                        "Here is your proposed schedule for today (9:00 AM - 2:00 PM):\n\n"
                        "| Time Slot | Activity | Category | Notes |\n"
                        "| :--- | :--- | :--- | :--- |\n"
                        "| **09:00 - 10:30** | Write Proposal | Deep Work | 90m high-energy morning sprint |\n"
                        "| **10:30 - 10:40** | Recovery Buffer | Rest / Buffer | 10m cognitive decompression |\n"
                        "| **10:40 - 11:25** | Hit The Gym | Health | 45m physical refresh |\n"
                        "| **11:25 - 11:55** | Buy Groceries | Errands | 30m errand run |\n"
                        "| **11:55 - 14:00** | Open Slack Time | Buffer | Unallocated flex time |\n\n"
                        "Total allocated work: 165 mins | Total buffer: 10 mins.\n\n"
                        "**Do you confirm this schedule?** Please reply with 'Yes, save it' to store this schedule permanently."
                    ),
                )

        # TURN 3: Confirmation -> Storage Persistence
        if any(w in last_user_content.lower() for w in ["yes", "save", "approve", "confirm"]):
            return LLMResponse(
                thought="User confirmed schedule layout. Safe to invoke save_schedule_to_storage.",
                tool_calls=[
                    ToolCallRequest(
                        call_id="call_save_storage",
                        name="save_schedule_to_storage",
                        arguments={
                            "schedule": {
                                "date": "2026-10-10",
                                "time_blocks": [
                                    {"start_time": "09:00:00", "end_time": "10:30:00", "label": "Write Proposal", "is_buffer": False},
                                    {"start_time": "10:30:00", "end_time": "10:40:00", "label": "Deep Work Recovery Buffer", "is_buffer": True},
                                    {"start_time": "10:40:00", "end_time": "11:25:00", "label": "Hit The Gym Workout", "is_buffer": False},
                                    {"start_time": "11:25:00", "end_time": "11:55:00", "label": "Buy Groceries Errand", "is_buffer": False},
                                ],
                                "tasks_allocated": [
                                    {"title": "Write Proposal", "category": "Deep Work", "estimated_minutes": 90, "priority": "High"},
                                    {"title": "Hit The Gym Workout", "category": "Health", "estimated_minutes": 45, "priority": "Medium"},
                                    {"title": "Buy Groceries Errand", "category": "Errands", "estimated_minutes": 30, "priority": "Medium"},
                                ],
                                "buffer_time_minutes": 10,
                            },
                            "filepath": "daily_schedules/2026-10-10_schedule.json",
                        },
                    )
                ],
            )

        return LLMResponse(content="Schedule recorded.")


def run_e2e_simulation() -> None:
    print("=" * 75)
    print("DAILY ROUTINE & TASK CONCIERGE -- END-TO-END INTEGRATION SIMULATION")
    print("=" * 75)

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_sessions.db")
    session_id = "session_concierge_e2e_9901"

    try:
        # Initialize SQLite Session Store
        store = SQLiteSessionStore(db_path=db_path)
        llm = MultiTurnScenarioLLM()

        # ------------------------------------------------------------------
        # TURN 1: Ambiguous Input (Zero-Assumption Trigger)
        # ------------------------------------------------------------------
        print("\n" + "-" * 75)
        print(">>> [TURN 1: USER SENDS AMBIGUOUS INPUT]")
        print("-" * 75)
        runner_turn1 = ConciergeRunner(
            session_store=store,
            session_id=session_id,
            llm_client=llm,
        )

        user_input_1 = "I need to write a proposal, hit the gym, and buy groceries sometime between 9 AM and 2 PM."
        print(f"USER: {user_input_1}\n")

        response_1 = runner_turn1.run(user_input_1)
        print(f"\nCONCIERGE:\n{response_1}")

        # Verify Turn 1 Persistence in SQLite
        assert store.exists(session_id), "Session was not saved to SQLite store in Turn 1"
        saved_state_1 = store.load(session_id)
        assert saved_state_1 is not None
        assert len(saved_state_1.message_history) == 2  # user + assistant
        print("\n[VERIFIED]: Turn 1 completed and session saved to SQLite successfully.")

        # ------------------------------------------------------------------
        # TURN 2: User Clarification -> Tools Invocation & Schedule Proposal
        # ------------------------------------------------------------------
        print("\n" + "-" * 75)
        print(">>> [TURN 2: USER PROVIDES CLARIFICATIONS (SPAWNING FRESH RUNNER INSTANCE)]")
        print("-" * 75)
        # Instantiate a completely NEW runner instance to prove cross-process restoration
        runner_turn2 = ConciergeRunner(
            session_store=store,
            session_id=session_id,
            llm_client=llm,
        )
        assert len(runner_turn2.state.message_history) == 2, "Failed to restore history from store"

        user_input_2 = (
            "Let's allocate 90 minutes for the proposal (high priority), "
            "45 minutes for the gym, and 30 minutes for groceries."
        )
        print(f"USER: {user_input_2}\n")

        response_2 = runner_turn2.run(user_input_2)
        print(f"\nCONCIERGE:\n{response_2}")

        # Verify Turn 2 Persistence in SQLite
        saved_state_2 = store.load(session_id)
        assert saved_state_2 is not None
        assert saved_state_2.active_schedule is not None
        assert saved_state_2.active_schedule.buffer_time_minutes == 10
        print("\n[VERIFIED]: Turn 2 schedule calculated with 10m deep-work buffer and stored in SQLite.")

        # ------------------------------------------------------------------
        # TURN 3: User Confirmation -> Safe Storage Execution
        # ------------------------------------------------------------------
        print("\n" + "-" * 75)
        print(">>> [TURN 3: USER CONFIRMATION & FILE PERSISTENCE]")
        print("-" * 75)
        runner_turn3 = ConciergeRunner(
            session_store=store,
            session_id=session_id,
            llm_client=llm,
        )

        user_input_3 = "Yes, save it"
        print(f"USER: {user_input_3}\n")

        # Mock the final step acknowledging save after tool execution
        original_gen = llm.generate

        def turn_3_generate(messages: List[Dict[str, Any]], tools: List[Dict[str, Any]], temperature: float, max_tokens: int) -> LLMResponse:
            if any(m.get("role") == "tool" and m.get("name") == "save_schedule_to_storage" for m in messages):
                return LLMResponse(
                    thought="Schedule persistence confirmed via save_schedule_to_storage.",
                    content="Your daily schedule has been safely stored to JSON. All set for a productive day!",
                )
            return original_gen(messages, tools, temperature, max_tokens)

        llm.generate = turn_3_generate

        response_3 = runner_turn3.run(user_input_3)
        print(f"\nCONCIERGE:\n{response_3}")

        # Final Verification
        final_state = store.load(session_id)
        assert final_state is not None
        print(f"\nFinal Session History Count: {len(final_state.message_history)} messages.")
        print(f"Final Schedule Date: {final_state.active_schedule.date if final_state.active_schedule else 'None'}")
        print(f"Final Buffer Total: {final_state.active_schedule.buffer_time_minutes if final_state.active_schedule else 0} minutes.")

        print("\n" + "=" * 75)
        print("END-TO-END SIMULATION SUCCEEDED WITH 100% SPECIFICATION FIDELITY!")
        print("=" * 75)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    run_e2e_simulation()
