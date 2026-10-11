"""Domain schemas and data contracts for Daily Routine & Task Concierge agent.

Built with Pydantic v2 for runtime validation, serialization, and typing integrity.
"""

from __future__ import annotations

from datetime import date as dt_date, datetime, time, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskCategory(str, Enum):
    """Categorization for cognitive load balancing and routine grouping."""
    DEEP_WORK = "Deep Work"
    SHALLOW_WORK = "Shallow Work"
    ERRANDS = "Errands"
    HEALTH = "Health"
    REST = "Rest"


class TaskPriority(str, Enum):
    """Priority scoring levels for task scheduling and urgency weighting."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"
    NONE = "None"


class TaskStatus(str, Enum):
    """Lifecycle states of an individual task item."""
    PENDING = "Pending"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
    DEFERRED = "Deferred"


class TaskItem(BaseModel):
    """Atomic task domain entity parsed from user inputs or routine templates."""

    model_config = ConfigDict(use_enum_values=True, validate_assignment=True, extra="ignore")

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the task.",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Concise description or title of the action item.",
    )
    category: TaskCategory = Field(
        ...,
        description="Cognitive category (Deep Work, Shallow Work, Errands, Health).",
    )
    estimated_minutes: int = Field(
        ...,
        ge=5,
        le=720,
        description="Estimated duration in minutes (bounded between 5 minutes and 12 hours).",
    )
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Priority tier to determine scheduling precedence.",
    )
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        description="Current completion status of the task.",
    )
    target_start_time: Optional[str] = Field(
        default=None,
        description="Optional scheduled start time in HH:MM format (e.g. from relative timing or explicit slot).",
    )
    target_date: Optional[str] = Field(
        default=None,
        description="Optional scheduled calendar date in YYYY-MM-DD format.",
    )
    has_explicit_start: bool = Field(
        default=False,
        description="Whether an explicit start anchor time was specified.",
    )
    has_explicit_duration: bool = Field(
        default=True,
        description="Whether an explicit duration or end time was provided.",
    )

    @field_validator("title")
    @classmethod
    def strip_and_validate_title(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Task title cannot be empty or purely whitespace.")
        return clean


class TimeBlock(BaseModel):
    """Discrete time interval within a daily schedule allocated to a task or buffer."""

    model_config = ConfigDict(use_enum_values=True, validate_assignment=True)

    start_time: time = Field(
        ...,
        description="Block start time (HH:MM).",
    )
    end_time: time = Field(
        ...,
        description="Block end time (HH:MM).",
    )
    label: str = Field(
        ...,
        min_length=1,
        description="Descriptive label for this time block (e.g., task title or 'Buffer').",
    )
    task_id: Optional[str] = Field(
        default=None,
        description="Referenced TaskItem id if mapped to a task, otherwise None for buffer/breaks.",
    )
    is_buffer: bool = Field(
        default=False,
        description="True if this block represents slack/buffer time or rest interval.",
    )

    @model_validator(mode="after")
    def validate_chronology(self) -> "TimeBlock":
        if self.end_time <= self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) must be strictly after start_time ({self.start_time})."
            )
        return self

    @property
    def duration_minutes(self) -> int:
        """Calculate the duration of the time block in minutes."""
        start_dt = datetime.combine(dt_date.min, self.start_time)
        end_dt = datetime.combine(dt_date.min, self.end_time)
        return int((end_dt - start_dt).total_seconds() / 60)


class DailySchedule(BaseModel):
    """Aggregate plan representing a day's time slots, tasks, and slack buffers."""

    model_config = ConfigDict(use_enum_values=True, validate_assignment=True)

    date: dt_date = Field(
        ...,
        description="Target calendar date for this daily routine schedule.",
    )
    time_blocks: List[TimeBlock] = Field(
        default_factory=list,
        description="Chronologically ordered time slots across the day.",
    )
    tasks_allocated: List[TaskItem] = Field(
        default_factory=list,
        description="TaskItem records planned and scheduled in this daily plan.",
    )
    buffer_time_minutes: int = Field(
        default=0,
        ge=0,
        description="Aggregated buffer / slack duration in minutes across the schedule.",
    )

    @model_validator(mode="after")
    def validate_non_overlapping_blocks(self) -> "DailySchedule":
        """Ensure time blocks do not overlap and maintain temporal order."""
        sorted_blocks = sorted(self.time_blocks, key=lambda b: b.start_time)
        for i in range(len(sorted_blocks) - 1):
            curr_b = sorted_blocks[i]
            next_b = sorted_blocks[i + 1]
            if curr_b.end_time > next_b.start_time:
                raise ValueError(
                    f"Overlapping time blocks detected: '{curr_b.label}' ({curr_b.start_time}-{curr_b.end_time}) "
                    f"overlaps with '{next_b.label}' ({next_b.start_time}-{next_b.end_time})."
                )
        return self


class ChatMessage(BaseModel):
    """Conversational record item within agent memory history."""

    role: Literal["user", "assistant", "system", "tool"] = Field(
        ...,
        description="Role of the message sender.",
    )
    content: str = Field(
        ...,
        description="Text content or serialized payload of the message.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the interaction.",
    )


class ScheduleVersion(BaseModel):
    """Immutable snapshot of a DailySchedule at a specific version point."""

    model_config = ConfigDict(validate_assignment=True)

    version_id: int = Field(
        ...,
        description="Monotonically increasing version identifier.",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp string when this snapshot was created.",
    )
    change_summary: str = Field(
        ...,
        description="Brief summary or rationale describing what changed in this version.",
    )
    schedule_snapshot: DailySchedule = Field(
        ...,
        description="Complete serialized DailySchedule state for this version.",
    )


class AgentState(BaseModel):
    """Central working memory and execution state for the Concierge agent."""

    model_config = ConfigDict(validate_assignment=True)

    session_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the user session / agent run.",
    )
    current_user_query: Optional[str] = Field(
        default=None,
        description="Latest raw input received from the user.",
    )
    unparsed_notes: List[str] = Field(
        default_factory=list,
        description="Raw, unstructured text snippets or brain-dump notes pending extraction.",
    )
    active_schedule: Optional[DailySchedule] = Field(
        default=None,
        description="Current working schedule being constructed or mutated.",
    )
    message_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Chronological log of multi-turn interaction between user and agent.",
    )
    current_version_id: int = Field(
        default=0,
        description="Latest active schedule version identifier (0 if uncommitted).",
    )
    version_history: List[ScheduleVersion] = Field(
        default_factory=list,
        description="Chronological audit trail of committed schedule version snapshots.",
    )

