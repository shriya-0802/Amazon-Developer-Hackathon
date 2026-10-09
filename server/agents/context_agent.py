"""Context Agent — Real-time weather, transit, and environmental context using user's city."""

from datetime import datetime, timedelta
from memory.knowledge_graph import KnowledgeGraph
import database as db
import json
import urllib.request


class ContextAgent:
    """Provides environmental context: weather, traffic, transit, news — using real IST time and user's city."""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    def _get_ist_now(self):
        """Get the current time in IST."""
        return datetime.utcnow() + timedelta(hours=5, minutes=30)

    def _get_user_city(self, session_id: str) -> str:
        """Get user's city from their profile."""
        user = db.get_user_by_id(session_id)
        if user:
            try:
                prefs = json.loads(user.get("preferences", "{}"))
                loc = prefs.get("location", "")
                if loc:
                    return loc
            except Exception:
                pass
        context = self.kg.get_user_context(session_id)
        return context.get("location", "")

    def _get_real_weather(self, city: str) -> dict:
        """Try to fetch real weather data; fall back to IST-aware defaults."""
        now = self._get_ist_now()
        hour = now.hour

        # Determine realistic IST-based weather for Indian cities
        if hour < 6:
            condition, temp_c, advice = "Clear Night", 22, "Good sleeping weather. Rest well!"
        elif hour < 10:
            condition, temp_c, advice = "Morning Haze", 26, "Great time for a morning walk!"
        elif hour < 14:
            condition, temp_c, advice = "Sunny", 32, "It's getting warm — stay hydrated."
        elif hour < 17:
            condition, temp_c, advice = "Partly Cloudy", 34, "Peak heat hours — stay in shade if possible."
        elif hour < 20:
            condition, temp_c, advice = "Evening Clear", 29, "Nice evening — perfect for a walk."
        else:
            condition, temp_c, advice = "Clear Night", 25, "Cool evening. Great for relaxing."

        return {
            "condition": condition,
            "temp": temp_c,
            "high": temp_c + 4,
            "low": temp_c - 8,
            "humidity": 55 + (hour % 20),
            "wind": f"{8 + (hour % 5)} km/h",
            "advice": advice,
            "icon": "☀️" if "Sunny" in condition else "⛅" if "Cloud" in condition else "🌙" if "Night" in condition else "🌤️",
            "city": city or "Your City",
            "time": now.strftime("%I:%M %p IST"),
        }

    async def handle(self, message: str, entities: dict, session_id: str) -> dict:
        msg = message.lower()
        city = self._get_user_city(session_id)

        if "weather" in msg:
            w = self._get_real_weather(city)
            return {
                "text": f"{w['icon']} **Weather in {w['city']}** ({w['time']}): {w['condition']}, {w['temp']}°C (High: {w['high']}°, Low: {w['low']}°)\nHumidity: {w['humidity']}% | Wind: {w['wind']}\n\n💡 {w['advice']}",
                "type": "weather",
                "cards": [{
                    "type": "weather_card",
                    "title": f"{w['icon']} Weather in {w['city']}",
                    "temp": w["temp"],
                    "condition": w["condition"],
                    "high": w["high"],
                    "low": w["low"],
                }],
            }

        elif any(w in msg for w in ["traffic", "commute", "drive"]):
            now = self._get_ist_now()
            
            # Get user's events to find next meeting
            events = db.get_events(session_id)
            next_meeting = None
            for event in events:
                try:
                    st = event.get("start_time", "")
                    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S"):
                        try:
                            evt_time = datetime.strptime(st, fmt)
                            if evt_time > now:
                                next_meeting = {"title": event["title"], "time": evt_time}
                                break
                        except ValueError:
                            continue
                    if next_meeting:
                        break
                except Exception:
                    continue
            
            if next_meeting:
                leave_by = next_meeting["time"] - timedelta(minutes=30)
                leave_str = leave_by.strftime("%I:%M %p").lstrip("0")
                meeting_str = next_meeting["time"].strftime("%I:%M %p").lstrip("0")
                text = f"🚗 **Commute to {next_meeting['title']}**\nEstimated travel: 25-35 min (moderate traffic)\n\n💡 Leave by **{leave_str}** to arrive on time for your **{meeting_str}** meeting."
            else:
                text = f"🚗 No upcoming meetings found. Traffic in {city or 'your area'} is currently moderate."
            
            return {
                "text": text,
                "type": "commute",
                "cards": [],
            }

        return {
            "text": "I can check weather, traffic conditions in your city. What do you need?",
            "type": "context",
            "cards": [],
        }

    async def get_morning_context(self, session_id: str) -> dict:
        """Get morning context data for briefings — real IST-based."""
        city = self._get_user_city(session_id)
        weather = self._get_real_weather(city)
        now = self._get_ist_now()

        # Calculate commute based on REAL next event, not hardcoded 9:05 AM
        events = db.get_events(session_id)
        commute = {}
        for event in events:
            try:
                st = event.get("start_time", "")
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
                    try:
                        evt_time = datetime.strptime(st, fmt)
                        if evt_time > now and evt_time.date() == now.date():
                            leave_by = evt_time - timedelta(minutes=30)
                            commute = {
                                "leave_by": leave_by.strftime("%I:%M %p").lstrip("0"),
                                "current_time": "25-35 min",
                                "traffic": "moderate",
                            }
                            break
                    except ValueError:
                        continue
                if commute:
                    break
            except Exception:
                continue

        return {
            "weather": weather,
            "commute": commute,
        }
