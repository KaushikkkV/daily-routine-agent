"""FastAPI bridge server for Daily Routine & Task Concierge agent.

Exposes clean REST API endpoints for frontend consumption (React/shadcn-ui),
wrapping the ReAct execution runner, deterministic tools, guardrails,
and event-sourced schedule versioning.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date as dt_date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_config import AgentConfig
from guardrails import (
    get_casual_steering_response,
    is_casual_or_steering_input,
    is_incomplete_scheduling_request,
    is_unanchored_meeting_request,
)
from runner import ConciergeRunner, LLMClient, LLMResponse, ToolCallRequest
from schemas import AgentState, DailySchedule, ScheduleVersion
from session_store import SQLiteSessionStore
from tools import (
    bind_agent_state,
    calculate_schedule_blocks,
    get_bound_agent_state,
    is_chained_multitask_sequence,
    pack_chained_multitask_sequence,
    parse_task_attributes,
    revert_schedule_to_version,
    sanitize_task_title,
    save_schedule_to_storage,
)

# Load environment configuration (.env)
load_dotenv()

# ============================================================================
# FastAPI Application & CORS Setup
# ============================================================================

app = FastAPI(
    title="Daily Routine & Task Concierge API",
    description="Bridge API server wrapping ReAct agent runner and schedule versioning.",
    version="1.0.0",
)

# Enable CORS for local development environments
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Session Store
DB_PATH = os.getenv("CONCIERGE_DB_PATH", "concierge_sessions.db")
session_store = SQLiteSessionStore(db_path=DB_PATH)


# ============================================================================
# Request / Response Schemas
# ============================================================================

class ChatRequest(BaseModel):
    """Payload for conversational interaction turn."""
    session_id: str = Field(..., description="Unique identifier for the user session.")
    message: str = Field(..., min_length=1, description="User prompt or command string.")


class ChatResponse(BaseModel):
    """Structured response contract for chat interactions."""
    reply: str = Field(..., description="Clean concierge conversational message.")
    thought: Optional[str] = Field(None, description="Internal reasoning or thoughts.")
    current_version_id: int = Field(..., description="Active schedule version ID.")
    pending_approval: bool = Field(..., description="Whether a draft schedule awaits user approval.")
    schedule: Optional[DailySchedule] = Field(None, description="Active schedule object or null.")
    action_chips: List[str] = Field(default_factory=list, description="Action chips for quick interactive selection.")
    requires_date_selection: bool = Field(default=False, description="Whether inline generative date picker should render.")
    ui_action: Optional[str] = Field(None, description="Directive for frontend UI, e.g. show_date_time_picker.")
    default_task: Optional[str] = Field(None, description="Clean task title for interactive date/time picker.")


class ScheduleResponse(BaseModel):
    """Response contract returning active schedule and audit snapshots."""
    session_id: str
    current_version_id: int
    schedule: Optional[DailySchedule] = None
    version_history: List[ScheduleVersion] = []


class RollbackRequest(BaseModel):
    """Payload to revert schedule to an earlier version snapshot."""
    target_version_id: int = Field(..., ge=1, description="Version ID to restore.")


class RollbackResponse(BaseModel):
    """Response returned upon schedule reversion."""
    success: bool
    message: str
    restored_version_id: int
    current_version_id: int
    schedule: Optional[DailySchedule] = None
    version_history: List[ScheduleVersion] = []


class ApproveResponse(BaseModel):
    """Response returned upon committing pending draft schedule."""
    success: bool
    message: str
    session_id: str
    current_version_id: int
    pending_approval: bool
    schedule: Optional[DailySchedule] = None
    version_history: List[ScheduleVersion] = []


# ============================================================================
# LLM Client Implementations (Live OpenAI/Groq with Heuristic Fallback)
# ============================================================================

class SmartFallbackLLM:
    """Heuristic fallback LLM simulating the Concierge agent workflow.

    Activated when no valid live API key is configured or when external inference
    fails, ensuring 100% offline uptime and seamless local UI development.
    """

    def __init__(self) -> None:
        self.step = 0

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        self.step += 1
        user_msgs = [m for m in messages if m.get("role") == "user"]
        last_user = user_msgs[-1]["content"] if user_msgs else ""
        last_user_lower = last_user.lower()

        # 1. Approval / Confirmation check
        if any(w in last_user_lower for w in ["yes", "save", "approve", "confirm", "commit"]):
            bound_state = get_bound_agent_state()
            if bound_state and bound_state.active_schedule:
                sched_data = bound_state.active_schedule.model_dump(mode="json")
                return LLMResponse(
                    thought="User gave explicit approval to save the schedule. Invoking save_schedule_to_storage.",
                    tool_calls=[
                        ToolCallRequest(
                            call_id=f"call_save_{uuid4().hex[:6]}",
                            name="save_schedule_to_storage",
                            arguments={
                                "schedule": sched_data,
                                "filepath": f"daily_schedules/{sched_data.get('date', 'today')}_schedule.json",
                                "change_summary": "Schedule approved and committed to storage.",
                            },
                        )
                    ],
                )
            return LLMResponse(
                thought="User confirmed, but no active schedule was found in working memory.",
                content="No pending schedule found to save. Please share your tasks and I'll generate a plan for you!",
            )

        # 2. Rollback / Revert check
        if any(w in last_user_lower for w in ["rollback", "revert", "undo"]):
            version_match = re.search(r"version\s*(\d+)", last_user_lower)
            target_id = int(version_match.group(1)) if version_match else 1
            return LLMResponse(
                thought=f"User requested schedule rollback to version {target_id}.",
                tool_calls=[
                    ToolCallRequest(
                        call_id=f"call_revert_{uuid4().hex[:6]}",
                        name="revert_schedule_to_version",
                        arguments={"target_version_id": target_id},
                    )
                ],
            )

        # 3. Check for tool responses from the current turn (after latest user message)
        last_user_idx = max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=0)
        current_turn_msgs = messages[last_user_idx:]
        tool_msgs = [m for m in current_turn_msgs if m.get("role") == "tool"]
        last_tool = tool_msgs[-1] if tool_msgs else None

        # If calculate_schedule_blocks was just executed, present the schedule
        if last_tool and last_tool.get("name") == "calculate_schedule_blocks":
            try:
                obs_data = json.loads(last_tool.get("content", "{}"))
                if obs_data.get("success"):
                    sched = obs_data.get("data", {})
                    buffer_mins = sched.get("buffer_time_minutes", 0)
                    blocks = sched.get("time_blocks", [])
                    task_names = [b.get("label") for b in blocks if not b.get("is_buffer")]
                    if len(task_names) > 1 and is_chained_multitask_sequence(last_user):
                        tasks_str = ", ".join(task_names)
                        start_str = blocks[0].get("start_time", "09:00")[:5] if blocks else "now"
                        return LLMResponse(
                            thought=f"Chained multi-task sequence packed into {len(blocks)} blocks starting at {start_str}. Directing user to review timeline.",
                            content=(
                                f"I've sequenced your {len(task_names)} activities starting at {start_str}: {tasks_str}. "
                                f"Please review the timeline on your Schedule Board to adjust or approve."
                            ),
                        )
                    return LLMResponse(
                        thought=(
                            "Daily schedule calculated with deep-work recovery buffers. "
                            "Directing user to review interactive timeline on the Schedule Board."
                        ),
                        content=(
                            f"I've organized your day with high-focus tasks scheduled during morning hours and added "
                            f"{buffer_mins} minutes of recovery buffers to protect your energy. "
                            f"Please review the interactive timeline in the right pane and let me know if you'd like to make adjustments or approve it."
                        ),
                    )
            except Exception:
                pass

        # If revert_schedule_to_version was just executed, present rollback confirmation
        if last_tool and last_tool.get("name") == "revert_schedule_to_version":
            try:
                obs_data = json.loads(last_tool.get("content", "{}"))
                if obs_data.get("success"):
                    restored_id = obs_data.get("data", {}).get("restored_version_id", 1)
                    return LLMResponse(
                        thought=f"Schedule restored to version {restored_id}. Directing user to review restored timeline.",
                        content=(
                            f"I've rolled back your schedule to version {restored_id}. "
                            f"Please review the restored timeline in the right pane to verify your time blocks."
                        ),
                    )
            except Exception:
                pass

        # If parse_task_attributes was just run, check for missing duration clarification or call calculate_schedule_blocks
        if tool_msgs and any(m.get("name") == "parse_task_attributes" for m in tool_msgs):
            parsed_tasks = []
            for m in tool_msgs:
                if m.get("name") == "parse_task_attributes":
                    try:
                        p_res = json.loads(m.get("content", "{}"))
                        if p_res.get("success") and p_res.get("data"):
                            parsed_tasks.append(p_res["data"])
                    except Exception:
                        pass

            if parsed_tasks:
                # Check for explicit anchor without duration: require professional clarification first!
                anchor_missing_duration = [
                    t for t in parsed_tasks
                    if t.get("has_explicit_start") and not t.get("has_explicit_duration")
                ]
                if anchor_missing_duration:
                    first_anchor = anchor_missing_duration[0]
                    anchor_time = first_anchor.get("target_start_time") or "the specified time"
                    return LLMResponse(
                        thought=f"Task '{first_anchor.get('title')}' specified at anchor time {anchor_time} without duration or end window. Inquiring for target duration before scheduling.",
                        content=f"I have noted the start time at {anchor_time}. Could you please specify the target end time or duration so I can block this accurately on your agenda?",
                    )

                # Unanchored Task Protocol for routine habits:
                # If a single routine/habit task is submitted without any start time or relative indicator,
                # do NOT automatically place it at 09:00.
                # Emit a structured clarification response with action chips metadata:
                # Text: "What time would you prefer to schedule your [TASK_TITLE]?"
                # Chips: ["Morning (07:00)", "Noon (12:30)", "Evening (18:00)", "Specify Time"]
                if len(parsed_tasks) == 1:
                    single_t = parsed_tasks[0]
                    t_title = single_t.get("title", "Task")
                    t_cat = single_t.get("category", "")
                    has_start = single_t.get("has_explicit_start", False)
                    target_start = single_t.get("target_start_time")

                    habit_keywords = [
                        "gym", "workout", "exercise", "lunch", "dinner", "breakfast", "meal",
                        "walk", "chores", "clean", "grocer", "nap", "sleep", "session", "run"
                    ]
                    is_habit = (
                        t_cat in ["Health", "Rest", "Errands"]
                        or any(hk in t_title.lower() for hk in habit_keywords)
                    )

                    if not has_start and not target_start and is_habit and not single_t.get("target_date"):
                        return LLMResponse(
                            thought=(
                                f"Single unanchored habit/routine task '{t_title}' detected without start time anchor. "
                                f"In accordance with Unanchored Task Protocol, prompting user with consultative time clarification chips."
                            ),
                            content=f"What time would you prefer to schedule your {t_title}?",
                            action_chips=["Morning (07:00)", "Noon (12:30)", "Evening (18:00)", "Specify Time"],
                            requires_date_selection=False,
                        )

                today_str = dt_date.today().isoformat()
                target_dates = [t.get("target_date") for t in parsed_tasks if t.get("target_date")]
                sched_date = target_dates[0] if target_dates else today_str

                target_starts = [
                    t.get("target_start_time")
                    for t in parsed_tasks
                    if t.get("target_start_time")
                ]
                start_time = target_starts[0] if target_starts else "09:00"
                end_time = "17:00"
                if start_time >= "16:00":
                    end_time = "23:59"

                return LLMResponse(
                    thought=(
                        f"Tasks normalized into structured TaskItems. Packing into non-overlapping "
                        f"chronological blocks for {sched_date} starting at {start_time} with deep-work recovery buffers."
                    ),
                    tool_calls=[
                        ToolCallRequest(
                            call_id=f"call_calc_{uuid4().hex[:6]}",
                            name="calculate_schedule_blocks",
                            arguments={
                                "tasks": parsed_tasks,
                                "start_time": start_time,
                                "end_time": end_time,
                                "schedule_date": sched_date,
                            },
                        )
                    ],
                )

        # 3.5. Check if user is replying with a duration to an anchor-time clarification
        prev_asst_msgs = [m for m in messages if m.get("role") == "assistant"]
        last_asst_msg = prev_asst_msgs[-1]["content"] if prev_asst_msgs else ""
        anchor_match = re.search(
            r"I have noted the start time at\s+([01]?\d|2[0-3]:[0-5]\d|\d{1,2}:\d{2})",
            last_asst_msg,
        )
        dur_match = re.search(
            r"\b(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b",
            last_user_lower,
        )
        if anchor_match and dur_match:
            anchor_time = anchor_match.group(1)
            prev_user_msgs = [m for m in messages if m.get("role") == "user"]
            prev_user_query = prev_user_msgs[-2]["content"] if len(prev_user_msgs) >= 2 else "Meeting"
            dur_val = float(dur_match.group(1))
            is_hours = any(h in dur_match.group(0).lower() for h in ["hour", "hr", "h"]) and "m" not in dur_match.group(0).lower()
            dur_minutes = int(dur_val * 60) if is_hours else int(dur_val)
            dur_minutes = max(5, min(720, dur_minutes))
            combined_text = f"{prev_user_query} for {dur_minutes} minutes"
            return LLMResponse(
                thought=f"User clarified duration ({dur_minutes}m) for commitment anchored at {anchor_time}. Normalizing task attributes.",
                tool_calls=[
                    ToolCallRequest(
                        call_id=f"call_parse_clarified_{uuid4().hex[:4]}",
                        name="parse_task_attributes",
                        arguments={"raw_text": combined_text},
                    )
                ],
            )

        # 3.6. Check if user is replying to an unanchored habit clarification
        habit_clarification_match = re.search(
            r"What time would you prefer to schedule your\s+([^?]+)\?",
            last_asst_msg,
            re.IGNORECASE,
        )
        if habit_clarification_match:
            habit_name = habit_clarification_match.group(1).strip()
            # If user selected "Specify Time"
            if "specify time" in last_user_lower:
                return LLMResponse(
                    thought=f"User requested to specify custom time for {habit_name}.",
                    content=f"Please enter your preferred start time for {habit_name} (for example: 'at 16:30' or 'at 07:45').",
                )
            # If user selected a chip or entered time e.g. "Morning (07:00)" or "Evening (18:00)" or "at 18:00" or "18:00"
            time_match = re.search(r"([01]?\d|2[0-3]):([0-5]\d)", last_user)
            if time_match:
                chosen_time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
                dur_minutes = 45
                if any(m in habit_name.lower() for m in ["lunch", "dinner"]):
                    dur_minutes = 45
                elif "breakfast" in habit_name.lower():
                    dur_minutes = 30
                elif "nap" in habit_name.lower():
                    dur_minutes = 30
                combined_text = f"Schedule {habit_name} at {chosen_time} for {dur_minutes} minutes"
                return LLMResponse(
                    thought=f"User selected time ({chosen_time}) for habit {habit_name}. Parsing task attributes.",
                    tool_calls=[
                        ToolCallRequest(
                            call_id=f"call_parse_habit_{uuid4().hex[:4]}",
                            name="parse_task_attributes",
                            arguments={"raw_text": combined_text},
                        )
                    ],
                )

        # 3.65. Consultative Concierge Steering for Casual / Ambiguous Talk
        casual_reply = get_casual_steering_response(last_user)
        if casual_reply:
            return LLMResponse(
                thought="Casual conversation, venting, or ambiguous state detected. Engaging with Executive Routine Concierge steering persona offering 2 actionable choices.",
                content=casual_reply,
                ui_action=None,
                requires_date_selection=False,
                default_task=None,
                action_chips=[],
            )

        # 3.66. Confirmation Gate: User responding to steering choices
        # Case A: Accepted recovery buffer / break
        break_triggers = [
            "schedule a 20-minute recovery buffer now", "schedule the break", "schedule a break",
            "20-minute recovery buffer now", "recovery buffer now", "schedule recovery buffer",
            "schedule a 15-minute reset buffer now", "15-minute reset buffer now", "reset buffer now",
            "schedule the reset buffer", "schedule reset buffer", "let's do recovery buffer",
            "take a break now", "block out 30 minutes for a quick reset now",
        ]
        if any(bt in last_user_lower for bt in break_triggers) or (
            ("recovery buffer" in last_user_lower or "reset buffer" in last_user_lower or "the break" in last_user_lower)
            and ("schedule" in last_user_lower or "now" in last_user_lower or "yes" in last_user_lower or "do" in last_user_lower)
        ):
            cur_time = datetime.now().strftime("%H:%M")
            dur = 20
            if "15" in last_user_lower:
                dur = 15
            elif "30" in last_user_lower:
                dur = 30
            task_item = {
                "id": str(uuid4()),
                "title": "Recovery Buffer",
                "category": "Rest",
                "estimated_minutes": dur,
                "priority": "Low",
                "status": "Pending",
                "target_start_time": cur_time,
                "target_date": dt_date.today().isoformat(),
                "has_explicit_start": True,
                "has_explicit_duration": True,
            }
            return LLMResponse(
                thought=f"User accepted recovery buffer option. Packing {dur}m Recovery Buffer starting at {cur_time}.",
                tool_calls=[
                    ToolCallRequest(
                        call_id=f"call_calc_buffer_{uuid4().hex[:6]}",
                        name="calculate_schedule_blocks",
                        arguments={
                            "tasks": [task_item],
                            "start_time": cur_time,
                            "end_time": "23:59",
                            "schedule_date": dt_date.today().isoformat(),
                        },
                    )
                ],
            )

        # Case B: Accepted wrap up early
        if any(wt in last_user_lower for wt in ["wrap up early", "wrap up today's remaining tasks early", "wrap up remaining tasks"]):
            return LLMResponse(
                thought="User chose to wrap up remaining tasks early.",
                content="Understood! Wrapping up today's commitments early so you can protect your energy and rest. Have a great evening!",
            )

        # Case C: Accepted map out focus blocks
        if any(mt in last_user_lower for mt in ["map out your focus blocks", "map out my focus blocks", "map out focus blocks"]):
            return LLMResponse(
                thought="User chose to map out focus blocks.",
                content="Ready whenever you are! What are the primary 2-3 focus blocks or priorities you'd like to tackle today?",
            )

        # 3.7. Chained Multi-Task Sequencing:
        if is_chained_multitask_sequence(last_user):
            pack_result = pack_chained_multitask_sequence(last_user)
            if pack_result.get("success") and pack_result.get("task_items"):
                task_items = pack_result["task_items"]
                anchor = pack_result.get("anchor_start", "09:00")
                sched_date = task_items[0].get("target_date") if task_items else dt_date.today().isoformat()
                return LLMResponse(
                    thought=(
                        f"Chained multi-task sequence detected with {len(task_items)} activities starting at anchor {anchor}. "
                        f"Invoking calculate_schedule_blocks to pack timeline in one pass without date picker."
                    ),
                    tool_calls=[
                        ToolCallRequest(
                            call_id=f"call_seq_{uuid4().hex[:6]}",
                            name="calculate_schedule_blocks",
                            arguments={
                                "tasks": task_items,
                                "start_time": anchor,
                                "end_time": "23:59",
                                "schedule_date": sched_date,
                            },
                        )
                    ],
                )

        # 3.8. Standalone Incomplete / Unanchored Scheduling Request:
        if is_incomplete_scheduling_request(last_user):
            clean_title = sanitize_task_title(last_user)
            return LLMResponse(
                thought=f"Standalone unanchored task '{clean_title}' detected without start time or date. Proactively eliciting date and time via enhanced inline picker card.",
                content=f"I'll help you schedule {clean_title}. Please select your target date and time below.",
                ui_action="show_date_time_picker",
                requires_date_selection=True,
                default_task=clean_title,
                action_chips=[],
            )

        # 3.8. Future Date Intent Detection:
        future_intent_phrases = [
            "schedule a meeting", "next week", "plan tomorrow", "book slot",
            "book a slot", "pick a date", "future schedule", "schedule future",
            "plan for next week", "plan for tomorrow", "schedule meeting"
        ]
        has_future_intent = any(phrase in last_user_lower for phrase in future_intent_phrases)
        has_date_and_dur = bool(re.search(r"\d{4}-\d{2}-\d{2}", last_user)) and bool(
            re.search(r"\b(?:for\s+)?\d+\s*(?:m|min|mins|minutes?|hour|hours?|h)\b", last_user_lower)
        )

        if has_future_intent and not has_date_and_dur:
            return LLMResponse(
                thought="User expressed future scheduling intent. Flagging requires_date_selection to render inline Generative UI date-picker card.",
                content="I can help you schedule that! Please select your target date and duration using the calendar card below:",
                ui_action="show_date_time_picker",
                requires_date_selection=True,
                action_chips=[],
            )

        # 4. Check for ambiguous input (no duration hints and no activity intention)
        lifestyle_or_action_kws = [
            "gym", "workout", "dinner", "lunch", "breakfast", "meal", "cook", "walk",
            "meeting", "sync", "call", "grocer", "laundry", "clean", "break", "rest",
            "want to", "need to", "have a", "plan to", "going to", "time to", "schedule", "exercise",
            "sleep", "bedtime", "nap",
        ]
        is_routine_or_action = any(kw in last_user_lower for kw in lifestyle_or_action_kws)
        has_numbers = any(char.isdigit() for char in last_user)
        has_duration = any(kw in last_user_lower for kw in ["min", "hour", "hr", "m "])
        if not is_routine_or_action and not has_numbers and not has_duration and len(last_user.split()) > 3:
            return LLMResponse(
                thought="User input is ambiguous and missing duration estimates. Under the Pragmatic Assumption Policy, asking 1 clarifying question.",
                content=(
                    "I would be glad to help organize your day! To build an optimal, energy-balanced schedule, "
                    "could you please clarify roughly how much time you'd like to allocate for your main priorities today?"
                ),
            )

        # 5. Extract tasks and invoke parse_task_attributes
        items = [line.strip("-•* ").strip() for line in re.split(r"[,;\n]", last_user) if line.strip("-•* ").strip()]
        if not items:
            items = [last_user]

        tool_calls = [
            ToolCallRequest(
                call_id=f"call_parse_{i}_{uuid4().hex[:4]}",
                name="parse_task_attributes",
                arguments={"raw_text": item},
            )
            for i, item in enumerate(items[:4])
        ]

        return LLMResponse(
            thought=f"Normalizing {len(tool_calls)} raw task items into validated domain TaskItems.",
            tool_calls=tool_calls,
        )


class OpenAILLMClient:
    """OpenAI-compatible HTTP LLM client supporting Groq, OpenAI, Ollama, and local servers."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        self.model_name = model_name or os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
        self.fallback = SmartFallbackLLM()

    def _is_live_configured(self) -> bool:
        """Check whether a realistic, non-placeholder API key is set."""
        if not self.api_key:
            return False
        placeholder_substrings = ["your_actual", "your_groq", "your_api_key", "placeholder", "xxx"]
        return not any(p in self.api_key.lower() for p in placeholder_substrings)

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Dispatch inference to OpenAI-compatible endpoint or fallback gracefully."""
        if not self._is_live_configured():
            return self.fallback.generate(messages, tools, temperature, max_tokens)

        endpoint = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "DailyRoutineConcierge/1.0",
        }

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            choice = data["choices"][0]["message"]
            content = choice.get("content")
            thought = choice.get("reasoning_content") or choice.get("reasoning")

            # Extract thought prefix if model embedded it in message body
            if not thought and content and content.startswith("Thought:"):
                lines = content.split("\n", 1)
                thought = lines[0].replace("Thought:", "").strip()
                content = lines[1].strip() if len(lines) > 1 else ""

            # Parse tool calls if present
            tool_calls: List[ToolCallRequest] = []
            for tc in choice.get("tool_calls", []):
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {}
                elif isinstance(args_raw, dict):
                    args = args_raw
                else:
                    args = {}

                tool_calls.append(
                    ToolCallRequest(
                        call_id=tc.get("id", str(uuid4())),
                        name=name,
                        arguments=args,
                    )
                )

            return LLMResponse(content=content, thought=thought, tool_calls=tool_calls)

        except urllib.error.HTTPError as he:
            error_body = he.read().decode("utf-8", errors="replace")
            print(f"[LLM WARNING] HTTP {he.code} from {endpoint}: {error_body}. Invoking heuristic fallback.")
            return self.fallback.generate(messages, tools, temperature, max_tokens)
        except Exception as exc:
            print(f"[LLM WARNING] Error calling live LLM ({exc}). Invoking heuristic fallback.")
            return self.fallback.generate(messages, tools, temperature, max_tokens)


class CapturingLLMClient:
    """Wrapper around LLMClient to intercept and capture all reasoning thoughts during a turn."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.captured_thoughts: List[str] = []
        self.action_chips: List[str] = []
        self.requires_date_selection: bool = False
        self.ui_action: Optional[str] = None
        self.default_task: Optional[str] = None

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        resp = self.inner.generate(messages, tools, temperature, max_tokens)
        if resp.action_chips:
            self.action_chips = list(resp.action_chips)
        if resp.requires_date_selection:
            self.requires_date_selection = True
        if resp.ui_action:
            self.ui_action = resp.ui_action
        if resp.default_task:
            self.default_task = resp.default_task

        # 1. Thought explicitly in response
        if resp.thought:
            self.captured_thoughts.append(resp.thought)
        # 2. Thought in content text
        elif resp.content and resp.content.startswith("Thought:"):
            first_line = resp.content.split("\n", 1)[0].replace("Thought:", "").strip()
            self.captured_thoughts.append(first_line)
        # 3. Informative tool dispatch summary
        elif resp.tool_calls:
            call_names = ", ".join(tc.name for tc in resp.tool_calls)
            self.captured_thoughts.append(f"Analyzing activities and executing tools: [{call_names}]")

        return resp


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/health")
async def health_check() -> Dict[str, str]:
    """Health status and timestamp ping endpoint."""
    return {
        "status": "healthy",
        "service": "Daily Routine & Task Concierge API",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Execute a conversational ReAct turn with the Concierge agent.

    Accepts session_id and user message, executes tool reasoning, updates persistent state,
    and returns isolated conversational reply, thoughts, active schedule, and approval status.
    """
    session_id = request.session_id.strip() or str(uuid4())
    user_message = request.message.strip()

    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User message cannot be empty.",
        )

    # 1. Restore or initialize agent state
    state = session_store.load(session_id)
    if not state:
        state = AgentState(session_id=session_id)

    # 2. Bind active agent state for tool access & versioning
    bind_agent_state(state)

    # 3. Set up runner with capturing LLM client
    base_llm = OpenAILLMClient()
    capturing_llm = CapturingLLMClient(inner=base_llm)
    agent_config = AgentConfig.create_default()

    runner = ConciergeRunner(
        config=agent_config,
        state=state,
        llm_client=capturing_llm,
        session_store=session_store,
        session_id=session_id,
    )

    # 4. Execute ReAct turn
    try:
        raw_reply = runner.run(user_message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent runner error: {str(exc)}",
        )

    # 5. Extract and isolate thoughts from conversational reply
    clean_reply = raw_reply
    extracted_thought = None

    if clean_reply.startswith("Thought:"):
        parts = clean_reply.split("\n\n", 1)
        if len(parts) > 1:
            extracted_thought = parts[0].replace("Thought:", "").strip()
            clean_reply = parts[1].strip()
        else:
            parts = clean_reply.split("\n", 1)
            if len(parts) > 1:
                extracted_thought = parts[0].replace("Thought:", "").strip()
                clean_reply = parts[1].strip()

    final_thought_list = list(capturing_llm.captured_thoughts)
    if extracted_thought and extracted_thought not in final_thought_list:
        final_thought_list.insert(0, extracted_thought)

    isolated_thought = "\n\n".join(final_thought_list) if final_thought_list else None

    # 6. Determine whether active schedule is pending user approval
    active_sched = runner.state.active_schedule
    pending_approval = False

    if active_sched is not None:
        if len(runner.state.version_history) == 0:
            # Active schedule exists with no committed snapshots
            pending_approval = True
        else:
            # Check if active schedule differs from the latest committed version snapshot
            latest_committed = runner.state.version_history[-1].schedule_snapshot
            if active_sched.model_dump() != latest_committed.model_dump():
                pending_approval = True
            else:
                pending_approval = False

        # Additional verification: Check confirmation cues in conversational message
        confirmation_keywords = ["confirm this schedule", "yes, save it", "approve", "confirm to save", "click approve"]
        if any(kw in clean_reply.lower() for kw in confirmation_keywords):
            pending_approval = True

    # 7. Persist updated state
    session_store.save(runner.state)

    # 8. Extract action chips & date selection intent
    action_chips = list(capturing_llm.action_chips)
    requires_date_selection = capturing_llm.requires_date_selection
    ui_action = capturing_llm.ui_action
    default_task = capturing_llm.default_task

    # 0. Casual / Ambiguous / Steering Inputs: Never emit ui_action or default_task!
    if is_casual_or_steering_input(user_message):
        ui_action = None
        requires_date_selection = False
        default_task = None
        casual_reply = get_casual_steering_response(user_message)
        if casual_reply:
            clean_reply = casual_reply
    # 1. Chained Multi-Task Sequences: Must pack timeline in one pass and NOT emit ui_action show_date_time_picker!
    elif is_chained_multitask_sequence(user_message):
        ui_action = None
        requires_date_selection = False
        default_task = None
    # 2. Standalone Incomplete / Unanchored Task:
    elif is_incomplete_scheduling_request(user_message):
        clean_title = sanitize_task_title(user_message)
        clean_reply = f"I'll help you schedule {clean_title}. Please select your target date and time below."
        ui_action = "show_date_time_picker"
        requires_date_selection = True
        default_task = clean_title
    elif ui_action == "show_date_time_picker":
        requires_date_selection = True

    # Safeguard: Habit clarification question in response
    if "what time would you prefer to schedule" in clean_reply.lower() and not action_chips:
        action_chips = ["Morning (07:00)", "Noon (12:30)", "Evening (18:00)", "Specify Time"]

    # Safeguard: Future date intent in user message
    future_intent_phrases = [
        "schedule a meeting", "next week", "plan tomorrow", "book slot",
        "book a slot", "pick a date", "future schedule"
    ]
    has_date_and_dur = bool(re.search(r"\d{4}-\d{2}-\d{2}", user_message)) and bool(
        re.search(r"\b(?:for\s+)?\d+\s*(?:m|min|mins|minutes?|hour|hours?|h)\b", user_message.lower())
    )
    if not is_casual_or_steering_input(user_message) and not is_chained_multitask_sequence(user_message) and any(phrase in user_message.lower() for phrase in future_intent_phrases) and not has_date_and_dur:
        requires_date_selection = True
        ui_action = ui_action or "show_date_time_picker"

    return ChatResponse(
        reply=clean_reply,
        thought=isolated_thought,
        current_version_id=runner.state.current_version_id,
        pending_approval=pending_approval,
        schedule=runner.state.active_schedule,
        action_chips=action_chips,
        requires_date_selection=requires_date_selection,
        ui_action=ui_action,
        default_task=default_task,
    )


@app.get("/api/schedule/{session_id}", response_model=ScheduleResponse)
async def get_schedule_endpoint(session_id: str) -> ScheduleResponse:
    """Retrieve the current active schedule and complete snapshot version history."""
    clean_session_id = session_id.strip()
    state = session_store.load(clean_session_id)

    if not state:
        # Return an empty schedule envelope to allow clean initial frontend rendering
        return ScheduleResponse(
            session_id=clean_session_id,
            current_version_id=0,
            schedule=None,
            version_history=[],
        )

    return ScheduleResponse(
        session_id=clean_session_id,
        current_version_id=state.current_version_id,
        schedule=state.active_schedule,
        version_history=state.version_history,
    )


@app.post("/api/schedule/{session_id}/rollback", response_model=RollbackResponse)
async def rollback_schedule_endpoint(session_id: str, request: RollbackRequest) -> RollbackResponse:
    """Revert active schedule to a previously committed version snapshot."""
    clean_session_id = session_id.strip()
    state = session_store.load(clean_session_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{clean_session_id}' not found.",
        )

    bind_agent_state(state)
    result = revert_schedule_to_version(
        target_version_id=request.target_version_id,
        agent_state=state,
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", f"Failed to restore version {request.target_version_id}."),
        )

    # Persist restored state back to session store
    session_store.save(state)

    return RollbackResponse(
        success=True,
        message=f"Successfully restored schedule to version {request.target_version_id}.",
        restored_version_id=request.target_version_id,
        current_version_id=state.current_version_id,
        schedule=state.active_schedule,
        version_history=state.version_history,
    )


@app.post("/api/schedule/{session_id}/approve", response_model=ApproveResponse)
async def approve_schedule_endpoint(session_id: str) -> ApproveResponse:
    """Commit and persist the active draft schedule to permanent storage."""
    clean_session_id = session_id.strip()
    state = session_store.load(clean_session_id)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{clean_session_id}' not found.",
        )

    if not state.active_schedule:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active draft schedule found to approve.",
        )

    # Bind state and invoke storage persistence
    bind_agent_state(state)
    sched_date = str(state.active_schedule.date)
    storage_path = f"daily_schedules/{clean_session_id}_{sched_date}.json"

    save_result = save_schedule_to_storage(
        schedule=state.active_schedule,
        filepath=storage_path,
        change_summary="Schedule approved and committed via UI dashboard.",
        agent_state=state,
    )

    if not save_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage commit failed: {save_result.get('error')}",
        )

    # Save finalized state to session database
    session_store.save(state)

    return ApproveResponse(
        success=True,
        message="Schedule approved and committed to storage.",
        session_id=clean_session_id,
        current_version_id=state.current_version_id,
        pending_approval=False,
        schedule=state.active_schedule,
        version_history=state.version_history,
    )


# ============================================================================
# Main Entrypoint
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
