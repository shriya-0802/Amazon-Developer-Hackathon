"""Knowledge Graph — Persistent user memory across sessions."""

from datetime import datetime
from typing import Any, Optional
import json
import database as db


class KnowledgeGraph:
    """
    In-memory knowledge graph for persistent user context.
    In production, this would be backed by DynamoDB.
    """

    def __init__(self):
        # User preferences and context
        self._preferences: dict[str, dict[str, Any]] = {}
        # Interaction history
        self._interactions: dict[str, list[dict]] = {}
        # Learned patterns (built from REAL user data only)
        self._patterns: dict[str, dict[str, Any]] = {}
        # Entity relationships
        self._entities: dict[str, list[dict]] = {}
        # No pre-populated demo data — everything is from real user input

    def store_preference(self, session_id: str, key: str, value: Any, importance: str = "medium"):
        """Store a user preference."""
        if session_id not in self._preferences:
            self._preferences[session_id] = {}
        self._preferences[session_id][key] = value

    def get_user_context(self, session_id: str) -> dict:
        """Get all user context for a session from the real database."""
        # Get from DB first
        user = db.get_user_by_id(session_id)
        if user:
            context = {
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "role": user.get("role", ""),
                "fitness_goal": user.get("fitness_goal", ""),
                "diet_preference": user.get("diet_preference", ""),
            }
            # Merge with any dynamic session preferences
            try:
                prefs = json.loads(user.get("preferences", "{}"))
                context.update(prefs)
            except Exception:
                pass
            
            # Merge memory graph in-session preferences
            context.update(self._preferences.get(session_id, {}))
            return context
            
        # Fallback to local memory if user not found in DB
        return dict(self._preferences.get(session_id, {}))

    def add_interaction(self, session_id: str, message: str, intent: str):
        """Record an interaction."""
        if session_id not in self._interactions:
            self._interactions[session_id] = []

        self._interactions[session_id].append({
            "message": message,
            "intent": intent,
            "timestamp": datetime.now().isoformat(),
        })

        # Keep last 100 interactions
        if len(self._interactions[session_id]) > 100:
            self._interactions[session_id] = self._interactions[session_id][-100:]

    def get_patterns(self, session_id: str) -> dict:
        """Get learned patterns for a user."""
        return dict(self._patterns.get(session_id, {}))

    def search_memories(self, session_id: str, query: str) -> list[dict]:
        """Search memories relevant to a query."""
        results = []
        prefs = self._preferences.get(session_id, {})
        query_lower = query.lower()

        for key, value in prefs.items():
            if any(w in key.lower() for w in query_lower.split()):
                results.append({"key": key, "value": str(value)})

        return results

    def get_full_graph(self, session_id: str) -> dict:
        """Get the full knowledge graph (for visualization)."""
        return {
            "preferences": self._preferences.get(session_id, {}),
            "interactions_count": len(self._interactions.get(session_id, [])),
            "patterns": self._patterns.get(session_id, {}),
            "entities": self._entities.get(session_id, []),
        }
