"""End-to-end tests for ConciergeRunner execution loop.

Tests tool dispatching, observation recursion, console logging format,
and circuit breaker boundary enforcement.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from agent_config import AgentConfig
from runner import ConciergeRunner, LLMClient, LLMResponse, ToolCallRequest
from schemas import AgentState


class MockLLMClient:
    """Mock LLM client simulating multi-step ReAct reasoning and tool invocations."""

    def __init__(self, script: List[LLMResponse]) -> None:
        self.script = script
        self.call_count = 0

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        if self.call_count < len(self.script):
            resp = self.script[self.call_count]
            self.call_count += 1
            return resp
        # Default fallback if script exhausted
        return LLMResponse(content="I have completed your schedule layout. Please review and confirm to save.")


class InfiniteLoopLLMClient:
    """Mock LLM that persistently issues tool calls to test circuit breaker tripping."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            thought=f"Looping step {self.call_count}, attempting to parse notes again.",
            tool_calls=[
                ToolCallRequest(
                    call_id=f"call_{self.call_count}",
                    name="parse_task_attributes",
                    arguments={"raw_text": f"Task item iteration {self.call_count}"},
                )
            ],
        )


def run_runner_tests() -> None:
    print("=" * 60)
    print("RUNNING RUNNER LOOP & CIRCUIT BREAKER TESTS")
    print("=" * 60)

    # -------------------------------------------------------------
    # TEST 1: Full multi-step ReAct Execution Flow
    # -------------------------------------------------------------
    print("\n[TEST 1] Testing standard multi-step ReAct flow...")

    scripted_steps = [
        # Step 1: Model reasons and decides to parse raw task strings
        LLMResponse(
            thought="Normalizing user's natural language input into structured task properties.",
            tool_calls=[
                ToolCallRequest(
                    call_id="call_parse_1",
                    name="parse_task_attributes",
                    arguments={"raw_text": "Draft System Architecture RFC 90m high priority"},
                ),
            ],
        ),
        # Step 2: Model receives parsed task, reasons about time slots, and calculates schedule blocks
        LLMResponse(
            thought="Task parsed successfully as Deep Work. Now packing into schedule starting at 09:00 with buffer.",
            tool_calls=[
                ToolCallRequest(
                    call_id="call_calc_1",
                    name="calculate_schedule_blocks",
                    arguments={
                        "tasks": [
                            {
                                "title": "Draft System Architecture RFC",
                                "category": "Deep Work",
                                "estimated_minutes": 90,
                                "priority": "High",
                            }
                        ],
                        "start_time": "09:00",
                        "end_time": "12:00",
                        "schedule_date": "2026-10-10",
                    },
                )
            ],
        ),
        # Step 3: Model presents proposed schedule to user and asks for explicit approval (Strict Boundary)
        LLMResponse(
            thought="Schedule blocks successfully calculated. Presenting to user for approval before saving to storage.",
            content=(
                "Here is your proposed schedule for today:\n"
                "- 09:00 - 10:30: Draft System Architecture RFC (Deep Work, 90m)\n"
                "- 10:30 - 10:40: Deep Work Recovery Buffer (10m)\n\n"
                "Do you approve this schedule? If confirmed, I will save it to storage."
            ),
        ),
    ]

    mock_client = MockLLMClient(script=scripted_steps)
    runner = ConciergeRunner(llm_client=mock_client)

    user_query = "Please schedule my morning: Draft System Architecture RFC 90m high priority between 9am and 12pm."
    final_output = runner.run(user_query)

    print("\n[FINAL AGENT OUTPUT]:\n" + final_output)

    # Assertions
    assert mock_client.call_count == 3
    assert runner.state.active_schedule is not None
    assert runner.state.active_schedule.buffer_time_minutes == 10
    assert len(runner.state.active_schedule.time_blocks) == 2
    assert len(runner.state.message_history) > 0
    print("  [PASS] Test 1 passed: Multi-step ReAct executed and active_schedule stored in state.")

    # -------------------------------------------------------------
    # TEST 2: Circuit Breaker Enforcement (max_iterations = 10)
    # -------------------------------------------------------------
    print("\n[TEST 2] Testing circuit breaker limit (max_iterations = 10)...")
    infinite_client = InfiniteLoopLLMClient()
    circuit_runner = ConciergeRunner(llm_client=infinite_client, max_iterations=10)

    circuit_result = circuit_runner.run("Keep analyzing my tasks.")
    print("\n[CIRCUIT BREAKER OUTPUT]: " + circuit_result)

    assert infinite_client.call_count == 10, f"Expected 10 calls, got {infinite_client.call_count}"
    assert (
        "I've processed part of your request, but needed more steps to finalize. Would you like me to continue?"
        in circuit_result
    )
    print("  [PASS] Test 2 passed: Circuit breaker tripped cleanly at iteration limit with graceful fallback.")

    print("\n" + "=" * 60)
    print("ALL RUNNER TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_runner_tests()
