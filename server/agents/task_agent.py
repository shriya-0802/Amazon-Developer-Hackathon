"""Task Agent — Intelligent task management with real database integration."""

from datetime import datetime, timedelta
from memory.knowledge_graph import KnowledgeGraph
import database as db


class TaskAgent:
    """Manages tasks with intelligent prioritization using real user data."""

    def __init__(self, kg: KnowledgeGraph):
        self.kg = kg

    async def handle(self, message: str, entities: dict, session_id: str) -> dict:
        msg = message.lower()

        if any(w in msg for w in ["add", "create", "new task"]):
            task_text = message.replace("add task", "").replace("create task", "").replace("remind me to", "").strip()
            if not task_text:
                task_text = entities.get("task", "New task")

            priority = entities.get("priority", "medium")
            today = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")

            result = db.add_task(session_id, {
                "title": task_text,
                "description": "",
                "priority": priority,
                "category": "general",
                "due_date": today,
            })

            pending = db.get_tasks(session_id, status="pending")

            return {
                "text": f"✅ Added: **{task_text}** (Priority: {priority})\n\nYou now have {len(pending)} pending tasks.",
                "type": "task_added",
                "cards": [{
                    "type": "info_card",
                    "title": "✅ Task Added",
                    "body": f"{task_text}\nPriority: {priority} | Due: Today",
                }],
            }

        elif any(w in msg for w in ["complete", "done", "finish", "mark"]):
            tasks = db.get_tasks(session_id, status="pending")
            if tasks:
                db.complete_task(tasks[0]["id"])
                return {
                    "text": f"🎉 Completed: **{tasks[0]['title']}**!\n\n{len(tasks)-1} tasks remaining.",
                    "type": "task_completed",
                    "cards": [],
                }
            return {"text": "No pending tasks to complete!", "type": "info", "cards": []}

        elif any(w in msg for w in ["list", "show", "what", "pending"]):
            return await self._list_tasks(session_id)

        elif "prioritize" in msg:
            return await self._prioritize(session_id)

        return await self._list_tasks(session_id)

    async def get_priority_tasks(self, session_id: str) -> dict:
        """Get high priority tasks for briefings."""
        all_tasks = db.get_tasks(session_id, status="pending")
        priority = [t for t in all_tasks if t["priority"] == "high"]
        return {"tasks": priority}

    async def _list_tasks(self, session_id: str) -> dict:
        pending = db.get_tasks(session_id, status="pending")

        if not pending:
            return {
                "text": "Here is the status of your task list:",
                "type": "task_list",
                "cards": [{
                    "type": "info_card",
                    "title": "✅ All Caught Up",
                    "body": "You have no pending tasks. Enjoy your day! 🎉",
                }],
            }

        text = f"Here are your {len(pending)} pending tasks:"
        body_text = ""
        for t in pending:
            icon = "🔴" if t["priority"] == "high" else "🟡" if t["priority"] == "medium" else "🟢"
            text += f"{icon} **{t['title']}** — Due: {t.get('due_date', 'TBD')}\n"
            body_text += f"{icon} {t['title']} (Due: {t.get('due_date', 'TBD')})\n"

        return {
            "text": text,
            "type": "task_list",
            "cards": [{
                "type": "info_card",
                "title": "✅ Your Tasks",
                "body": body_text.strip(),
            }],
        }

    async def _prioritize(self, session_id: str) -> dict:
        pending = db.get_tasks(session_id, status="pending")
        if not pending:
            return await self._list_tasks(session_id)
            
        pending.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("priority", "medium"), 1))

        text = "📋 Here's your prioritized task list:\n\n"
        body_text = ""
        for i, t in enumerate(pending, 1):
            text += f"{i}. **{t['title']}** ({t['priority']} priority, due {t.get('due_date', 'TBD')})\n"
            body_text += f"{i}. {t['title']} ({t['priority']} priority)\n"

        if pending:
            text += f"\n💡 I suggest tackling \"{pending[0]['title']}\" first — it's your highest priority item."

        return {
            "text": text,
            "type": "prioritized",
            "cards": [{
                "type": "info_card",
                "title": "📋 Prioritized Tasks",
                "body": body_text.strip(),
            }],
        }
