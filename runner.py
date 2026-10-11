"""Agent execution runner implementing the single ReAct loop.

Manages conversational state, dispatches LLM inferences, executes tools,
handles recursive observations, and enforces circuit-breaker safety bounds.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Protocol
from uuid import uuid4

from agent_config import AgentConfig, FALLBACK_ITERATION_MESSAGE, MAX_ITERATIONS
from guardrails import (
    GuardrailViolation,
    ScheduleValidationViolation,
    post_execution_guardrail,
    pre_execution_guardrail,
)
from schemas import AgentState, ChatMessage, DailySchedule
from session_store import SQLiteSessionStore


@dataclass
class ToolCallRequest:
    """Standard representation of an LLM tool call request."""
    call_id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    """Normalized response payload from an LLM inference call."""
    content: Optional[str] = None
    thought: Optional[str] = None
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    action_chips: List[str] = field(default_factory=list)
    requires_date_selection: bool = False
    ui_action: Optional[str] = None
    default_task: Optional[str] = None


class LLMClient(Protocol):
    """Protocol for LLM client integration supporting tool use and structured chat."""
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        ...


class ConciergeRunner:
    """Production runner executing the ReAct loop for Daily Routine & Task Concierge."""

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        state: Optional[AgentState] = None,
        llm_client: Optional[LLMClient] = None,
        session_store: Optional[SQLiteSessionStore] = None,
        session_id: Optional[str] = None,
        max_iterations: int = MAX_ITERATIONS,
        verbose: bool = False,
    ) -> None:
        self.config = config or AgentConfig.create_default()
        self.llm_client = llm_client
        self.session_store = session_store
        chosen_iterations = (
            self.config.max_iterations
            if config is not None and max_iterations == MAX_ITERATIONS
            else max_iterations
        )
        self.max_iterations = min(chosen_iterations, MAX_ITERATIONS)
        self.verbose = verbose or os.getenv("CONCIERGE_DEBUG", "0").lower() in ("1", "true", "yes")

        # 1. State initialization and session restoration
        if state:
            self.state = state
        elif self.session_store and session_id and self.session_store.exists(session_id):
            loaded = self.session_store.load(session_id)
            self.state = loaded if loaded else AgentState(session_id=session_id)
        else:
            self.state = AgentState(session_id=session_id or str(uuid4()))

        # 2. Reconstruct raw message history for LLM context with dynamic temporal anchor
        current_local_now = datetime.now()
        dynamic_temporal_context = (
            f"\n\n# Current Temporal Reference\n"
            f"- Current Local Date: {current_local_now.strftime('%Y-%m-%d')}\n"
            f"- Current Local Time: {current_local_now.strftime('%H:%M')} (24-hour format)\n"
            f"- Current Day of Week: {current_local_now.strftime('%A')}\n"
        )
        full_system_prompt = self.config.system_prompt + dynamic_temporal_context

        self._raw_messages: List[Dict[str, Any]] = [
            {"role": "system", "content": full_system_prompt}
        ]
        for msg in self.state.message_history:
            self._raw_messages.append({"role": msg.role, "content": msg.content})

    def _persist_state(self) -> None:
        """Persist current state to session store if configured."""
        if self.session_store:
            try:
                self.session_store.save(self.state)
            except Exception as e:
                print(f"Warning: Failed to persist session state: {e}")

    def run(self, user_input: str) -> str:
        """Execute a full conversational turn through the ReAct loop until completion or circuit breaker.

        Args:
            user_input: Raw natural-language prompt or command from the user.

        Returns:
            The final assistant response text string.
        """
        # Refresh dynamic temporal context in system message
        current_local_now = datetime.now()
        dynamic_temporal_context = (
            f"\n\n# Current Temporal Reference\n"
            f"- Current Local Date: {current_local_now.strftime('%Y-%m-%d')}\n"
            f"- Current Local Time: {current_local_now.strftime('%H:%M')} (24-hour format)\n"
            f"- Current Day of Week: {current_local_now.strftime('%A')}\n"
        )
        if self._raw_messages and self._raw_messages[0]["role"] == "system":
            self._raw_messages[0]["content"] = self.config.system_prompt + dynamic_temporal_context
        # 1. Pre-Execution Guardrail (Injection and Off-Topic Check)
        is_valid, redirect_text = pre_execution_guardrail(user_input)
        if not is_valid:
            print(f"[GUARDRAIL_INTERCEPT] Pre-execution guardrail tripped for input: '{user_input[:50]}...'")
            # Update state with user input and guardrail redirection without calling LLM
            self.state.current_user_query = user_input
            self.state.message_history.append(
                ChatMessage(role="user", content=user_input, timestamp=datetime.now(timezone.utc))
            )
            self.state.message_history.append(
                ChatMessage(role="assistant", content=redirect_text or "", timestamp=datetime.now(timezone.utc))
            )
            self._raw_messages.append({"role": "user", "content": user_input})
            self._raw_messages.append({"role": "assistant", "content": redirect_text or ""})
            self._persist_state()
            return redirect_text or ""

        # 2. Update working memory and state history
        self.state.current_user_query = user_input
        self.state.message_history.append(
            ChatMessage(role="user", content=user_input, timestamp=datetime.now(timezone.utc))
        )
        self._raw_messages.append({"role": "user", "content": user_input})

        step = 0
        iteration = 0
        tool_schemas = self.config.tool_registry.get_all_schemas()

        while step < self.max_iterations:
            step += 1
            iteration = step

            # Check if LLM client is configured
            if not self.llm_client:
                raise RuntimeError(
                    "No LLMClient provided to ConciergeRunner. Pass a configured client to execute inferences."
                )

            # 2. Invoke Language Model
            response: LLMResponse = self.llm_client.generate(
                messages=self._raw_messages,
                tools=tool_schemas,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            # 3. Handle Chain of Thought Logging
            thought_text = response.thought or ""
            if not thought_text and response.content and response.content.startswith("Thought:"):
                # Extract thought prefix if model included it in content
                lines = response.content.split("\n", 1)
                thought_text = lines[0].replace("Thought:", "").strip()

            if thought_text and self.verbose:
                print(f"[THOUGHT] {thought_text}")

            # 4. Handle Terminal Assistant Message (No Tool Calls)
            if not response.tool_calls:
                final_text = response.content or ""
                self._raw_messages.append({"role": "assistant", "content": final_text})
                self.state.message_history.append(
                    ChatMessage(
                        role="assistant",
                        content=final_text,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
                self._persist_state()
                return final_text

            # 5. Handle Tool Call Dispatches
            # First, append the assistant's tool-call intention message to raw history
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.call_id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ],
            }
            self._raw_messages.append(assistant_msg)

            for tc in response.tool_calls:
                print(f"[ACTION: {tc.name}] Arguments: {json.dumps(tc.arguments)}")

                # Pre-save guardrail check for save_schedule_to_storage
                if tc.name == "save_schedule_to_storage":
                    sched_arg = tc.arguments.get("schedule")
                    try:
                        if isinstance(sched_arg, dict):
                            sched_to_check = DailySchedule(**sched_arg)
                        elif self.state.active_schedule:
                            sched_to_check = self.state.active_schedule
                        else:
                            sched_to_check = None

                        if sched_to_check:
                            post_execution_guardrail(sched_to_check)
                    except GuardrailViolation as gv:
                        print(f"[GUARDRAIL_INTERCEPT] Blocked schedule persistence due to guardrail violation: {gv}")
                        tool_output = {
                            "success": False,
                            "data": None,
                            "error": f"GuardrailViolation: Cannot save invalid schedule: {str(gv)}",
                        }
                    else:
                        tool_output = self.config.tool_registry.execute(name=tc.name, **tc.arguments)
                else:
                    # Safe Tool Execution via Registry
                    tool_output = self.config.tool_registry.execute(name=tc.name, **tc.arguments)

                # Post-Execution Guardrail Validation for generated schedule
                if tc.name == "calculate_schedule_blocks" and tool_output.get("success"):
                    try:
                        candidate_schedule = DailySchedule(**tool_output["data"])
                        post_execution_guardrail(candidate_schedule)
                        self.state.active_schedule = candidate_schedule
                    except GuardrailViolation as gv:
                        print(f"[GUARDRAIL_INTERCEPT] Post-execution guardrail caught violation: {gv}")
                        tool_output = {
                            "success": False,
                            "data": None,
                            "error": f"GuardrailViolation: Generated schedule violated safety guardrail: {str(gv)}",
                        }
                    except Exception as e:
                        print(f"Warning: Failed to parse schedule into AgentState: {e}")

                obs_summary = json.dumps(tool_output, default=str)
                print(f"[OBSERVATION: {tc.name}] Result: {obs_summary}")

                # Append tool observation message
                self._raw_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.call_id,
                    "name": tc.name,
                    "content": obs_summary,
                })
                self.state.message_history.append(
                    ChatMessage(
                        role="tool",
                        content=f"Tool '{tc.name}' result: {obs_summary}",
                        timestamp=datetime.now(timezone.utc),
                    )
                )

        # 6. Circuit Breaker Fallback
        circuit_msg = FALLBACK_ITERATION_MESSAGE
        print(
            f"[CIRCUIT_BREAKER] Reached maximum allowed iterations ({self.max_iterations}). "
            f"Fallback returned: {circuit_msg}"
        )
        self._raw_messages.append({"role": "assistant", "content": circuit_msg})
        self.state.message_history.append(
            ChatMessage(
                role="assistant",
                content=circuit_msg,
                timestamp=datetime.now(timezone.utc),
            )
        )
        self._persist_state()
        return circuit_msg
