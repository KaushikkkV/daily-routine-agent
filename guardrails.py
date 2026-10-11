"""Safety guardrails, validation checks, and security boundaries for the Concierge agent."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from schemas import DailySchedule, TaskCategory, TimeBlock
from tools import is_chained_multitask_sequence, sanitize_task_title


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
    # Core Task & Scheduling terms
    r"\btasks?\b",
    r"\bschedules?\b",
    r"\bscheduling\b",
    r"\broutines?\b",
    r"\btodos?\b",
    r"\bto-dos?\b",
    r"\bplans?\b",
    r"\bplanning\b",
    r"\bset\s*up\b",
    r"\bsetup\b",
    r"\bbook(?:ing)?s?\b",
    r"\bblock(?:ing)?s?\b",
    r"\bslots?\b",
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
    # Lifestyle, Fitness & Wellness
    r"\bgyms?\b",
    r"\bworkouts?\b",
    r"\bexercise\b",
    r"\bfitness\b",
    r"\bruns?\b",
    r"\brunning\b",
    r"\bjogs?\b",
    r"\bjogging\b",
    r"\bwalks?\b",
    r"\bwalking\b",
    r"\byoga\b",
    r"\bstretch(?:ing)?\b",
    r"\bmeditat(?:e|ion|ing)?\b",
    r"\bcardio\b",
    r"\bswims?\b",
    r"\bswimming\b",
    r"\bcycl(?:e|ing)|bike|biking\b",
    r"\bdoctor\b",
    r"\bdentist\b",
    r"\bappointments?\b",
    r"\btherap(?:y|ist)\b",
    r"\bnaps?\b",
    r"\brest\b",
    r"\brecovery\b",
    r"\bsleep\b",
    # Meals & Breaks
    r"\blunch\b",
    r"\bdinner\b",
    r"\bbreakfast\b",
    r"\bmeals?\b",
    r"\beats?\b",
    r"\beating\b",
    r"\bcook(?:ing)?\b",
    r"\bfood\b",
    r"\bcoffee\b",
    r"\btea\b",
    r"\bsnacks?\b",
    r"\bbreaks?\b",
    r"\bslack\b",
    # Chores, Personal & Household
    r"\bshower(?:ing)?\b",
    r"\bbaths?\b",
    r"\bhygiene\b",
    r"\bchores?\b",
    r"\bgrocer(?:y|ies)\b",
    r"\blaundry\b",
    r"\bdishes\b",
    r"\bclean(?:ing)?\b",
    r"\bbuys?\b",
    r"\bshops?\b",
    r"\bshopping\b",
    r"\bcommute|commuting|drive|driving\b",
    # Work, Meetings & Collaboration
    r"\bmeet(?:ing)?s?\b",
    r"\bcalls?\b",
    r"\bsyncs?\b",
    r"\bstandups?\b",
    r"\bcatchups?\b",
    r"\b1:1\b",
    r"\b1-on-1\b",
    r"\binterviews?\b",
    r"\bpresentation\b",
    r"\breviews?\b",
    r"\bemails?\b",
    r"\bcoding|codes?\b",
    r"\bdebug(?:ging)?\b",
    r"\bwrit(?:e|ing)\b",
    r"\bdrafts?\b",
    r"\bread(?:ing)?\b",
    r"\bstud(?:y|ying)\b",
    r"\bresearch\b",
    # Activity Intention & Action Verbs
    r"\b(?:want|need|have|plan|going)\s+to\b",
    r"\b(?:go\s+to|attend|schedule|start|finish|do)\b",
    r"\b(?:tomorrow|today|tonight|next\s+week|this\s+week|slot|slots|book|booking)\b",
]

# Purely out-of-domain intents to reject (trivia, general knowledge, essays, jokes, weather, code tutorials)
OFF_TOPIC_INTENT_PATTERNS = [
    # Creative writing, poems, jokes, stories, essays
    r"\b(?:write|tell)\s+(?:me\s+)?(?:a\s+)?(?:poem|joke|story|song|essay|riddle|fairy\s*tale|speech)\b",
    # Factual encyclopedic Q&A and historical trivia
    r"\b(?:what|who|where|when|why)\s+is\s+(?:the\s+)?(?:capital|president|meaning\s+of\s+life|distance\s+to|history\s+of|population\s+of|currency\s+of|founder\s+of|inventor\s+of)\b",
    r"\bwho\s+(?:was|is)\s+(?:the\s+)?(?:first|president|king|queen|emperor|prime\s+minister)\b",
    # Weather inquiries
    r"\b(?:how|what)\s+(?:is|about)\s+the\s+weather\b",
    r"\bweather\s+(?:forecast|today|tomorrow|in\s+\w+)\b",
    r"\b(?:will|is\s+it\s+going\s+to)\s+rain\s+today\b",
    # Coding assistance and programming tutorials
    r"\b(?:write|code|program)\s+(?:a|an|some)?\s*(?:python|javascript|typescript|react|sql|html|css|c\+\+|java|go|rust|script|function|app|bot|api)\b",
    r"\bhow\s+to\s+(?:code|program|build\s+a\s+website|write\s+a\s+function|fix\s+this\s+bug)\b",
    # Academic/scientific explanations
    r"\bexplain\s+(?:quantum|physics|relativity|calculus|philosophy|photosynthesis|thermodynamics|gravity)\b",
    # Malicious
    r"\bhow\s+to\s+(?:hack|invest|build\s+a\s+bomb)\b",
]


# Casual / Ambiguous / Venting Patterns with Contextual Steering Responses
CASUAL_STEERING_PATTERNS = [
    # 1. Greetings & Casual Openers ("yo", "hey", "what's up", "sup", "hi", "hello")
    (
        r"^(?:yo(?:[\s,]+concierge)?|hey(?:[\s,]+there)?|hi(?:[\s,]+there)?|hello|what'?s\s+up|whats\s+up|sup|howdy|good\s+(?:morning|afternoon|evening))[\s!?.~]*$",
        "Hey! Ready whenever you are. Should we map out your focus blocks for today, or are you looking to schedule a specific workout or meeting?",
    ),
    # 2. Fatigue, Exhaustion, Sleepiness ("feeling tired", "exhausted", "so tired", etc.)
    (
        r"\b(?:feeling\s+tired|feel\s+tired|so\s+tired|exhausted|feeling\s+exhausted|im\s+tired|i'm\s+tired|im\s+exhausted|i'm\s+exhausted|sleepy|feeling\s+sleepy|drained|feeling\s+drained|burnt\s+out)\b",
        "Sounds like you need to protect your energy. Should we schedule a 20-minute recovery buffer now, or wrap up today's remaining tasks early?",
    ),
    # 3. Post-Meal / Afternoon Slump ("just had lunch", "just finished lunch", "had lunch", etc.)
    (
        r"\b(?:just\s+had\s+lunch|just\s+finished\s+lunch|had\s+lunch|ate\s+lunch|finished\s+lunch|just\s+ate\s+lunch|done\s+with\s+lunch|just\s+had\s+a\s+meal|just\s+ate)\b",
        "Hope it was good. Should we lock in a low-intensity shallow work block to beat the afternoon slump, or jump straight into deep work?",
    ),
    # 4. Overwhelm & Stress ("feeling overwhelmed", "overwhelmed", "stressed", "so much to do")
    (
        r"\b(?:feeling\s+overwhelmed|feel\s+overwhelmed|overwhelmed|so\s+overwhelmed|im\s+overwhelmed|i'm\s+overwhelmed|stressed|feeling\s+stressed|so\s+much\s+to\s+do|anxious|frazzled)\b",
        "Take a breath—we'll get everything under control. Should we schedule a 15-minute reset buffer now, or quickly prioritize your top three must-do items?",
    ),
    # 5. Boredom & Aimless state ("im bored", "bored", "so bored", "nothing to do")
    (
        r"\b(?:i(?:'m|\s+am)\s+bored|feeling\s+bored|im\s+bored|bored|so\s+bored|nothing\s+to\s+do|what\s+should\s+i\s+do)\b",
        "Let's build some positive momentum. Should we kick off a 45-minute deep focus sprint, or knock out a few quick operational errands first?",
    ),
]


def is_casual_or_steering_input(user_input: str) -> bool:
    """Check if input is casual talk, greeting, emotional venting, or post-meal status."""
    return get_casual_steering_response(user_input) is not None


def get_casual_steering_response(user_input: str) -> Optional[str]:
    """Identify casual conversation, status updates, or emotional venting,
    and return an executive concierge steering response with 2 actionable choices.

    Returns None if the input contains a concrete schedulable task or command.
    """
    clean = user_input.strip()
    if not clean:
        return None
    lower = clean.lower()

    if is_chained_multitask_sequence(lower):
        return None

    # Confirmation / rollback phrases are not casual steering
    confirmation_phrases = ["yes", "save", "approve", "confirm", "commit", "rollback", "revert", "undo"]
    if any(lower == p or lower.startswith(f"{p} ") for p in confirmation_phrases):
        return None

    # Check CASUAL_STEERING_PATTERNS in order
    for pattern, response in CASUAL_STEERING_PATTERNS:
        if re.search(pattern, lower, re.IGNORECASE):
            # Check if there's also an explicit task creation command with target, e.g. "schedule a meeting at 12"
            if re.search(r"\b(?:schedule|book|set\s+up)\s+(?:a\s+)?(?:meeting|gym|call|workout|dentist|appointment)\b", lower):
                return None
            return response

    return None


def is_incomplete_scheduling_request(user_input: str) -> bool:
    """Determine whether an in-domain user query expresses scheduling intent but lacks parameters.

    Incomplete requests include shorthand, habits, meetings, or conversational tasks that lack
    an explicit start time anchor (e.g. 'at 12', '14:00') or duration (e.g. '30m', '1 hour'):
        - "setup a meet", "SETUP A MEET"
        - "gym tomorrow"
        - "dinner with team"
        - "quick call"
        - "i wanna go to gym"
        - "schedule a call", "set up a call"
        - "schedule a meeting", "set up a meeting"
        - "coffee with sarah"
        - "doctor appointment"
        - "dentist next week"
        - "dentist"
        - "workout"
        - "book a slot"

    Returns:
        True if the request has scheduling intent but lacks parameters, False otherwise.
    """
    clean = user_input.strip().lower()

    # Casual chit-chat, greetings, or venting are steered conversationally and are NOT incomplete task requests
    if is_casual_or_steering_input(clean):
        return False

    # Confirmations, approvals, rollbacks are NOT incomplete requests
    confirmation_phrases = ["yes", "save", "approve", "confirm", "commit", "rollback", "revert", "undo", "looks good", "ok", "okay"]
    if any(clean == p or clean.startswith(f"{p} ") or clean.startswith(f"{p},") for p in confirmation_phrases):
        return False

    # Chained multi-task sequences are planned in one pass and are NOT incomplete standalone requests
    if is_chained_multitask_sequence(clean):
        return False

    # Must contain a task, activity, routine, or scheduling indicator keyword
    task_intent_keywords = [
        "meet", "call", "sync", "standup", "appointment", "slot", "calendar",
        "gym", "workout", "exercise", "run", "walk", "yoga", "meditat",
        "dinner", "lunch", "breakfast", "cook", "meal", "food", "coffee", "tea",
        "dentist", "doctor", "therapy", "errand", "grocer", "laundry", "clean",
        "dishes", "chore", "code", "coding", "draft", "write", "study", "research",
        "nap", "sleep", "rest", "break", "schedule", "plan", "book", "set up", "setup",
        "priorit", "todo", "to-do", "task", "work", "deep work", "shallow work"
    ]
    if not any(kw in clean for kw in task_intent_keywords):
        return False

    # Check for explicit start time anchor (e.g. "now", "at 12", "at 3pm", "10:30", "in 5 minutes", "after 10m", "02:30 PM")
    has_explicit_time = bool(
        re.search(
            r"\b(?:now|right\s+now|immediately|at\s+\d{1,2}(?::\d{2})?|\d{1,2}(?::\d{2})?\s*(?:am|pm)|(?:in|after)\s+\d+\s*(?:m|min|mins|minutes?|h|hours?))\b",
            clean,
            re.IGNORECASE,
        )
    )
    if has_explicit_time:
        return False

    # Check for explicit duration (e.g. "30m", "45 mins", "1 hour", "for 2h")
    has_explicit_duration = bool(
        re.search(
            r"\b(?:\d+(?:\.\d+)?)\s*(?:m|min|mins|minutes?|h|hrs?|hours?)\b",
            clean,
            re.IGNORECASE,
        )
    )
    if has_explicit_duration:
        return False

    # Check for multi-task requests with delimiters
    items = [line.strip("-•* ").strip() for line in re.split(r"[,;\n]", clean) if line.strip("-•* ").strip()]
    if len(items) > 1 and any(re.search(r"\d+", it) for it in items):
        return False

    return True


# Backwards compatibility alias
is_unanchored_meeting_request = is_incomplete_scheduling_request


def pre_execution_guardrail(user_input: str) -> Tuple[bool, Optional[str]]:
    """Validate incoming user input against prompt-injection attacks and off-topic queries.

    In-Domain Definition: Any utterance that mentions an action, event, meeting,
    appointment, workout, task, errand, break, or routine—regardless of brevity or phrasing—is
    strictly IN-DOMAIN.

    Out-of-Domain Definition: Only purely irrelevant conversational topics
    (e.g., coding assistance, factual Q&A, historical trivia, creative writing, weather)
    qualify as OUT-OF-DOMAIN.

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

    # 2. Purely Out-of-Domain Queries (coding assistance, factual Q&A, historical trivia, creative writing, weather)
    for ot_pattern in OFF_TOPIC_INTENT_PATTERNS:
        if re.search(ot_pattern, lower_input, re.IGNORECASE):
            return (
                False,
                "I specialize exclusively in task scheduling, routine design, and time management. "
                "Please provide your to-do items, time commitments, or desired schedule to proceed.",
            )

    # 3. All other utterances—regardless of brevity or phrasing—are strictly IN-DOMAIN!
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
