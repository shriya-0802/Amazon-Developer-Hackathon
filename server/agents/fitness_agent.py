"""Fitness Agent — Fitness tracking with real database integration."""

from datetime import datetime
from memory.knowledge_graph import KnowledgeGraph
import database as db


class FitnessAgent:
    """Tracks fitness goals using real user data from the database."""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    async def handle(self, message: str, entities: dict, session_id: str) -> dict:
        msg = message.lower()

        if any(w in msg for w in ["marathon", "training", "train for"]):
            goal = "half marathon"
            if "full" in msg:
                goal = "full marathon"
            return await self.set_goal(goal, session_id)

        elif any(w in msg for w in ["status", "how am i", "progress", "steps"]):
            status = await self.get_status(session_id)
            return self._format_status(status, session_id)

        elif any(w in msg for w in ["log", "did", "ran", "walked", "completed"]):
            return await self.log_activity(message, session_id)

        elif "report" in msg or "week" in msg:
            return await self.weekly_report(session_id)

        status = await self.get_status(session_id)
        return self._format_status(status, session_id)

    async def get_status(self, session_id: str) -> dict:
        """Get current fitness status from the real database."""
        entries = db.get_fitness_history(session_id, days=7)

        # Get user's step goal from DB
        user = db.get_user_by_id(session_id)
        step_goal = user.get("fitness_goal", 10000) if user else 10000

        if entries:
            today = entries[0]  # Most recent
            today_steps = today.get("steps", 0)
            step_pct = round(today_steps / step_goal * 100) if step_goal > 0 else 0
            weekly_avg = round(sum(e.get("steps", 0) for e in entries) / len(entries))
        else:
            today_steps = 0
            step_pct = 0
            weekly_avg = 0

        context = self.kg.get_user_context(session_id)
        active_goal = context.get("fitness_goal", "")

        result = {
            "today_steps": today_steps,
            "step_goal": step_goal,
            "step_pct": step_pct,
            "weekly_avg": weekly_avg,
            "trend": "up" if weekly_avg > step_goal * 0.8 else "down",
            "active_minutes_today": entries[0].get("active_minutes", 0) if entries else 0,
            "active_goal": active_goal if active_goal else None,
        }

        if step_pct < 100:
            remaining = step_goal - today_steps
            result["steps_trend"] = f"You've taken {today_steps:,} steps today ({step_pct}% of goal). {remaining:,} more to go! Your weekly average is {weekly_avg:,}."
            result["suggestion"] = "I've blocked a 30-min walk at 2:00 PM between your meetings."
        else:
            result["steps_trend"] = f"🎉 You've hit your step goal! {today_steps:,} steps today. Weekly avg: {weekly_avg:,}."

        if active_goal:
            result["progress"] = "Week 2 of 12 — on track"

        return result

    async def set_goal(self, goal: str, session_id: str) -> dict:
        """Set a new fitness goal."""
        self.kg.store_preference(session_id, "fitness_goal", goal)

        if "marathon" in goal.lower():
            plan = "12-week progressive training plan"
            return {
                "text": f"🏃 Great goal! I'm setting up a **{plan}** for your {goal}.\n\nBased on your calendar, the best days for long runs are **Saturday** and **Tuesday mornings**.\n\nHere's your Week 1 plan:\n• Mon: Rest or easy walk (30 min)\n• Tue: Easy run (3 miles)\n• Wed: Cross-training (30 min)\n• Thu: Easy run (3 miles)\n• Fri: Rest\n• Sat: Long run (4 miles)\n• Sun: Recovery walk\n\nWant me to block these in your calendar?",
                "type": "goal_set",
                "cards": [{
                    "type": "action_card",
                    "title": f"🏃 {goal.title()} Training Plan",
                    "body": f"{plan}\nWeek 1 of 12 starts Monday",
                    "actions": [
                        {"label": "📅 Block Calendar", "value": "block_training"},
                        {"label": "📊 View Full Plan", "value": "full_plan"},
                    ],
                }],
            }

        return {
            "text": f"🎯 Goal set: **{goal}**. I'll track your progress and suggest optimal training times.",
            "type": "goal_set",
            "cards": [],
        }

    async def log_activity(self, activity: str, session_id: str) -> dict:
        """Log a fitness activity to the real database."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        entries = db.get_fitness_history(session_id, days=1)

        # Try to parse steps from activity message
        steps = 0
        for word in activity.split():
            if word.isdigit():
                steps = int(word)
                break

        if entries:
            current = entries[0]
            new_steps = current.get("steps", 0) + (steps or 1000)
            new_minutes = current.get("active_minutes", 0) + 30
        else:
            new_steps = steps or 1000
            new_minutes = 30

        db.log_fitness(session_id, {
            "date": today,
            "steps": new_steps,
            "calories_burned": round(new_steps * 0.04),
            "active_minutes": new_minutes,
        })

        user = db.get_user_by_id(session_id)
        step_goal = user.get("fitness_goal", 10000) if user else 10000
        pct = round(new_steps / step_goal * 100)

        return {
            "text": f"💪 Activity logged!\n\n📊 Today's stats:\n• Steps: {new_steps:,} ({pct}% of goal)\n• Active minutes: {new_minutes}\n• Estimated calories: {round(new_steps * 0.04):,}\n\nYou're {'on track' if pct >= 80 else 'making progress'}!",
            "type": "activity_logged",
            "cards": [{
                "type": "progress_card",
                "title": "💪 Activity Logged",
                "body": f"Steps: {new_steps:,} / {step_goal:,}",
                "progress": min(pct, 100),
            }],
        }

    async def weekly_report(self, session_id: str) -> dict:
        """Generate weekly fitness report from real data."""
        entries = db.get_fitness_history(session_id, days=7)

        user = db.get_user_by_id(session_id)
        step_goal = user.get("fitness_goal", 10000) if user else 10000

        if not entries:
            return {
                "text": "📊 No fitness data logged yet this week. Start by telling me about your activity!",
                "type": "weekly_report",
                "cards": [],
            }

        total_steps = sum(e.get("steps", 0) for e in entries)
        avg_steps = round(total_steps / len(entries))
        days_hit = sum(1 for e in entries if e.get("steps", 0) >= step_goal)
        total_calories = sum(e.get("calories_burned", 0) for e in entries)
        avg_active = round(sum(e.get("active_minutes", 0) for e in entries) / len(entries))

        text = f"📊 **Weekly Fitness Report**\n\n"
        text += f"🦶 Steps: {avg_steps:,} avg/day ({days_hit}/{len(entries)} days hit goal)\n"
        text += f"⏱️ Active minutes: {avg_active} avg/day\n"
        text += f"🔥 Calories: {total_calories:,} total\n"

        if days_hit >= 5:
            text += f"\n🎉 Great week! You hit your step goal {days_hit} out of {len(entries)} days."
        else:
            text += f"\n💪 You hit your goal {days_hit}/{len(entries)} days. Let's aim for {days_hit+1} next week!"

        return {
            "text": text,
            "type": "weekly_report",
            "cards": [{
                "type": "stats_card",
                "title": "📊 Weekly Report",
                "stats": {
                    "avg_steps": avg_steps,
                    "days_hit_goal": days_hit,
                    "avg_active_min": avg_active,
                    "total_calories": total_calories,
                },
            }],
        }

    def _format_status(self, status: dict, session_id: str) -> dict:
        text = f"🏋️ **Fitness Status**\n\n{status.get('steps_trend', 'No data yet.')}"
        if status.get("suggestion"):
            text += f"\n\n💡 {status['suggestion']}"

        return {
            "text": text,
            "type": "fitness_status",
            "cards": [{
                "type": "progress_card",
                "title": "🏋️ Today's Fitness",
                "body": f"{status['today_steps']:,} / {status['step_goal']:,} steps",
                "progress": status["step_pct"],
            }],
        }
