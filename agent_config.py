"""Agent configuration, system prompt definition, and tool registry for the Concierge agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from tools import (
    OPENAI_TOOL_SCHEMAS,
    calculate_schedule_blocks,
    parse_task_attributes,
    revert_schedule_to_version,
    save_schedule_to_storage,
)

SYSTEM_PROMPT = """# Identity & Core Mission
You are the **Daily Routine & Task Concierge**, an executive-grade personal scheduling assistant. Your purpose is to ingest natural-language to-dos, brain dumps, and routine requests, normalize them into structured entities, score priorities and cognitive load, and generate realistic, non-overlapping daily schedules with mandatory recovery buffers.

---

# Operational Principles & Behavioral Rules

1. **Zero Assumption Policy (Clarifying Questions)**:
   - Never invent, hallucinate, or assume user commitments, start/end deadlines, or durations when inputs are vague or contradictory.
   - If an item lacks essential clarity (e.g. "prepare presentation" without duration or priority), query the user directly before committing to a final schedule.

2. **Energy-First Chronobiology**:
   - **High-energy tasks** (Deep Work, Critical, and High priority items) must automatically be scheduled in the earliest available morning/day slots.
   - Low-energy tasks (Shallow Work, routine Errands) should be batched in later slots or post-lunch lulls unless the user specifies otherwise.

3. **Chain of Thought Visibility**:
   - Always state your reasoning briefly before invoking any tool. Explain what you are parsing, how you are prioritizing, or why a buffer is required.
   - Format your reasoning as:
     `Thought: [1-2 sentences outlining the evaluation and the intended tool action]`

4. **Deep Work Recovery Safeguards**:
   - Deep work cognitively depletes users. Ensure a 10-minute recovery buffer is placed after deep-work tasks.
   - Do not schedule consecutive back-to-back deep-work marathons without slack.

5. **Version Control & Rollback Protocol**:
   - You have access to `revert_schedule_to_version(target_version_id=...)` to roll back to any previously committed schedule snapshot if the user requests an undo, reversion, or rollback.
   - When the user asks to revert or undo, identify the desired version snapshot from history and invoke `revert_schedule_to_version`.

---

# Strict Safety Boundaries & Approval Gates

- **Storage Persistence Gate**:
  - **CRITICAL**: You are **STRICTLY FORBIDDEN** from calling `save_schedule_to_storage` autonomously.
  - You must first present the complete proposed schedule layout to the user in a formatted table and request explicit approval.
  - Only call `save_schedule_to_storage` when the user has confirmed with explicit affirmation (e.g., "Yes, save it", "Looks good, commit it", "Approve").

---

# Tool Usage Protocol

1. **Step 1 - Attribute Normalization**: Use `parse_task_attributes(raw_text=...)` to sanitize and normalize freeform notes into validated `TaskItem` records.
2. **Step 2 - Temporal Packing**: Use `calculate_schedule_blocks(tasks=..., start_time=..., end_time=..., schedule_date=...)` to pack tasks into non-overlapping chronological blocks with buffers.
3. **Step 3 - Review & Confirmation**: Present the schedule cleanly to the user.
4. **Step 4 - Storage**: Once explicitly approved, invoke `save_schedule_to_storage(schedule=..., filepath=...)`.
5. **Step 5 - Rollback / Undo**: If the user requests to undo changes or revert to an earlier plan, use `revert_schedule_to_version(target_version_id=...)` to restore that version's snapshot.
"""


@dataclass
class ToolDefinition:
    """Encapsulation of a registered tool function and its OpenAI schema."""
    name: str
    callable_func: Callable[..., Dict[str, Any]]
    schema: Dict[str, Any]
    description: str


class ToolRegistry:
    """Central registry and dispatcher for deterministic agent tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        callable_func: Callable[..., Dict[str, Any]],
        schema: Dict[str, Any],
        description: str = "",
    ) -> None:
        """Register a tool with its function callable and API schema."""
        self._tools[name] = ToolDefinition(
            name=name,
            callable_func=callable_func,
            schema=schema,
            description=description or schema.get("function", {}).get("description", ""),
        )

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Retrieve tool definition by name."""
        return self._tools.get(name)

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Return all registered OpenAI-compatible tool schemas."""
        return [tool_def.schema for tool_def in self._tools.values()]

    def execute(self, name: str, **kwargs: Any) -> Dict[str, Any]:
        """Dispatch a tool call safely, returning a structured response envelope."""
        tool_def = self._tools.get(name)
        if not tool_def:
            return {
                "success": False,
                "data": None,
                "error": f"Tool '{name}' is not registered in the tool registry.",
            }
        try:
            return tool_def.callable_func(**kwargs)
        except Exception as exc:
            return {
                "success": False,
                "data": None,
                "error": f"Unhandled error during tool execution: {str(exc)}",
            }


@dataclass
class AgentConfig:
    """Unified configuration contract for the Daily Routine & Task Concierge agent."""

    system_prompt: str = SYSTEM_PROMPT
    model_name: str = "gemini-2.5-pro"
    temperature: float = 0.1
    max_tokens: int = 2048
    tool_choice: str = "auto"
    tool_registry: ToolRegistry = field(default_factory=ToolRegistry)

    @classmethod
    def create_default(cls) -> "AgentConfig":
        """Instantiate and configure the Concierge agent with all default tools."""
        registry = ToolRegistry()

        # Build schema lookup
        schema_map = {
            s["function"]["name"]: s
            for s in OPENAI_TOOL_SCHEMAS
        }

        # 1. Register parse_task_attributes
        registry.register(
            name="parse_task_attributes",
            callable_func=parse_task_attributes,
            schema=schema_map["parse_task_attributes"],
            description="Parses unstructured task notes into validated TaskItem properties.",
        )

        # 2. Register calculate_schedule_blocks
        registry.register(
            name="calculate_schedule_blocks",
            callable_func=calculate_schedule_blocks,
            schema=schema_map["calculate_schedule_blocks"],
            description="Packs tasks into chronological time slots with deep work recovery buffers.",
        )

        # 3. Register save_schedule_to_storage
        registry.register(
            name="save_schedule_to_storage",
            callable_func=save_schedule_to_storage,
            schema=schema_map["save_schedule_to_storage"],
            description="Persists validated DailySchedule JSON to storage upon user confirmation.",
        )

        # 4. Register revert_schedule_to_version
        registry.register(
            name="revert_schedule_to_version",
            callable_func=revert_schedule_to_version,
            schema=schema_map["revert_schedule_to_version"],
            description="Rolls back active schedule to a specified snapshot version_id.",
        )

        return cls(tool_registry=registry)
