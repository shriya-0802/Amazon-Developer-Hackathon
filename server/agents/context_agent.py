"""Context Agent — Weather, transit, news, and environmental context."""

from datetime import datetime
from memory.knowledge_graph import KnowledgeGraph


class ContextAgent:
    """Provides environmental context: weather, traffic, transit, news."""

    DEMO_CONTEXT = {
        "weather": {
            "condition": "Partly cloudy",
            "temp": 72,
            "high": 78,
            "low": 62,
            "humidity": 45,
            "wind": "8 mph NW",
            "advice": "Beautiful day — perfect for that afternoon walk!",
            "icon": "⛅",
        },
        "commute": {
            "usual_time": "25 min",
            "current_time": "32 min",
            "traffic": "moderate",
            "leave_by": "9:05 AM",
            "route": "via I-405 S",
            "incidents": "Minor slowdown near exit 12",
        },
        "news_highlights": [
            "Tech earnings beat expectations across the board",
            "New AI regulations proposed in the EU",
            "Local: Downtown farmers market this Saturday",
        ],
    }

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    async def handle(self, message: str, entities: dict, session_id: str) -> dict:
        msg = message.lower()

        if "weather" in msg:
            w = self.DEMO_CONTEXT["weather"]
            return {
                "text": f"{w['icon']} **Weather**: {w['condition']}, {w['temp']}°F (High: {w['high']}°, Low: {w['low']}°)\nHumidity: {w['humidity']}% | Wind: {w['wind']}\n\n💡 {w['advice']}",
                "type": "weather",
                "cards": [{
                    "type": "weather_card",
                    "title": f"{w['icon']} Weather",
                    "temp": w["temp"],
                    "condition": w["condition"],
                    "high": w["high"],
                    "low": w["low"],
                }],
            }

        elif any(w in msg for w in ["traffic", "commute", "drive"]):
            c = self.DEMO_CONTEXT["commute"]
            return {
                "text": f"🚗 **Commute**: {c['current_time']} ({c['traffic']} traffic)\nUsual: {c['usual_time']} | Route: {c['route']}\n⚠️ {c['incidents']}\n\n💡 Leave by {c['leave_by']} to make your 9:30 AM meeting.",
                "type": "commute",
                "cards": [{
                    "type": "commute_card",
                    "title": "🚗 Commute",
                    "time": c["current_time"],
                    "traffic": c["traffic"],
                    "leave_by": c["leave_by"],
                }],
            }

        return {
            "text": "I can check weather, traffic, and news. What do you need?",
            "type": "context",
            "cards": [],
        }

    async def get_morning_context(self, session_id: str) -> dict:
        """Get morning context data for briefings."""
        return self.DEMO_CONTEXT
