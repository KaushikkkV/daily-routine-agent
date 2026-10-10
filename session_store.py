"""Persistent session storage for Daily Routine & Task Concierge agent.

Implements an ACID-compliant SQLite session store preserving AgentState,
message history, and active schedules across conversational turns.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from schemas import AgentState


class SQLiteSessionStore:
    """Persistent SQLite-backed session store for agent memory and execution state."""

    def __init__(self, db_path: str = "concierge_sessions.db") -> None:
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and return a SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize sessions schema."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, state: AgentState) -> None:
        """Persist or update an AgentState instance.

        Args:
            state: The AgentState model to persist.
        """
        now = datetime.now(timezone.utc).isoformat()
        state_serialized = state.model_dump_json()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_sessions (session_id, state_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    updated_at = excluded.updated_at
                """,
                (state.session_id, state_serialized, now, now),
            )
            conn.commit()

    def load(self, session_id: str) -> Optional[AgentState]:
        """Retrieve and deserialize an AgentState by its session_id.

        Args:
            session_id: Unique identifier of the session.

        Returns:
            Restored AgentState instance or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT state_json FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return AgentState.model_validate_json(row["state_json"])

    def exists(self, session_id: str) -> bool:
        """Check if a session exists in the store."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            )
            return cursor.fetchone() is not None

    def delete(self, session_id: str) -> bool:
        """Remove a session from storage."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_sessions(self) -> List[str]:
        """List all stored session IDs."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT session_id FROM agent_sessions ORDER BY updated_at DESC")
            return [row["session_id"] for row in cursor.fetchall()]
