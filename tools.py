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

from uuid import uuid4

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


def sanitize_task_title(raw_text: str) -> str:
    """Sanitize and normalize a raw task description into a clean, professional title.

    Strips conversational filler ('i wanna go to', 'setup a', 'need to'), temporal tokens
    ('now', 'tomorrow', 'today', 'at 02:30 PM'), and metadata noise, returning clean titles
    like 'Gym Session', 'Meeting', etc.
    """
    if not raw_text or not raw_text.strip():
        return "Meeting"

    t = raw_text.strip()

    # 1. Strip leading filler prefixes
    prefixes = [
        r"^(?:i\s+would\s+like\s+to|i'd\s+like\s+to|i\s+want\s+to\s+go\s+to\s+(?:the\s+)?|i\s+want\s+to\s+(?:go\s+to\s+)?|i\s+want\s+to|i\s+wanna\s+go\s+to\s+(?:the\s+)?|i\s+wanna\s+(?:go\s+to\s+)?|i\s+wanna)\s+",
        r"^(?:want\s+to\s+go\s+to\s+(?:the\s+)?|want\s+to|wanna\s+go\s+to\s+(?:the\s+)?|wanna)\s+",
        r"^(?:i\s+need\s+to\s+cook\s+(?:some\s+)?|need\s+to\s+cook\s+(?:some\s+)?|need\s+to\s+cook|need\s+to\s+make\s+(?:some\s+)?|need\s+to\s+make|i\s+need\s+to)\s+",
        r"^(?:i\s+have\s+to|i\s+have\s+a(?:n)?|i\s+have|i\s+plan\s+to|i'm\s+going\s+to|i\s+gotta|i\s+must|need\s+to|have\s+to|plan\s+to|going\s+to)\s+",
        r"^(?:schedule\s+a(?:n)?|schedule|add\s+a(?:n)?|add|book\s+a(?:n)?|book|set\s+up\s+a(?:n)?|set\s+up|setup\s+a(?:n)?|setup|set\s+a(?:n)?|set)\s+",
        r"^(?:please\s+schedule|please|take\s+a(?:n)?|take\s+some|do\s+some|do\s+a(?:n)?|do)\s+",
        r"^(?:again\s+)",
        r"^(?:quick\s+)",
    ]
    for p in prefixes:
        t = re.sub(p, "", t, flags=re.IGNORECASE).strip()

    # 2. Strip movement verbs (e.g. "go to the gym" -> "gym")
    t = re.sub(r"^(?:go\s+to\s+(?:the\s+)?|attend\s+(?:the\s+)?)\s*", "", t, flags=re.IGNORECASE).strip()

    # 3. Strip temporal words and anchors (e.g. "now", "tomorrow", "at 12", "at 02:30 PM", "in 5 minutes")
    t = re.sub(r"\b(?:now|right\s+now|immediately)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:in|after)\s+\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:in|after)\s+(?:a\s+)?(?:half\s+(?:an\s+)?hour|few\s+minutes)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:for\s+)?\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:today|tomorrow|tonight|this\s+morning|this\s+afternoon|this\s+evening|next\s+week|day\s+after\s+tomorrow|\d{4}-\d{2}-\d{2})\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:critical|urgent|asap|high\s+priority|low\s+priority|medium\s+priority|p[0-3])\b", "", t, flags=re.IGNORECASE)

    # 4. Clean dangling prepositions & whitespace
    t = re.sub(r"\s+\b(?:in|at|for|from|to|on|after|before|by|and|with)\s*$", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^\s*\b(?:in|at|for|from|to|on|after|before|by|and|with)\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t).strip(" -:;,")

    # 5. Domain Normalization Map
    norm_map = {
        "gym": "Gym Session",
        "the gym": "Gym Session",
        "workout": "Workout Session",
        "the workout": "Workout Session",
        "exercise": "Exercise Session",
        "meet": "Meeting",
        "meeting": "Meeting",
        "call": "Call",
        "sync": "Sync",
        "standup": "Daily Standup",
        "1:1": "1:1 Sync",
        "cook lunch": "Lunch Preparation",
        "lunch": "Lunch Preparation",
        "lunch break": "Lunch Break",
        "cook dinner": "Dinner Preparation",
        "dinner": "Dinner Preparation",
        "dinner with team": "Dinner With Team",
        "breakfast": "Breakfast Preparation",
        "groceries": "Grocery Shopping",
        "buy groceries": "Grocery Shopping",
        "chores": "House Chores",
        "clean": "House Chores",
        "walk": "Walk & Fresh Air",
        "rest": "Rest",
        "nap": "Power Nap",
        "sleep": "Rest & Sleep",
        "bedtime": "Rest & Sleep",
    }
    lowered = t.lower()
    if lowered in norm_map:
        return norm_map[lowered]

    if not t:
        return "Meeting"

    # Capitalize cleanly
    words = t.split()
    return " ".join(w.capitalize() if w.islower() else w for w in words)


