"""Session Store — Manages conversation sessions."""

from datetime import datetime
from typing import Any


class SessionStore:
    """Simple in-memory session store. In production, backed by DynamoDB."""

    def __init__(self):
        self._sessions: dict[str, dict] = {}

    def get_or_create(self, session_id: str) -> dict:
        """Get or create a session."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "id": session_id,
                "created_at": datetime.now().isoformat(),
                "messages": [],
                "context": {},
            }
        return self._sessions[session_id]

    def update(self, session_id: str, user_message: str, response: dict):
        """Update session with new message/response pair."""
        session = self.get_or_create(session_id)
        session["messages"].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat(),
        })
        session["messages"].append({
            "role": "assistant",
            "content": response.get("text", ""),
            "timestamp": datetime.now().isoformat(),
        })
        session["last_active"] = datetime.now().isoformat()

    def get_history(self, session_id: str, limit: int = 10) -> list:
        """Get recent message history."""
        session = self._sessions.get(session_id, {})
        messages = session.get("messages", [])
        return messages[-limit:]
