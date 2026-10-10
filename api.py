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
from runner import ConciergeRunner, LLMClient, LLMResponse, ToolCallRequest
from schemas import AgentState, DailySchedule, ScheduleVersion
from session_store import SQLiteSessionStore
from tools import (
    bind_agent_state,
    calculate_schedule_blocks,
    get_bound_agent_state,
    parse_task_attributes,
    revert_schedule_to_version,
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

        # 3. Check for previous tool responses in message history
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        last_tool = tool_msgs[-1] if tool_msgs else None

        # If calculate_schedule_blocks was just executed, present the schedule
        if last_tool and last_tool.get("name") == "calculate_schedule_blocks":
            try:
                obs_data = json.loads(last_tool.get("content", "{}"))
                if obs_data.get("success"):
                    sched = obs_data.get("data", {})
                    blocks = sched.get("time_blocks", [])
                    table_rows = []
                    for b in blocks:
                        notes = "Deep work focus" if not b.get("is_buffer") else "Recovery buffer"
                        table_rows.append(
                            f"| **{b.get('start_time')} - {b.get('end_time')}** | {b.get('label')} | {notes} |"
                        )
                    table_md = "\n".join(table_rows)
                    return LLMResponse(
                        thought=(
                            "Daily schedule calculated with deep-work recovery buffers. "
                            "Presenting proposed layout and awaiting user approval before persisting."
                        ),
                        content=(
                            f"Here is your proposed schedule for today:\n\n"
                            f"| Time Slot | Activity | Notes |\n"
                            f"| :--- | :--- | :--- |\n"
                            f"{table_md}\n\n"
                            f"Total buffer time: **{sched.get('buffer_time_minutes', 0)} mins**.\n\n"
                            f"**Do you confirm this schedule?** Please reply with 'Yes, save it' or click **Approve** to commit."
                        ),
                    )
            except Exception:
                pass

        # If parse_task_attributes was just run, call calculate_schedule_blocks
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
                today_str = dt_date.today().isoformat()
                return LLMResponse(
                    thought=(
                        "Tasks normalized into structured TaskItems. Packing into non-overlapping "
                        "chronological blocks starting at 09:00 with deep-work recovery buffers."
                    ),
                    tool_calls=[
                        ToolCallRequest(
                            call_id=f"call_calc_{uuid4().hex[:6]}",
                            name="calculate_schedule_blocks",
                            arguments={
                                "tasks": parsed_tasks,
                                "start_time": "09:00",
                                "end_time": "17:00",
                                "schedule_date": today_str,
                            },
                        )
                    ],
                )

        # 4. Check for ambiguous input (no duration hints)
        has_numbers = any(char.isdigit() for char in last_user)
        has_duration = any(kw in last_user_lower for kw in ["min", "hour", "hr", "m "])
        if not has_numbers and not has_duration and len(last_user.split()) > 3:
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

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        resp = self.inner.generate(messages, tools, temperature, max_tokens)

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

    return ChatResponse(
        reply=clean_reply,
        thought=isolated_thought,
        current_version_id=runner.state.current_version_id,
        pending_approval=pending_approval,
        schedule=runner.state.active_schedule,
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
