"""Safety guardrails, validation checks, and security boundaries for the Concierge agent."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from schemas import DailySchedule, TaskCategory, TimeBlock


class GuardrailViolation(Exception):
    """Base exception for all agent guardrail safety violations."""
    def __init__(self, message: str, guardrail_type: str) -> None:
        super().__init__(message)
        self.guardrail_type = guardrail_type


class PromptInjectionViolation(GuardrailViolation):
    """Raised when adversarial prompt injection or instruction override patterns are detected."""
    def __init__(self, message: str) -> None:
        super().__init__(message, guardrail_type="prompt_injection")


class OffTopicViolation(GuardrailViolation):
    """Raised when user input is completely unrelated to task management or scheduling."""
    def __init__(self, message: str) -> None:
        super().__init__(message, guardrail_type="off_topic")


class ScheduleValidationViolation(GuardrailViolation):
    """Raised when a candidate schedule violates temporal boundaries or produces overlapping slots."""
    def __init__(self, message: str) -> None:
        super().__init__(message, guardrail_type="schedule_validation")


# Known adversarial prompt injection heuristics
INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|prompts|rules)",
    r"disregard\s+(?:all\s+)?(?:previous|system)\s+(?:instructions|rules)",
    r"system\s+(?:override|prompt\s+leak|reset)",
    r"you\s+are\s+now\s+(?:DAN|unrestricted|jailbroken|an\s+exploit)",
    r"bypass\s+(?:safety|rules|guardrails|scheduling)",
    r"reveal\s+(?:your\s+)?(?:system\s+prompt|developer\s+instructions|hidden\s+rules)",
    r"simulate\s+(?:a\s+mode\s+without\s+rules|unfiltered)",
    r"new\s+system\s+directive:",
]

# Domain keywords matched as discrete words or phrases
CORE_DOMAIN_TERMS = [
    r"\btasks?\b",
    r"\bschedules?\b",
    r"\bscheduling\b",
    r"\broutines?\b",
    r"\btodos?\b",
    r"\bto-dos?\b",
    r"\bplans?\b",
    r"\bplanning\b",
    r"\bagenda\b",
    r"\bcalendar\b",
    r"\bdeep\s+work\b",
    r"\bshallow\s+work\b",
    r"\berrands?\b",
    r"\breschedules?\b",
    r"\bpriorit(?:y|ize|ization)\b",
    r"\btime\s*blocks?\b",
    r"\bbuffers?\b",
    r"\bdeadlines?\b",
    r"\breverts?\b",
    r"\bundo\b",
    r"\brollbacks?\b",
    r"\bversions?\b",
]

# Obvious off-topic intents to immediately reject
OFF_TOPIC_INTENT_PATTERNS = [
    r"\b(?:write|tell)\s+(?:me\s+)?(?:a\s+)?(?:poem|joke|story|song|essay|riddle)\b",
    r"\b(?:what|who|where|when|why)\s+is\s+(?:the\s+)?(?:capital|president|meaning|distance|history)\b",
    r"\bhow\s+to\s+(?:hack|bake|cook|invest|build\s+a\s+bomb)\b",
    r"\bexplain\s+(?:quantum|physics|relativity|calculus|philosophy)\b",
]


def pre_execution_guardrail(user_input: str) -> Tuple[bool, Optional[str]]:
    """Validate incoming user input against prompt-injection attacks and off-topic queries.

    Args:
        user_input: Raw text string provided by the user.

    Returns:
        Tuple of (is_valid: bool, rejection_response: Optional[str]).
        If is_valid is True, rejection_response is None and execution may proceed.
        If is_valid is False, rejection_response provides the polite redirection text.
    """
    clean_input = user_input.strip()
    if not clean_input:
        return (
            False,
            "I didn't receive any tasks or schedule details. Please share your daily to-dos or routine goals.",
        )

    lower_input = clean_input.lower()

    # 1. Adversarial Prompt Injection Check
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower_input, re.IGNORECASE):
            return (
                False,
                "I am the Daily Routine & Task Concierge. I cannot bypass my operational guidelines "
                "or alter my core instructions. How may I assist you with scheduling your tasks today?",
            )

    # 2. Explicit Off-Topic Query Patterns
    for ot_pattern in OFF_TOPIC_INTENT_PATTERNS:
        if re.search(ot_pattern, lower_input, re.IGNORECASE):
            return (
                False,
                "I specialize exclusively in task scheduling, routine design, and time management. "
                "Please provide your to-do items, time commitments, or desired schedule to proceed.",
            )

    # 3. Confirmation and Affirmation Whitelist
    confirmation_phrases = ["yes", "save it", "approve", "confirmed", "looks good", "save", "ok", "okay", "go ahead", "proceed"]
    if any(lower_input == p or lower_input.startswith(f"{p} ") or lower_input.startswith(f"{p},") for p in confirmation_phrases):
        return (True, None)

    # 4. Core Domain Keyword Word-Boundary Matches
    has_domain_term = any(re.search(term, lower_input, re.IGNORECASE) for term in CORE_DOMAIN_TERMS)

    # 5. Temporal Pattern Matches (e.g., 9am, 10:30, 2h, 45m)
    has_time_spec = bool(re.search(r"\b(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d+\s*(?:h|m|hrs?|mins?))\b", lower_input))

    if not has_domain_term and not has_time_spec:
        return (
            False,
            "I specialize exclusively in task scheduling, routine design, and time management. "
            "Please provide your to-do items, time commitments, or desired schedule to proceed.",
        )

    return (True, None)


def post_execution_guardrail(schedule: DailySchedule) -> None:
    """Validate candidate schedule integrity before presentation or persistence.

    Enforces:
    1. Zero overlapping time allocations.
    2. Chronological ordering of time blocks.
    3. Strict 24-hour boundary compliance (00:00 to 23:59).
    4. Duration sanity and non-negative buffer allowances.

    Args:
        schedule: DailySchedule object to validate.

    Raises:
        ScheduleValidationViolation: If any boundary or consistency check fails.
    """
    if not schedule.time_blocks:
        return

    # Check 1: 24-hour validity and non-negative blocks
    for b in schedule.time_blocks:
        if b.end_time <= b.start_time:
            raise ScheduleValidationViolation(
                f"Block '{b.label}' has invalid temporal ordering: start {b.start_time} >= end {b.end_time}."
            )
        duration = b.duration_minutes
        if duration <= 0 or duration > 1440:
            raise ScheduleValidationViolation(
                f"Block '{b.label}' duration ({duration} mins) exceeds 24-hour daily boundaries."
            )

    # Check 2: Zero Overlapping Slots and Chronology
    sorted_blocks = sorted(schedule.time_blocks, key=lambda b: b.start_time)
    for i in range(len(sorted_blocks) - 1):
        curr = sorted_blocks[i]
        nxt = sorted_blocks[i + 1]
        if curr.end_time > nxt.start_time:
            raise ScheduleValidationViolation(
                f"Overlapping blocks detected: '{curr.label}' ({curr.start_time}-{curr.end_time}) "
                f"collides with '{nxt.label}' ({nxt.start_time}-{nxt.end_time})."
            )

    # Check 3: Buffer Time Consistency
    computed_buffer = sum(b.duration_minutes for b in schedule.time_blocks if b.is_buffer)
    if computed_buffer != schedule.buffer_time_minutes:
        raise ScheduleValidationViolation(
            f"Buffer duration mismatch: schedule records {schedule.buffer_time_minutes}m, "
            f"but actual buffer blocks total {computed_buffer}m."
        )
