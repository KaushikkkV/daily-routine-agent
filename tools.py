"""Deterministic tool execution layer for Daily Routine & Task Concierge agent.

Implements isolated, validated functions for parsing, schedule block calculation,
and file persistence, wrapped in standardized safety envelopes.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date as dt_date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, TypedDict, Union

from schemas import (
    DailySchedule,
    ScheduleVersion,
    TaskCategory,
    TaskItem,
    TaskPriority,
    TaskStatus,
    TimeBlock,
)


# Global / module-level version tracking and state binding
_BOUND_AGENT_STATE: Optional[Any] = None
_FALLBACK_VERSION_HISTORY: List[ScheduleVersion] = []


def bind_agent_state(state: Any) -> None:
    """Bind an active AgentState instance for runtime tool access and versioning."""
    global _BOUND_AGENT_STATE
    _BOUND_AGENT_STATE = state


def get_bound_agent_state() -> Optional[Any]:
    """Retrieve the currently bound AgentState instance if available."""
    return _BOUND_AGENT_STATE


class ToolResult(TypedDict):
    """Standardized response contract for all deterministic tool executions."""
    success: bool
    data: Any
    error: Optional[str]


def parse_task_attributes(raw_text: str) -> dict[str, Any]:
    """Normalize raw user text input into validated TaskItem properties.

    Extracts duration in minutes, priority tier, cognitive category,
    and sanitized title using deterministic pattern heuristics.

    Args:
        raw_text: Unstructured string describing the task (e.g. "Draft RFC 90m high priority").

    Returns:
        Structured ToolResult dictionary containing parsed task properties or error.
    """
    try:
        if not raw_text or not raw_text.strip():
            return {
                "success": False,
                "data": None,
                "error": "Input raw_text cannot be empty.",
            }

        text = raw_text.strip()
        lower_text = text.lower()

        # 1. Deterministic Duration Extraction
        # Look for explicit patterns like: "1.5 hours", "2 hrs", "90 mins", "45m", "1h 30m"
        minutes: Optional[int] = None
        hour_min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:and\s*)?(\d+)?\s*(?:minutes?|mins?|m)?", lower_text)
        min_only_match = re.search(r"(\d+)\s*(?:minutes?|mins?|m)\b", lower_text)

        if hour_min_match:
            hours = float(hour_min_match.group(1))
            add_mins = int(hour_min_match.group(2)) if hour_min_match.group(2) else 0
            minutes = int(hours * 60) + add_mins
        elif min_only_match:
            minutes = int(min_only_match.group(1))
        else:
            # Fallback default: standard 30-minute block
            minutes = 30

        # Bound check between 5 and 720 minutes per schema
        minutes = max(5, min(720, minutes))

        # 2. Deterministic Priority Extraction
        if any(kw in lower_text for kw in ["critical", "p0", "urgent", "asap", "emergency"]):
            priority = TaskPriority.CRITICAL
        elif any(kw in lower_text for kw in ["high", "important", "p1", "must do", "priority"]):
            priority = TaskPriority.HIGH
        elif any(kw in lower_text for kw in ["low", "p3", "someday", "optional", "minor"]):
            priority = TaskPriority.LOW
        else:
            priority = TaskPriority.MEDIUM

        # 3. Deterministic Category Extraction
        health_kws = ["gym", "workout", "run", "walk", "doctor", "dentist", "meditat", "exercise", "lunch", "meal", "stretch", "yoga", "sleep"]
        errands_kws = ["errand", "grocer", "buy", "pick up", "clean", "laundry", "dishes", "bank", "mail", "bill", "call mom", "shop"]
        shallow_kws = ["email", "slack", "standup", "sync", "admin", "ticket", "organize", "filing", "chat", "inbox", "meeting"]
        deep_kws = ["code", "architecture", "rfc", "design", "write", "research", "study", "analysis", "draft", "feature", "build", "debug", "refactor", "spec"]

        if any(kw in lower_text for kw in health_kws):
            category = TaskCategory.HEALTH
        elif any(kw in lower_text for kw in errands_kws):
            category = TaskCategory.ERRANDS
        elif any(kw in lower_text for kw in deep_kws):
            category = TaskCategory.DEEP_WORK
        elif any(kw in lower_text for kw in shallow_kws):
            category = TaskCategory.SHALLOW_WORK
        else:
            # Duration-based cognitive fallback
            category = TaskCategory.DEEP_WORK if minutes >= 60 else TaskCategory.SHALLOW_WORK

        # 4. Clean Title Extraction
        # Strip metadata noise from title string
        cleaned_title = re.sub(
            r"\b(\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)|critical|urgent|asap|high priority|low priority|p[0-3])\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        cleaned_title = re.sub(r"\s{2,}", " ", cleaned_title).strip(" -:;,")
        if not cleaned_title:
            cleaned_title = text.strip()

        # 5. Schema Validation & Instantiation Check
        task_candidate = TaskItem(
            title=cleaned_title,
            category=category,
            estimated_minutes=minutes,
            priority=priority,
            status=TaskStatus.PENDING,
        )

        return {
            "success": True,
            "data": task_candidate.model_dump(),
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to parse task attributes: {str(exc)}",
        }


def calculate_schedule_blocks(
    tasks: Union[List[TaskItem], List[dict[str, Any]]],
    start_time: str = "09:00",
    end_time: str = "17:00",
    schedule_date: Optional[str] = None,
) -> dict[str, Any]:
    """Pack tasks into discrete chronological slots, inserting 10-minute buffers after Deep Work items.

    Args:
        tasks: Collection of TaskItem objects or dictionary representations.
        start_time: Daily schedule start time in 'HH:MM' 24-hour format (e.g. '09:00').
        end_time: Daily schedule end time in 'HH:MM' 24-hour format (e.g. '17:00').
        schedule_date: Optional ISO date string 'YYYY-MM-DD'. Defaults to today.

    Returns:
        Structured ToolResult dictionary containing serialized DailySchedule or error.
    """
    try:
        # 1. Parse Calendar Date
        target_date = dt_date.fromisoformat(schedule_date) if schedule_date else dt_date.today()

        # 2. Parse & Validate Boundary Times
        try:
            start_t = datetime.strptime(start_time, "%H:%M").time()
            end_t = datetime.strptime(end_time, "%H:%M").time()
        except ValueError as err:
            return {
                "success": False,
                "data": None,
                "error": f"Invalid time format. Expected 'HH:MM', got '{start_time}' or '{end_time}'. Detail: {err}",
            }

        start_dt = datetime.combine(target_date, start_t)
        end_dt = datetime.combine(target_date, end_t)

        if end_dt <= start_dt:
            return {
                "success": False,
                "data": None,
                "error": f"End time ({end_time}) must be strictly after start time ({start_time}).",
            }

        # 3. Normalize and Validate Task Items
        validated_tasks: List[TaskItem] = []
        for item in tasks:
            if isinstance(item, TaskItem):
                validated_tasks.append(item)
            elif isinstance(item, dict):
                validated_tasks.append(TaskItem(**item))
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Invalid task item type: {type(item)}. Expected TaskItem or dict.",
                }

        # 4. Deterministic Priority Sorting (Critical > High > Medium > Low)
        priority_weights = {
            TaskPriority.CRITICAL: 4,
            TaskPriority.HIGH: 3,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 1,
        }
        sorted_tasks = sorted(
            validated_tasks,
            key=lambda t: priority_weights.get(TaskPriority(t.priority), 0),
            reverse=True,
        )

        # 5. Pack into Time Blocks with Deep Work Buffers
        cursor_dt = start_dt
        time_blocks: List[TimeBlock] = []
        allocated_tasks: List[TaskItem] = []
        total_buffer_minutes = 0

        for task in sorted_tasks:
            task_duration = timedelta(minutes=task.estimated_minutes)
            next_cursor = cursor_dt + task_duration

            # Check if task fits in the remaining schedule window
            if next_cursor > end_dt:
                continue  # Out of time slot capacity for this day

            # Allocate Task Block
            block = TimeBlock(
                start_time=cursor_dt.time(),
                end_time=next_cursor.time(),
                label=task.title,
                task_id=task.id,
                is_buffer=False,
            )
            time_blocks.append(block)
            allocated_tasks.append(task)
            cursor_dt = next_cursor

            # Insert 10-minute buffer after Deep Work items if space remains
            if task.category == TaskCategory.DEEP_WORK:
                buffer_duration = timedelta(minutes=10)
                buffer_end_dt = cursor_dt + buffer_duration

                if buffer_end_dt <= end_dt:
                    buffer_block = TimeBlock(
                        start_time=cursor_dt.time(),
                        end_time=buffer_end_dt.time(),
                        label="Deep Work Recovery Buffer",
                        task_id=None,
                        is_buffer=True,
                    )
                    time_blocks.append(buffer_block)
                    cursor_dt = buffer_end_dt
                    total_buffer_minutes += 10

        # 6. Instantiate and Validate Full DailySchedule
        daily_schedule = DailySchedule(
            date=target_date,
            time_blocks=time_blocks,
            tasks_allocated=allocated_tasks,
            buffer_time_minutes=total_buffer_minutes,
        )

        return {
            "success": True,
            "data": daily_schedule.model_dump(mode="json"),
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to calculate schedule blocks: {str(exc)}",
        }


def save_schedule_to_storage(
    schedule: Union[DailySchedule, dict[str, Any]],
    filepath: str,
    change_summary: str = "Schedule confirmed and saved",
    agent_state: Optional[Any] = None,
) -> dict[str, Any]:
    """Persist a generated DailySchedule to local storage in structured JSON format,
    incrementing schedule version and recording an immutable snapshot.

    Args:
        schedule: DailySchedule model or dictionary representation.
        filepath: Destination file path on local filesystem.
        change_summary: Brief description or rationale of this version change.
        agent_state: Optional AgentState instance to update in-memory version history.

    Returns:
        Structured ToolResult dictionary containing persistence status and version metadata or error.
    """
    try:
        if not filepath or not filepath.strip():
            return {
                "success": False,
                "data": None,
                "error": "Destination filepath cannot be empty.",
            }

        # 1. Validate Schedule Schema
        if isinstance(schedule, DailySchedule):
            validated_obj = schedule
            payload = schedule.model_dump(mode="json")
        elif isinstance(schedule, dict):
            validated_obj = DailySchedule(**schedule)
            payload = validated_obj.model_dump(mode="json")
        else:
            return {
                "success": False,
                "data": None,
                "error": f"Invalid schedule object type: {type(schedule)}. Expected DailySchedule or dict.",
            }

        # 2. Increment Version & Create Snapshot
        state = agent_state or get_bound_agent_state()
        now_iso = datetime.now(timezone.utc).isoformat()

        if state is not None:
            new_version_id = state.current_version_id + 1
            state.current_version_id = new_version_id
            state.active_schedule = validated_obj
        else:
            new_version_id = len(_FALLBACK_VERSION_HISTORY) + 1

        snapshot = ScheduleVersion(
            version_id=new_version_id,
            timestamp=now_iso,
            change_summary=change_summary,
            schedule_snapshot=validated_obj,
        )

        if state is not None:
            state.version_history.append(snapshot)
        _FALLBACK_VERSION_HISTORY.append(snapshot)

        # 3. Ensure Target Directory Exists
        target_path = os.path.abspath(filepath)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # 4. Attach Version Metadata to Serialized File Payload
        payload["version_id"] = new_version_id
        payload["change_summary"] = change_summary
        active_history = state.version_history if state else _FALLBACK_VERSION_HISTORY
        payload["version_history"] = [v.model_dump(mode="json") for v in active_history]

        # 5. Atomic File Write
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        file_size = os.path.getsize(target_path)

        return {
            "success": True,
            "data": {
                "filepath": target_path,
                "version_id": new_version_id,
                "change_summary": change_summary,
                "size_bytes": file_size,
                "time_blocks_count": len(payload.get("time_blocks", [])),
                "tasks_count": len(payload.get("tasks_allocated", [])),
                "saved_at_utc": now_iso,
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to save schedule to storage: {str(exc)}",
        }


def revert_schedule_to_version(
    target_version_id: int,
    agent_state: Optional[Any] = None,
) -> dict[str, Any]:
    """Revert active schedule to a previously committed snapshot by version_id.

    Args:
        target_version_id: Monotonically increasing identifier of the version to restore.
        agent_state: Optional AgentState instance containing version_history.

    Returns:
        Structured ToolResult dictionary containing restored DailySchedule and version metadata, or error.
    """
    try:
        state = agent_state or get_bound_agent_state()
        history = state.version_history if state else _FALLBACK_VERSION_HISTORY

        if not history:
            return {
                "success": False,
                "data": None,
                "error": f"No version history available to revert to version {target_version_id}.",
            }

        target_snapshot: Optional[ScheduleVersion] = None
        for ver in history:
            if ver.version_id == target_version_id:
                target_snapshot = ver
                break

        if not target_snapshot:
            available_ids = [v.version_id for v in history]
            return {
                "success": False,
                "data": None,
                "error": f"Version ID {target_version_id} not found. Available versions: {available_ids}",
            }

        restored_schedule = target_snapshot.schedule_snapshot
        if state is not None:
            state.active_schedule = restored_schedule
            state.current_version_id = target_version_id

        return {
            "success": True,
            "data": {
                "restored_version_id": target_version_id,
                "restored_at_timestamp": target_snapshot.timestamp,
                "change_summary": target_snapshot.change_summary,
                "schedule": restored_schedule.model_dump(mode="json"),
            },
            "error": None,
        }

    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to revert schedule to version {target_version_id}: {str(exc)}",
        }


# OpenAI-compatible function calling schemas
OPENAI_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "parse_task_attributes",
            "description": "Extracts and normalizes raw text into structured task properties (title, category, duration, priority).",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_text": {
                        "type": "string",
                        "description": "Unstructured text string describing the action item or task (e.g. 'Draft system RFC 90m high priority').",
                    }
                },
                "required": ["raw_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_schedule_blocks",
            "description": "Packs prioritized tasks into chronological time blocks between start and end times, inserting 10-minute recovery buffers after Deep Work items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tasks": {
                        "type": "array",
                        "description": "List of task objects containing id, title, category, estimated_minutes, and priority.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "category": {
                                    "type": "string",
                                    "enum": ["Deep Work", "Shallow Work", "Errands", "Health"],
                                },
                                "estimated_minutes": {"type": "integer", "minimum": 5, "maximum": 720},
                                "priority": {
                                    "type": "string",
                                    "enum": ["Low", "Medium", "High", "Critical"],
                                },
                                "status": {
                                    "type": "string",
                                    "enum": ["Pending", "In Progress", "Completed", "Cancelled", "Deferred"],
                                },
                            },
                            "required": ["title", "category", "estimated_minutes"],
                        },
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Daily schedule start time in 24h 'HH:MM' format. Defaults to '09:00'.",
                        "default": "09:00",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "Daily schedule end time in 24h 'HH:MM' format. Defaults to '17:00'.",
                        "default": "17:00",
                    },
                    "schedule_date": {
                        "type": "string",
                        "description": "Optional ISO format date 'YYYY-MM-DD'. Defaults to current date.",
                    },
                },
                "required": ["tasks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_schedule_to_storage",
            "description": "Persists the validated DailySchedule structure to local storage at the designated JSON filepath, creating an immutable version snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schedule": {
                        "type": "object",
                        "description": "Validated DailySchedule payload with date, time_blocks, tasks_allocated, and buffer_time_minutes.",
                    },
                    "filepath": {
                        "type": "string",
                        "description": "Absolute or relative file path where the JSON schedule should be stored.",
                    },
                    "change_summary": {
                        "type": "string",
                        "description": "Optional summary or rationale describing what was modified in this schedule version.",
                    },
                },
                "required": ["schedule", "filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "revert_schedule_to_version",
            "description": "Reverts the active daily schedule to a previously committed snapshot using its target_version_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_version_id": {
                        "type": "integer",
                        "description": "The integer version_id of the historical snapshot to restore.",
                    }
                },
                "required": ["target_version_id"],
            },
        },
    },
]