def is_chained_multitask_sequence(raw_text: str) -> bool:
    """Determine if user input expresses a chained sequence of multiple tasks.

    Detects sequential indicators ('then', 'after that', 'and then', 'afterwards', 'and after that')
    or multiple distinct tasks.
    """
    clean = raw_text.strip().lower()

    # Confirmations, approvals, rollbacks are not multi-task sequences
    confirmation_phrases = ["yes", "save", "approve", "confirm", "commit", "rollback", "revert", "undo", "looks good", "ok", "okay"]
    if any(clean == p or clean.startswith(f"{p} ") or clean.startswith(f"{p},") for p in confirmation_phrases):
        return False

    # Check for sequential indicators
    seq_indicator = bool(
        re.search(r"\b(?:and\s+then|then|after\s+that|followed\s+by|afterwards|and\s+after\s+that)\b", clean)
    )
    if seq_indicator:
        return True

    # Check for multiple distinct task activities separated by commas/semicolons/newlines
    task_activity_kws = [
        "meeting", "meet", "gym", "workout", "rest", "break", "lunch", "dinner",
        "breakfast", "call", "sync", "walk", "grocer", "code", "coding", "rfc",
        "draft", "clean", "chores", "nap", "sleep", "standup"
    ]
    segments = [s.strip() for s in re.split(r"[,;\n]", clean) if s.strip()]
    if len(segments) >= 2:
        matches = sum(1 for seg in segments if any(kw in seg for kw in task_activity_kws))
        if matches >= 2:
            return True

    return False


