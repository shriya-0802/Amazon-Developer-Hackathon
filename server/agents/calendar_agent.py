"""Calendar Agent — Smart schedule management with real database integration."""

from datetime import datetime, timedelta
from typing import Any
from memory.knowledge_graph import KnowledgeGraph
import database as db


class CalendarAgent:
    """Manages calendar, meetings, and intelligent schedule optimization."""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    def _get_events(self, session_id: str) -> list:
        """Pull real events from database for this user."""
        today = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
        events = db.get_events(session_id, date=today)
        return events

    def _format_time(self, iso_str: str) -> str:
        """Convert ISO time to readable format."""
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%-I:%M %p")
        except Exception:
            return iso_str

    async def handle(self, message: str, entities: dict, session_id: str) -> dict:
        """Handle calendar-related messages."""
        msg = message.lower()

        if "today" in msg or "schedule" in msg or "meetings" in msg:
            schedule = await self.get_today_schedule(session_id)
            meetings = schedule["meetings"]

            if not meetings:
                return {
                    "text": "📅 You have no meetings scheduled for today. Your day is wide open! 🎉",
                    "type": "schedule",
                    "cards": [],
                }

            text = f"📅 You have {len(meetings)} meetings today:\n\n"
            for m in meetings:
                text += f"• **{m['time']}** — {m['title']} ({m.get('location', 'TBD')})\n"

            free = schedule.get("free_blocks", [])
            if free:
                best = max(free, key=lambda x: x["duration"])
                text += f"\n💡 Your longest free block is {best['start']} - {best['end']} ({best['duration']} min). Great for deep work!"

            return {
                "text": text,
                "type": "schedule",
                "cards": [{
                    "type": "schedule_card",
                    "title": "📅 Today's Schedule",
                    "meetings": meetings,
                    "free_blocks": free,
                }],
            }

        elif "block" in msg or "optimize" in msg:
            return await self.smart_schedule("optimize", "", session_id)

        elif "add" in msg or "create" in msg:
            # Extract event details from message
            title = message.replace("add meeting", "").replace("add event", "").replace("create event", "").strip()
            if not title:
                title = "New Event"
            now = datetime.utcnow() + timedelta(hours=5, minutes=30)
            today = now.strftime("%Y-%m-%d")
            
            # Default to next hour
            start_dt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            end_dt = start_dt + timedelta(hours=1)
            
            db.add_event(session_id, {
                "title": title,
                "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "end_time": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "event_type": "meeting",
            })
            return {
                "text": f"📅 Added event: **{title}** to your calendar!",
                "type": "event_added",
                "cards": [],
            }

        return {
            "text": "I can show your schedule, find free time, or optimize your day. What would you like?",
            "type": "schedule",
            "cards": [],
        }

    async def get_today_schedule(self, session_id: str) -> dict:
        """Get today's full schedule from the database."""
        events = self._get_events(session_id)

        meetings = []
        for e in events:
            meetings.append({
                "id": e["id"],
                "title": e["title"],
                "time": self._format_time(e["start_time"]),
                "duration": 30,
                "type": e.get("event_type", "meeting"),
                "location": e.get("location", ""),
            })

        # Calculate free blocks (simplified)
        free_blocks = []
        if len(meetings) > 0:
            free_blocks = [
                {"start": "8:00 AM", "end": meetings[0]["time"], "duration": 90},
                {"start": "12:00 PM", "end": "2:00 PM", "duration": 120},
            ]

        return {"meetings": meetings, "free_blocks": free_blocks}

    async def smart_schedule(self, action: str, goal: str, session_id: str) -> dict:
        """Intelligently manage scheduling."""
        schedule = await self.get_today_schedule(session_id)
        meetings = schedule["meetings"]
        total_meeting_time = len(meetings) * 30

        if action == "optimize":
            return {
                "text": f"🔄 Schedule Optimization:\n\nYou have {len(meetings)} events today ({total_meeting_time} min total).\n\n1. ✅ Deep work block → Before your first meeting\n2. ✅ Lunch + walk → 12:00-1:00 PM\n3. ✅ Creative work → Afternoon free block\n\nWant me to add these focus blocks to your calendar?",
                "type": "optimization",
                "cards": [{
                    "type": "action_card",
                    "title": "🔄 Optimized Schedule",
                    "body": f"{len(meetings)} meetings, focus blocks suggested",
                    "actions": [
                        {"label": "✅ Apply All", "value": "apply_all"},
                        {"label": "📝 Customize", "value": "customize"},
                    ],
                }],
            }

        return {"text": "How would you like to manage your schedule?", "type": "schedule", "cards": []}