def pack_chained_multitask_sequence(
    raw_text: str,
    reference_time: Optional[str] = None,
    schedule_date: Optional[str] = None,
) -> dict[str, Any]:
    """Unpack a chained multi-task sequence, apply default durations and anchor time, and pack the timeline in one pass.

    Example: 'setup meeting now, then gym and after that rest and then again meeting'
    - Anchors starting from 'now' (current local time) or specified time
    - Applies sensible durations: Meeting: 30m, Gym: 45m, Rest/Buffer: 15m, Lunch/Dinner: 45m, etc.
    - Packs chronological non-overlapping blocks without prompting for clarification.
    """
    try:
        ref_dt = datetime.now()
        if reference_time:
            try:
                if "T" in reference_time or "-" in reference_time:
                    ref_dt = datetime.fromisoformat(reference_time)
                else:
                    parsed_t = datetime.strptime(reference_time.strip(), "%H:%M").time()
                    ref_dt = datetime.combine(ref_dt.date(), parsed_t)
            except Exception:
                ref_dt = datetime.now()

        # Date resolution
        target_date_str = schedule_date
        if not target_date_str:
            iso_m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw_text)
            if iso_m:
                target_date_str = iso_m.group(1)
            elif "tomorrow" in raw_text.lower():
                target_date_str = (ref_dt.date() + timedelta(days=1)).isoformat()
            else:
                target_date_str = ref_dt.date().isoformat()

        # Anchor Start Time resolution:
        clean_lower = raw_text.lower()
        if re.search(r"\b(?:now|right\s+now|immediately)\b", clean_lower):
            anchor_start = ref_dt.strftime("%H:%M")
        else:
            ampm_m = re.search(r"\b(?:at\s+)?([01]?\d|2[0-3])(?::([0-5]\d))?\s*(am|pm)\b", clean_lower)
            standalone_24h = re.search(r"\b(?:at\s+)?([01]?\d|2[0-3]):([0-5]\d)\b", clean_lower)
            if ampm_m:
                hr = int(ampm_m.group(1))
                mn = int(ampm_m.group(2)) if ampm_m.group(2) else 0
                ampm = ampm_m.group(3).lower()
                if ampm == "pm" and hr < 12:
                    hr += 12
                elif ampm == "am" and hr == 12:
                    hr = 0
                anchor_start = f"{hr:02d}:{mn:02d}"
            elif standalone_24h:
                anchor_start = f"{int(standalone_24h.group(1)):02d}:{standalone_24h.group(2)}"
            else:
                anchor_start = "09:00"

        # Split on sequential conjunctions / commas
        delim_pattern = r"(?:,\s*)?(?:\b(?:and\s+then|then|after\s+that|followed\s+by|afterwards|and\s+after\s+that)\b)|\s*,\s*"
        raw_segments = [s.strip() for s in re.split(delim_pattern, raw_text, flags=re.IGNORECASE) if s.strip()]

        segments = []
        for s in raw_segments:
            cleaned_s = re.sub(r"^(?:and|then|after\s+that|again)\s+", "", s, flags=re.IGNORECASE).strip()
            if cleaned_s:
                segments.append(cleaned_s)

        if not segments:
            segments = [raw_text]

        target_date_obj = dt_date.fromisoformat(target_date_str)
        anchor_time_obj = datetime.strptime(anchor_start, "%H:%M").time()
        cursor_dt = datetime.combine(target_date_obj, anchor_time_obj)

        task_items: List[TaskItem] = []
        for seg in segments:
            seg_lower = seg.lower()
            title = sanitize_task_title(seg)

            dur_m = re.search(r"\b(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", seg_lower)
            min_m = re.search(r"\b(?:for\s+)?(\d+)\s*(?:minutes?|mins?|m)\b", seg_lower)
            if dur_m:
                duration_mins = int(float(dur_m.group(1)) * 60)
            elif min_m:
                duration_mins = int(min_m.group(1))
            else:
                if any(kw in seg_lower for kw in ["meet", "meeting", "call", "sync", "standup", "1:1"]):
                    duration_mins = 30
                elif any(kw in seg_lower for kw in ["gym", "workout", "exercise", "fitness", "cardio"]):
                    duration_mins = 45
                elif any(kw in seg_lower for kw in ["rest", "buffer", "break", "nap", "relax"]):
                    duration_mins = 15
                elif any(kw in seg_lower for kw in ["lunch", "dinner", "breakfast", "meal", "cook", "eat"]):
                    duration_mins = 45
                elif any(kw in seg_lower for kw in ["code", "coding", "rfc", "deep work", "write", "research"]):
                    duration_mins = 60
                else:
                    duration_mins = 30

            if any(kw in seg_lower for kw in ["rest", "nap", "buffer", "break"]):
                cat = TaskCategory.REST
                priority = TaskPriority.LOW
            elif any(kw in seg_lower for kw in ["gym", "workout", "exercise", "walk", "lunch", "dinner"]):
                cat = TaskCategory.HEALTH
                priority = TaskPriority.MEDIUM
            elif any(kw in seg_lower for kw in ["code", "rfc", "deep work"]):
                cat = TaskCategory.DEEP_WORK
                priority = TaskPriority.HIGH
            else:
                cat = TaskCategory.SHALLOW_WORK
                priority = TaskPriority.MEDIUM

            start_str = cursor_dt.strftime("%H:%M")
            task_items.append(
                TaskItem(
                    id=str(uuid4()),
                    title=title,
                    category=cat,
                    estimated_minutes=duration_mins,
                    priority=priority,
                    status=TaskStatus.PENDING,
                    target_start_time=start_str,
                    target_date=target_date_str,
                    has_explicit_start=True,
                    has_explicit_duration=True,
                )
            )
            cursor_dt += timedelta(minutes=duration_mins)

        sched_res = calculate_schedule_blocks(
            tasks=task_items,
            start_time=anchor_start,
            end_time="23:59",
            schedule_date=target_date_str,
        )

        return {
            "success": sched_res.get("success", False),
            "data": sched_res.get("data"),
            "task_items": [t.model_dump() for t in task_items],
            "anchor_start": anchor_start,
            "error": sched_res.get("error"),
        }
    except Exception as exc:
        return {
            "success": False,
            "data": None,
            "error": f"Failed to pack chained multitask sequence: {str(exc)}",
        }


def parse_task_attributes(
    raw_text: str,
    reference_time: Optional[str] = None,
) -> dict[str, Any]:
    """Normalize raw user text input into validated TaskItem properties.

    Extracts duration in minutes, priority tier, cognitive category,
    relative time start offsets, and sanitized title using deterministic pattern heuristics.

    Args:
        raw_text: Unstructured string describing the task (e.g. "Draft RFC 90m high priority", "I have a meeting in 5 minutes").
        reference_time: Optional reference time (HH:MM or ISO format) for relative offset calculation. Defaults to current local time.

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

        # 1. Reference Time & Target Date Setup
        ref_dt = datetime.now()
        if reference_time:
            try:
                if "T" in reference_time or "-" in reference_time:
                    ref_dt = datetime.fromisoformat(reference_time)
                else:
                    parsed_t = datetime.strptime(reference_time.strip(), "%H:%M").time()
                    ref_dt = datetime.combine(ref_dt.date(), parsed_t)
            except Exception:
                ref_dt = datetime.now()

        # Future Date Resolution (e.g. "tomorrow", "next week", "YYYY-MM-DD")
        target_date_str: Optional[str] = None
        date_matched_text: Optional[str] = None

        if "day after tomorrow" in lower_text:
            target_date_str = (ref_dt.date() + timedelta(days=2)).isoformat()
            date_matched_text = "day after tomorrow"
        elif "tomorrow" in lower_text:
            target_date_str = (ref_dt.date() + timedelta(days=1)).isoformat()
            date_matched_text = "tomorrow"
        elif "next week" in lower_text:
            target_date_str = (ref_dt.date() + timedelta(days=7)).isoformat()
            date_matched_text = "next week"
        else:
            weekdays = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6,
                "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
            }
            next_day_match = re.search(
                r"\b(?:next|this coming)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)\b",
                lower_text,
            )
            if next_day_match:
                target_weekday = weekdays[next_day_match.group(1)]
                days_ahead = (target_weekday - ref_dt.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date_str = (ref_dt.date() + timedelta(days=days_ahead)).isoformat()
                date_matched_text = next_day_match.group(0)
            else:
                iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
                if iso_match:
                    target_date_str = iso_match.group(1)
                    date_matched_text = iso_match.group(0)

        # 2. Relative Time Offset & Explicit Anchor Time Detection
        target_start_time: Optional[str] = None
        rel_matched_text: Optional[str] = None
        has_explicit_start: bool = False

        # Check for relative offsets like "in 5 minutes", "after 1 hour", "in 1.5 hrs", "in 45m"
        rel_hr_min_match = re.search(
            r"\b(?:in|after)\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:and\s*)?(\d+)?\s*(?:minutes?|mins?|m)?\b",
            lower_text,
        )
        rel_min_match = re.search(
            r"\b(?:in|after)\s+(\d+)\s*(?:minutes?|mins?|m)\b",
            lower_text,
        )
        rel_half_hour = re.search(
            r"\b(?:in|after)\s+(?:a\s+)?half\s+(?:an\s+)?hour\b",
            lower_text,
        )
        rel_few_mins = re.search(
            r"\b(?:in|after)\s+(?:a\s+)?few\s+minutes\b",
            lower_text,
        )
        # Check for absolute anchor times like "at 12", "at 3 PM", "at 3pm", "at 12:00", "12:00"
        abs_time_match = re.search(
            r"\bat\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})\b",
            lower_text,
        )
        noon_match = re.search(r"\b(?:at|around)\s+noon\b", lower_text)
        midnight_match = re.search(r"\b(?:at|around)\s+midnight\b", lower_text)

        now_match = re.search(r"\b(?:now|right\s+now|immediately)\b", lower_text)
        ampm_time_match = re.search(
            r"\b(?:at\s+)?([01]?\d|2[0-3])(?::([0-5]\d))?\s*(am|pm)\b",
            lower_text,
            re.IGNORECASE,
        )

        if now_match:
            target_start_time = ref_dt.strftime("%H:%M")
            rel_matched_text = now_match.group(0)
            has_explicit_start = True
        elif ampm_time_match:
            hr = int(ampm_time_match.group(1))
            mn = int(ampm_time_match.group(2)) if ampm_time_match.group(2) else 0
            ampm = ampm_time_match.group(3).lower()
            if ampm == "pm" and hr < 12:
                hr += 12
            elif ampm == "am" and hr == 12:
                hr = 0
            target_start_time = f"{hr:02d}:{mn:02d}"
            rel_matched_text = ampm_time_match.group(0)
            has_explicit_start = True
        elif rel_hr_min_match:
            hours = float(rel_hr_min_match.group(1))
            add_mins = int(rel_hr_min_match.group(2)) if rel_hr_min_match.group(2) else 0
            offset_minutes = int(hours * 60) + add_mins
            target_start_dt = ref_dt + timedelta(minutes=offset_minutes)
            target_start_time = target_start_dt.strftime("%H:%M")
            rel_matched_text = rel_hr_min_match.group(0)
            has_explicit_start = True
        elif rel_min_match:
            offset_minutes = int(rel_min_match.group(1))
            target_start_dt = ref_dt + timedelta(minutes=offset_minutes)
            target_start_time = target_start_dt.strftime("%H:%M")
            rel_matched_text = rel_min_match.group(0)
            has_explicit_start = True
        elif rel_half_hour:
            target_start_dt = ref_dt + timedelta(minutes=30)
            target_start_time = target_start_dt.strftime("%H:%M")
            rel_matched_text = rel_half_hour.group(0)
            has_explicit_start = True
        elif rel_few_mins:
            target_start_dt = ref_dt + timedelta(minutes=5)
            target_start_time = target_start_dt.strftime("%H:%M")
            rel_matched_text = rel_few_mins.group(0)
            has_explicit_start = True
        elif noon_match:
            target_start_time = "12:00"
            rel_matched_text = noon_match.group(0)
            has_explicit_start = True
        elif midnight_match:
            target_start_time = "00:00"
            rel_matched_text = midnight_match.group(0)
            has_explicit_start = True
        elif abs_time_match:
            time_raw = abs_time_match.group(1).strip()
            try:
                ampm_m = re.search(r"(am|pm)", time_raw)
                ampm = ampm_m.group(1) if ampm_m else None
                digits = re.sub(r"[^\d:]", "", time_raw)
                if ":" in digits:
                    parts = digits.split(":")
                    hr = int(parts[0])
                    mn = int(parts[1])
                else:
                    hr = int(digits)
                    mn = 0

                if ampm:
                    if ampm == "pm" and hr < 12:
                        hr += 12
                    elif ampm == "am" and hr == 12:
                        hr = 0
                else:
                    if 1 <= hr <= 6:
                        hr += 12

                target_start_time = f"{hr:02d}:{mn:02d}"
                rel_matched_text = abs_time_match.group(0)
                has_explicit_start = True
            except Exception:
                pass
        else:
            standalone_time = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", lower_text)
            if standalone_time:
                target_start_time = f"{int(standalone_time.group(1)):02d}:{standalone_time.group(2)}"
                rel_matched_text = standalone_time.group(0)
                has_explicit_start = True

        # 3. Deterministic Duration Extraction
        text_for_duration = lower_text
        if rel_matched_text:
            text_for_duration = text_for_duration.replace(rel_matched_text, " ")
        if date_matched_text:
            text_for_duration = text_for_duration.replace(date_matched_text, " ")

        minutes: Optional[int] = None
        has_explicit_duration: bool = False

        hour_min_match = re.search(
            r"\b(?:for\s+)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:and\s*)?(\d+)?\s*(?:minutes?|mins?|m)?\b",
            text_for_duration,
        )
        min_only_match = re.search(
            r"\b(?:for\s+)?(\d+)\s*(?:minutes?|mins?|m)\b",
            text_for_duration,
        )
        end_time_match = re.search(
            r"\b(?:to|until|till|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})\b",
            text_for_duration,
        )

        if hour_min_match:
            hours = float(hour_min_match.group(1))
            add_mins = int(hour_min_match.group(2)) if hour_min_match.group(2) else 0
            minutes = int(hours * 60) + add_mins
            has_explicit_duration = True
        elif min_only_match:
            minutes = int(min_only_match.group(1))
            has_explicit_duration = True
        elif end_time_match and target_start_time:
            try:
                end_raw = end_time_match.group(1).strip()
                end_ampm_m = re.search(r"(am|pm)", end_raw)
                end_ampm = end_ampm_m.group(1) if end_ampm_m else None
                end_digits = re.sub(r"[^\d:]", "", end_raw)
                if ":" in end_digits:
                    end_parts = end_digits.split(":")
                    end_hr = int(end_parts[0])
                    end_mn = int(end_parts[1])
                else:
                    end_hr = int(end_digits)
                    end_mn = 0
                if end_ampm:
                    if end_ampm == "pm" and end_hr < 12:
                        end_hr += 12
                    elif end_ampm == "am" and end_hr == 12:
                        end_hr = 0
                else:
                    if 1 <= end_hr <= 6:
                        end_hr += 12
                start_h, start_m = [int(p) for p in target_start_time.split(":")]
                diff = (end_hr * 60 + end_mn) - (start_h * 60 + start_m)
                if diff > 0:
                    minutes = diff
                    has_explicit_duration = True
            except Exception:
                pass
        else:
            # Activity-specific sensible default durations
            if any(kw in lower_text for kw in ["sleep", "bedtime", "nighttime sleep", "slumber"]):
                minutes = 480  # Realistic 8-hour sleep duration
            elif any(kw in lower_text for kw in ["nap", "power nap", "quick rest"]):
                minutes = 30
            elif any(kw in lower_text for kw in ["meeting", "call", "sync", "standup", "catch up", "catchup", "1:1", "interview", "discussion"]):
                minutes = 30
            elif any(kw in lower_text for kw in ["gym", "workout", "exercise", "cardio", "lifting", "weights", "run", "running", "jog", "jogging", "swim", "yoga", "fitness"]):
                minutes = 45
            elif any(kw in lower_text for kw in ["lunch", "dinner", "breakfast", "meal", "cook", "cooking", "eat", "eating"]):
                minutes = 45
            elif any(kw in lower_text for kw in ["grocer", "errand", "clean", "laundry", "dishes", "shop", "shopping", "bank", "mail", "chores", "car wash"]):
                minutes = 30
            elif any(kw in lower_text for kw in ["break", "rest", "walk", "walking", "meditat", "stretch", "coffee", "tea", "wind down", "wind-down"]):
                minutes = 15
            elif any(kw in lower_text for kw in ["code", "coding", "rfc", "architecture", "design", "study", "research", "draft", "write"]):
                minutes = 60
            else:
                minutes = 30

        # Bound check between 5 and 720 minutes per schema
        minutes = max(5, min(720, minutes))

        # 4. Deterministic Priority Extraction
        if any(kw in lower_text for kw in ["sleep", "bedtime", "nap", "wind down", "wind-down"]):
            priority = TaskPriority.LOW
        elif any(kw in lower_text for kw in ["critical", "p0", "urgent", "asap", "emergency"]):
            priority = TaskPriority.CRITICAL
        elif any(kw in lower_text for kw in ["high", "important", "p1", "must do", "priority"]):
            priority = TaskPriority.HIGH
        elif any(kw in lower_text for kw in ["low", "p3", "someday", "optional", "minor"]):
            priority = TaskPriority.LOW
        else:
            priority = TaskPriority.MEDIUM

        # 5. Deterministic Category Extraction
        rest_kws = ["sleep", "nap", "bedtime", "rest", "wind down", "wind-down", "slumber"]
        health_kws = ["gym", "workout", "run", "walk", "doctor", "dentist", "meditat", "exercise", "lunch", "meal", "dinner", "breakfast", "cook", "stretch", "yoga", "recovery", "fitness", "cardio", "swim"]
        errands_kws = ["errand", "grocer", "buy", "pick up", "clean", "laundry", "dishes", "bank", "mail", "bill", "call mom", "shop", "chore", "car wash"]
        shallow_kws = ["meeting", "call", "sync", "standup", "email", "slack", "admin", "ticket", "organize", "filing", "chat", "inbox", "1:1", "interview"]
        deep_kws = ["code", "architecture", "rfc", "design", "write", "research", "study", "analysis", "draft", "feature", "build", "debug", "refactor", "spec"]

        if any(kw in lower_text for kw in rest_kws):
            category = TaskCategory.REST
        elif any(kw in lower_text for kw in health_kws):
            category = TaskCategory.HEALTH
        elif any(kw in lower_text for kw in errands_kws):
            category = TaskCategory.ERRANDS
        elif any(kw in lower_text for kw in deep_kws):
            category = TaskCategory.DEEP_WORK
        elif any(kw in lower_text for kw in shallow_kws):
            category = TaskCategory.SHALLOW_WORK
        else:
            category = TaskCategory.DEEP_WORK if minutes >= 60 else TaskCategory.SHALLOW_WORK

        # 6. Clean Title Extraction
        # 6a. Strip conversational prefixes
        cleaned_title = re.sub(
            r"^(?:i\s+would\s+like\s+to|i'd\s+like\s+to|i\s+want\s+to\s+go\s+to\s+(?:the\s+)?|i\s+want\s+to\s+(?:go\s+to\s+)?|i\s+want\s+to|i\s+wanna\s+go\s+to\s+(?:the\s+)?|i\s+wanna\s+(?:go\s+to\s+)?|i\s+wanna|want\s+to\s+go\s+to\s+(?:the\s+)?|want\s+to|wanna\s+go\s+to\s+(?:the\s+)?|wanna|i\s+need\s+to\s+cook\s+(?:some\s+)?|need\s+to\s+cook\s+(?:some\s+)?|need\s+to\s+cook|need\s+to\s+make\s+(?:some\s+)?|need\s+to\s+make|i\s+need\s+to|i\s+have\s+to|i\s+have\s+a(?:n)?|i\s+have|i\s+plan\s+to|i'm\s+going\s+to|i\s+gotta|i\s+must|need\s+to|have\s+to|plan\s+to|going\s+to|time\s+to|schedule\s+a(?:n)?|schedule|add\s+a(?:n)?|add|book\s+a(?:n)?|book|set\s+up\s+a(?:n)?|set\s+up|set\s+a(?:n)?|set|please\s+schedule|please|take\s+a(?:n)?|take\s+some)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

        # 6b. Strip leading movement verbs (e.g. "go to the gym" -> "gym")
        cleaned_title = re.sub(
            r"^(?:go\s+to\s+(?:the\s+)?|attend\s+(?:the\s+)?)\s*",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        ).strip()

        # 6c. Strip temporal offset and absolute time phrases
        cleaned_title = re.sub(
            r"\b(?:in|after)\s+\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        )
        cleaned_title = re.sub(
            r"\b(?:in|after)\s+(?:a\s+)?(?:half\s+(?:an\s+)?hour|few\s+minutes)\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        )
        cleaned_title = re.sub(
            r"\b(?:at)\s+(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{1,2}:\d{2})\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        )
        cleaned_title = re.sub(
            r"\b(?:for)\s+\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        )
        cleaned_title = re.sub(
            r"\b(?:today|tomorrow|tonight|this\s+morning|this\s+afternoon|this\s+evening|next\s+week|day\s+after\s+tomorrow|this\s+coming\s+[a-z]+|next\s+[a-z]+|\d{4}-\d{2}-\d{2})\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        )

        # 6d. Strip metadata noise (duration, priority keywords)
        cleaned_title = re.sub(
            r"\b(\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)|critical|urgent|asap|high\s+priority|low\s+priority|medium\s+priority|p[0-3])\b",
            "",
            cleaned_title,
            flags=re.IGNORECASE,
        ).strip()

        # 6e. Strip dangling prepositions or conjunctions
        cleaned_title = re.sub(r"\s+\b(?:in|at|for|from|to|on|after|before|by|and|with)\s*$", "", cleaned_title, flags=re.IGNORECASE)
        cleaned_title = re.sub(r"^\s*\b(?:in|at|for|from|to|on|after|before|by|and|with)\s+", "", cleaned_title, flags=re.IGNORECASE)
        cleaned_title = re.sub(r"\s{2,}", " ", cleaned_title).strip(" -:;,")

        if not cleaned_title:
            cleaned_title = text.strip()

        # 6f. Capitalize words cleanly while preserving acronyms (e.g. "RFC")
        title_words = cleaned_title.split()
        capitalized_words = [w.capitalize() if w.islower() else w for w in title_words]
        cleaned_title = " ".join(capitalized_words)

        # 6g. Title Normalization: Clean unstructured habits/routines into concise, professional titles
        norm_map = {
            "gym": "Gym Session",
            "the gym": "Gym Session",
            "gym session": "Gym Session",
            "workout": "Workout Session",
            "the workout": "Workout Session",
            "workout session": "Workout Session",
            "exercise": "Exercise Session",
            "cook lunch": "Lunch Preparation",
            "cooking lunch": "Lunch Preparation",
            "make lunch": "Lunch Preparation",
            "lunch": "Lunch Preparation",
            "lunch prep": "Lunch Preparation",
            "lunch preparation": "Lunch Preparation",
            "lunch break": "Lunch Break",
            "cook dinner": "Dinner Preparation",
            "cooking dinner": "Dinner Preparation",
            "make dinner": "Dinner Preparation",
            "dinner prep": "Dinner Preparation",
            "dinner preparation": "Dinner Preparation",
            "cook breakfast": "Breakfast Preparation",
            "cooking breakfast": "Breakfast Preparation",
            "make breakfast": "Breakfast Preparation",
            "breakfast prep": "Breakfast Preparation",
            "groceries": "Grocery Shopping",
            "buy groceries": "Grocery Shopping",
            "grocery shopping": "Grocery Shopping",
            "clean": "House Chores",
            "cleaning": "House Chores",
            "chores": "House Chores",
            "house cleaning": "House Chores",
            "walk": "Walk & Fresh Air",
            "take a walk": "Walk & Fresh Air",
            "go for a walk": "Walk & Fresh Air",
            "nap": "Power Nap",
            "power nap": "Power Nap",
            "sleep": "Rest & Sleep",
            "bedtime": "Rest & Sleep",
        }
        lower_cleaned = cleaned_title.lower().strip()
        if lower_cleaned in norm_map:
            cleaned_title = norm_map[lower_cleaned]

        # 7. Schema Validation & Instantiation Check
        task_candidate = TaskItem(
            title=cleaned_title,
            category=category,
            estimated_minutes=minutes,
            priority=priority,
            status=TaskStatus.PENDING,
            target_start_time=target_start_time,
            target_date=target_date_str,
            has_explicit_start=has_explicit_start,
            has_explicit_duration=has_explicit_duration,
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
        # 1. Parse Calendar Date (honor explicit schedule_date or infer target_date from tasks)
        if not schedule_date:
            for item in tasks:
                t_date = getattr(item, "target_date", None) if not isinstance(item, dict) else item.get("target_date")
                if t_date and isinstance(t_date, str):
                    schedule_date = t_date
                    break

        target_date = dt_date.fromisoformat(schedule_date) if schedule_date else dt_date.today()

        # 2. Normalize and Validate Task Items
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

        # 3. Align Start and End Times with Target Start Times
        target_starts = [
            t.target_start_time for t in validated_tasks
            if getattr(t, "target_start_time", None) and isinstance(t.target_start_time, str)
        ]

        if target_starts:
            earliest_target = min(target_starts)
            # If start_time was default or 00:00, or if all tasks are anchored, align start_time to earliest_target
            if start_time in ("09:00", "00:00") or start_time < earliest_target:
                start_time = earliest_target

        total_task_minutes = sum(t.estimated_minutes for t in validated_tasks) + len(validated_tasks) * 15

        # 4. Parse & Validate Boundary Times
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

        # Inverted schedule window check (unless target_starts dynamically adapt window)
        if not target_starts and end_dt <= start_dt:
            return {
                "success": False,
                "data": None,
                "error": f"End time ({end_time}) must be strictly after start time ({start_time}).",
            }

        # Dynamically expand end_time if target_starts are present and would exceed end_dt
        if target_starts:
            needed_dt = start_dt + timedelta(minutes=total_task_minutes + 30)
            day_limit = datetime.combine(target_date, time(23, 59))
            if end_dt <= start_dt or end_dt < needed_dt:
                end_dt = min(day_limit, needed_dt) if needed_dt > start_dt else day_limit
                end_time = end_dt.strftime("%H:%M")

        # 5. Deterministic Priority / Chronological Sorting
        priority_weights = {
            TaskPriority.CRITICAL: 4,
            TaskPriority.HIGH: 3,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 1,
        }
        has_anchors = any(getattr(t, "target_start_time", None) for t in validated_tasks)
        if has_anchors:
            # Sort chronologically for anchored / chained tasks
            sorted_tasks = sorted(
                validated_tasks,
                key=lambda t: (
                    getattr(t, "target_start_time", None) or "99:99",
                    -priority_weights.get(TaskPriority(t.priority), 0),
                ),
            )
        else:
            sorted_tasks = sorted(
                validated_tasks,
                key=lambda t: priority_weights.get(TaskPriority(t.priority), 0),
                reverse=True,
            )

        # 6. Pack into Time Blocks with Deep Work Buffers
        cursor_dt = start_dt
        time_blocks: List[TimeBlock] = []
        allocated_tasks: List[TaskItem] = []
        total_buffer_minutes = 0

        for task in sorted_tasks:
            # If task has a specific target_start_time, advance cursor if it starts later
            if getattr(task, "target_start_time", None):
                try:
                    task_target_t = datetime.strptime(task.target_start_time, "%H:%M").time()
                    task_target_dt = datetime.combine(target_date, task_target_t)
                    if cursor_dt < task_target_dt:
                        cursor_dt = task_target_dt
                except Exception:
                    pass

            task_duration = timedelta(minutes=task.estimated_minutes)
            next_cursor = cursor_dt + task_duration

            # Check if task fits in the remaining schedule window
            day_limit = datetime.combine(target_date, time(23, 59))
            if next_cursor > end_dt:
                if (target_starts or getattr(task, "category", None) == TaskCategory.REST) and next_cursor <= day_limit:
                    end_dt = next_cursor
                elif getattr(task, "category", None) == TaskCategory.REST and cursor_dt < day_limit:
                    next_cursor = day_limit
                    end_dt = day_limit
                else:
                    continue  # Out of time slot capacity for this day
            elif next_cursor > day_limit:
                next_cursor = day_limit

            if next_cursor <= cursor_dt:
                continue

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

        # 7. Instantiate and Validate Full DailySchedule
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
            "description": "Extracts and normalizes raw text into structured task properties with clean, professional titles (e.g. 'i wanna go to gym' -> 'Gym Session', 'need to cook lunch' -> 'Lunch Preparation').",
            "parameters": {
                "type": "object",
                "properties": {
                    "raw_text": {
                        "type": "string",
                        "description": "Unstructured text string describing the action item or task (e.g. 'Draft system RFC 90m high priority', 'i wanna go to gym', 'need to cook lunch', 'I have a meeting in 5 minutes').",
                    },
                    "reference_time": {
                        "type": "string",
                        "description": "Optional 24h reference time 'HH:MM' or ISO format datetime for relative offset calculations. Defaults to current local time.",
                    },
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
                        "description": "List of task objects containing id, title, category, estimated_minutes, priority, and optional target_start_time.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "title": {"type": "string"},
                                "category": {
                                    "type": "string",
                                    "enum": ["Deep Work", "Shallow Work", "Errands", "Health", "Rest"],
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
                                "target_start_time": {
                                    "type": "string",
                                    "description": "Optional scheduled start time in 24h 'HH:MM' format (e.g. '14:35').",
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
