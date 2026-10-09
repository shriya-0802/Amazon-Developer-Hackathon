"""
Agent Orchestrator — Multi-agent coordination layer.
Orchestrates across calendar, email, tasks, shopping, fitness, and context agents.
Uses persistent memory for cross-session intelligence.
"""

import json
import uuid
import os
from datetime import datetime, timedelta
from typing import Any, Optional
import boto3
from botocore.exceptions import ClientError

from memory.knowledge_graph import KnowledgeGraph
from memory.session_store import SessionStore
from agents.calendar_agent import CalendarAgent
from agents.task_agent import TaskAgent
from agents.shopping_agent import ShoppingAgent
from agents.fitness_agent import FitnessAgent
from agents.context_agent import ContextAgent


class AgentOrchestrator:
    """
    Central orchestrator that coordinates multiple specialist agents
    and maintains coherent cross-session context through a knowledge graph.
    """

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        session_store: SessionStore,
    ):
        self.kg = knowledge_graph
        self.sessions = session_store

        # Initialize specialist agents
        self.calendar = CalendarAgent(knowledge_graph)
        self.tasks = TaskAgent(knowledge_graph)
        self.shopping = ShoppingAgent(knowledge_graph)
        self.fitness = FitnessAgent(knowledge_graph)
        self.context = ContextAgent(knowledge_graph)

    async def process_message(self, message: str, session_id: str) -> dict:
        """
        Process a user message by routing to appropriate agents
        and synthesizing a coherent response.
        """
        # Get/create session
        session = self.sessions.get_or_create(session_id)

        # Classify intent and extract entities
        intent = self._classify_intent(message)
        entities = self._extract_entities(message)

        # Store interaction in memory
        self.kg.add_interaction(session_id, message, intent)

        # Route to appropriate agent(s)
        agent_responses = []

        msg_lower = message.strip().lower()

        # Handle Quick Action Buttons
        if msg_lower.startswith("do: "):
            cmd = msg_lower.replace("do: ", "").strip()
            if cmd == "morning_briefing":
                intent = "morning_briefing"
            elif cmd == "show_schedule":
                intent = "schedule"
            elif cmd == "show_tasks":
                intent = "task"
            elif cmd == "fitness_status":
                intent = "fitness"
            elif cmd == "order_all":
                intent = "shop"
                message = "checkout"  # force checkout behavior
            elif cmd == "block_fitness":
                import asyncio
                asyncio.create_task(self._simulate_notifications(session_id))
                return {
                    "text": "Fitness time blocked successfully! I'll notify you via Email, SMS, and Voice Message before it starts.",
                    "type": "confirmation",
                    "cards": [],
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "trigger_notification": True
                }
            elif cmd == "show_plan":
                return {
                    "text": "Here is your plan for the week:\n- **Mon:** 30m run\n- **Wed:** 45m strength\n- **Fri:** 30m cycling\nI'll add these to your calendar.",
                    "type": "confirmation",
                    "cards": [],
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat()
                }

        if intent in ("morning_briefing", "briefing", "good_morning") or "summary" in msg_lower or "analytics" in msg_lower:
            return await self.generate_briefing(session_id)

        elif intent in ("schedule", "calendar", "meeting", "appointment"):
            result = await self.calendar.handle(message, entities, session_id)
            agent_responses.append(result)

        elif intent in ("task", "todo", "remind", "remember_task"):
            result = await self.tasks.handle(message, entities, session_id)
            agent_responses.append(result)

        elif intent in ("shop", "buy", "order", "purchase", "shopping", "checkout"):
            result = await self.shopping.handle(message, entities, session_id)
            agent_responses.append(result)

        elif intent in ("fitness", "exercise", "workout", "health", "steps", "run", "marathon"):
            result = await self.fitness.handle(message, entities, session_id)
            agent_responses.append(result)

        elif intent in ("weather", "traffic", "commute", "news"):
            result = await self.context.handle(message, entities, session_id)
            agent_responses.append(result)

        elif intent == "remember":
            if any(w in msg_lower for w in ["what", "tell", "show", "list", "do you"]):
                # Retrieve memories
                context = self.kg.get_user_context(session_id)
                if not context:
                    text = "I don't have any specific preferences saved for you yet."
                else:
                    text = "🧠 **Here is what I remember about your profile & preferences:**\n\n"
                    for k, v in context.items():
                        if not v: continue
                        pretty_key = str(k).replace("_", " ").title()
                        text += f"- **{pretty_key}**: {v}\n"
                
                agent_responses.append({
                    "text": text,
                    "type": "memory_retrieval",
                    "cards": [],
                })
            else:
                self.kg.store_preference(session_id, entities.get("key", "general"), message)
                agent_responses.append({
                    "text": "Got it! I'll remember that for future reference. 🧠",
                    "type": "confirmation",
                    "cards": [],
                })
        elif intent == "support":
            # Customer Support Agent Logic
            import database as db
            import uuid
            now = datetime.now().isoformat()
            complaint_id = str(uuid.uuid4())
            db.get_db().execute(
                "INSERT INTO complaints (id, user_id, product_name, description, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (complaint_id, session_id, "Chat Support Escalation", message, "pending", now)
            ).connection.commit()
            
            agent_responses.append({
                "text": "I am so sorry you are experiencing an issue. As your Customer Support AI, I have immediately lodged a formal complaint on your behalf with the details you provided. This has been escalated securely to our Admin Dashboard where our Human and AI support teams will review and resolve it shortly.",
                "type": "support",
                "cards": []
            })
        else:
            # General conversation — use cross-agent intelligence
            result = await self._handle_general(message, entities, session_id)
            agent_responses.append(result)

        # Synthesize final response
        response = self._synthesize_response(agent_responses, session_id)

        # Check for proactive suggestions
        if not msg_lower.startswith("do:"):
            proactive = self._check_proactive_triggers(session_id)
            if proactive:
                response["proactive_suggestions"] = proactive

        # Update session
        self.sessions.update(session_id, message, response)

        return response

    async def _simulate_notifications(self, session_id: str):
        """Simulates sending external notifications to the user."""
        import asyncio
        import json
        from mcp_handler import MCPHandler
        await asyncio.sleep(2)
        print(f"[{session_id}] Sending Email...")
        await asyncio.sleep(1)
        print(f"[{session_id}] Sending SMS...")
        await asyncio.sleep(1)
        print(f"[{session_id}] Sending Voice Message...")
        
        # We can also add a reminder in the DB so it triggers the UI
        try:
            import database as db
            import uuid
            now = datetime.now()
            db.get_db().execute(
                "INSERT INTO events (id, user_id, title, description, start_time, end_time, location, event_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), session_id, "Fitness Block", "Automated fitness block", (now + timedelta(minutes=1)).isoformat(), (now + timedelta(minutes=31)).isoformat(), "Gym", "personal", now.isoformat())
            ).connection.commit()
        except Exception as e:
            print("Error scheduling fitness reminder", e)

    async def generate_briefing(self, session_id: str) -> dict:
        """Generate a comprehensive morning briefing by querying all agents."""
        now = datetime.now()
        user_context = self.kg.get_user_context(session_id)
        user_name = user_context.get("name", "there")

        # Gather data from all agents
        calendar_data = await self.calendar.get_today_schedule(session_id)
        tasks_data = await self.tasks.get_priority_tasks(session_id)
        fitness_data = await self.fitness.get_status(session_id)
        context_data = await self.context.get_morning_context(session_id)
        shopping_data = await self.shopping.get_suggestions(session_id)

        # Build the briefing
        greeting = f"Good morning, {user_name}! ☀️"

        sections = []

        # Weather & Context
        weather = context_data.get("weather", {})
        sections.append({
            "title": "🌤️ Weather",
            "content": f"{weather.get('condition', 'Partly cloudy')}, {weather.get('temp', '72')}°F. {weather.get('advice', 'Great day ahead!')}",
        })

        # Calendar
        meetings = calendar_data.get("meetings", [])
        if meetings:
            meeting_text = f"You have {len(meetings)} meeting{'s' if len(meetings) > 1 else ''} today"
            first = meetings[0]
            meeting_text += f", starting at {first.get('time', '9:00 AM')} ({first.get('title', 'Meeting')})."

            commute = context_data.get("commute", {})
            if commute:
                meeting_text += f" Based on current traffic, leave by {commute.get('leave_by', '8:45 AM')}."

            sections.append({
                "title": "📅 Schedule",
                "content": meeting_text,
            })

        # Tasks
        priority_tasks = tasks_data.get("tasks", [])
        if priority_tasks:
            task_text = f"{len(priority_tasks)} priority task{'s' if len(priority_tasks) > 1 else ''}: "
            task_text += ", ".join([t.get("title", "") for t in priority_tasks[:3]])
            sections.append({
                "title": "✅ Tasks",
                "content": task_text,
            })

        # Fitness
        fitness = fitness_data
        if fitness.get("active_goal"):
            goal_text = f"Goal: {fitness['active_goal']}. "
            if fitness.get("progress"):
                goal_text += f"Progress: {fitness['progress']}. "
            if fitness.get("suggestion"):
                goal_text += fitness["suggestion"]
            sections.append({
                "title": "🏋️ Fitness",
                "content": goal_text,
            })
        elif fitness.get("steps_trend"):
            sections.append({
                "title": "🏋️ Fitness",
                "content": fitness["steps_trend"],
            })

        # Shopping suggestions
        if shopping_data.get("reorder_suggestions"):
            items = shopping_data["reorder_suggestions"]
            sections.append({
                "title": "🛒 Smart Reorder",
                "content": f"Based on your patterns, you might need: {', '.join(items[:2])}",
            })

        # Build cards for MCP Apps
        cards = []
        for section in sections:
            cards.append({
                "type": "info_card",
                "title": section["title"],
                "body": section["content"],
            })

        # Proactive suggestion
        proactive = self._check_proactive_triggers(session_id)
        if proactive:
            cards.append({
                "type": "action_card",
                "title": "💡 Suggestion",
                "body": proactive[0]["text"],
                "actions": proactive[0].get("actions", []),
            })

        return {
            "text": greeting + "\n\nHere's your LifeSync briefing:\n\n" + "\n\n".join(
                [f"**{s['title']}**\n{s['content']}" for s in sections]
            ),
            "type": "briefing",
            "cards": cards,
            "sections": sections,
            "session_id": session_id,
            "timestamp": now.isoformat(),
        }

    async def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute an MCP tool by name."""
        session_id = arguments.pop("session_id", "default")

        tool_handlers = {
            "morning_briefing": self._tool_morning_briefing,
            "smart_schedule": self._tool_smart_schedule,
            "smart_shopping": self._tool_smart_shopping,
            "manage_tasks": self._tool_manage_tasks,
            "fitness_insights": self._tool_fitness_insights,
            "remember": self._tool_remember,
        }

        handler = tool_handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}

        return await handler(arguments, session_id)

    async def read_resource(self, uri: str) -> dict:
        """Read an MCP resource by URI."""
        resource_handlers = {
            "lifesync://user/profile": self._resource_profile,
            "lifesync://user/memory": self._resource_memory,
            "lifesync://schedule/today": self._resource_schedule,
            "lifesync://insights/weekly": self._resource_insights,
        }

        handler = resource_handlers.get(uri)
        if handler:
            return await handler()

        return {"error": f"Unknown resource: {uri}"}

    async def get_prompt(self, name: str, arguments: dict) -> dict:
        """Get an MCP prompt by name."""
        if name == "morning_routine":
            mood = arguments.get("mood", "neutral")
            return {
                "description": "Start your day with a personalized morning briefing",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Generate my morning briefing. I'm feeling {mood} today. Include my schedule, priority tasks, fitness progress, weather, and any smart suggestions based on my patterns.",
                        },
                    }
                ],
            }
        elif name == "goal_planning":
            goal = arguments.get("goal", "")
            return {
                "description": "Set and break down a new goal",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"I want to achieve this goal: {goal}. Break it down into actionable steps, suggest a timeline, and identify time blocks in my schedule.",
                        },
                    }
                ],
            }
        elif name == "weekly_review":
            return {
                "description": "Review your week's accomplishments",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": "Review my week — what did I accomplish, what's pending, how's my fitness, and what should I focus on next week?",
                        },
                    }
                ],
            }

        return {"description": "", "messages": []}

    # ─── Tool Implementations ───────────────────────────────────────────

    async def _tool_morning_briefing(self, args: dict, session_id: str) -> dict:
        user_name = args.get("user_name", "")
        if user_name:
            self.kg.store_preference(session_id, "name", user_name)
        return await self.generate_briefing(session_id)

    async def _tool_smart_schedule(self, args: dict, session_id: str) -> dict:
        action = args.get("action", "analyze")
        goal = args.get("goal", "")
        return await self.calendar.smart_schedule(action, goal, session_id)

    async def _tool_smart_shopping(self, args: dict, session_id: str) -> dict:
        return await self.shopping.handle(
            args.get("item", ""),
            {"action": args.get("action", "suggest"), "item": args.get("item", "")},
            session_id,
        )

    async def _tool_manage_tasks(self, args: dict, session_id: str) -> dict:
        return await self.tasks.handle(
            args.get("task", ""),
            {"action": args.get("action", "list"), "task": args.get("task", ""), "priority": args.get("priority", "medium")},
            session_id,
        )

    async def _tool_fitness_insights(self, args: dict, session_id: str) -> dict:
        action = args.get("action", "status")
        if action == "set_goal":
            return await self.fitness.set_goal(args.get("goal", ""), session_id)
        elif action == "log_activity":
            return await self.fitness.log_activity(args.get("activity", ""), session_id)
        elif action == "weekly_report":
            return await self.fitness.weekly_report(session_id)
        else:
            return await self.fitness.get_status(session_id)

    async def _tool_remember(self, args: dict, session_id: str) -> dict:
        key = args.get("key", "general")
        value = args.get("value", "")
        importance = args.get("importance", "medium")
        self.kg.store_preference(session_id, key, value, importance)
        return {"status": "stored", "key": key, "value": value}

    # ─── Resource Implementations ───────────────────────────────────────

    async def _resource_profile(self) -> dict:
        return self.kg.get_user_context("default")

    async def _resource_memory(self) -> dict:
        return self.kg.get_full_graph("default")

    async def _resource_schedule(self) -> dict:
        return await self.calendar.get_today_schedule("default")

    async def _resource_insights(self) -> dict:
        return await self.fitness.weekly_report("default")

    # ─── Internal Helpers ───────────────────────────────────────────────

    def _classify_intent(self, message: str) -> str:
        """Simple keyword-based intent classification."""
        import re
        msg = message.lower()

        intent_keywords = {
            "morning_briefing": [r"\bgood morning\b", r"\bmorning briefing\b", r"\bstart my day\b", r"\bdaily briefing\b", r"\bwhat's today\b"],
            "schedule": [r"\bschedule\b", r"\bcalendar\b", r"\bmeeting\b", r"\bmeetings\b", r"\bappointment\b", r"\bwhen\b", r"\bblock time\b"],
            "task": [r"\btask\b", r"\btasks\b", r"\btodo\b", r"\bto-do\b", r"\bremind me\b", r"\badd to list\b", r"\bchecklist\b"],
            "shop": [r"\bbuy\b", r"\border\b", r"\bshop\b", r"\bpurchase\b", r"\breorder\b", r"\bout of\b", r"\bneed more\b", r"\blaundry\b", r"\bdetergent\b", r"\bgrocery\b", r"\bcheckout\b", r"\bfresh\b", r"\bmeal plan\b", r"\bingredients\b", r"\bgroceries\b", r"\bcart\b", r"\bplace order\b"],
            "fitness": [r"\bfitness\b", r"\bexercise\b", r"\bworkout\b", r"\bsteps\b", r"\brun\b", r"\bmarathon\b", r"\btraining\b", r"\bgym\b", r"\bwalk\b", r"\bhealth\b"],
            "weather": [r"\bweather\b", r"\brain\b", r"\btemperature\b", r"\bforecast\b"],
            "remember": [r"\bremember\b", r"\bnote that\b", r"\bkeep in mind\b", r"\bdon't forget\b"],
            "support": [r"\bcomplaint\b", r"\bsupport\b", r"\bhelp me with\b", r"\bbad service\b", r"\bbroken\b", r"\bissue\b", r"\bproblem\b", r"\bcustomer service\b", r"\breplace\b", r"\brefund\b", r"\bdamaged\b", r"\bmissing\b", r"\bdelayed\b"],
        }

        for intent_name, patterns in intent_keywords.items():
            for pattern in patterns:
                if re.search(pattern, msg):
                    return intent_name

        return "general"

    def _extract_entities(self, message: str) -> dict:
        """Extract key entities from the message."""
        entities = {}

        # Simple entity extraction
        msg_lower = message.lower()

        # Time references
        time_words = ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for tw in time_words:
            if tw in msg_lower:
                entities["time_ref"] = tw

        # Priority
        if "urgent" in msg_lower or "important" in msg_lower or "high priority" in msg_lower:
            entities["priority"] = "high"
        elif "low priority" in msg_lower or "when you can" in msg_lower:
            entities["priority"] = "low"

        return entities

    async def _handle_general(self, message: str, entities: dict, session_id: str) -> dict:
        """Handle general conversation with context awareness."""
        context = self.kg.get_user_context(session_id)
        
        # Check if we have AWS credentials and use Bedrock Claude 3.5 Sonnet
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_ACCESS_KEY_ID") != "your_access_key_here":
            try:
                client = boto3.client(
                    service_name='bedrock-runtime',
                    region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
                )
                
                system_prompt = f"You are LifeSync, an AI personal operations center for the user. Their context: {json.dumps(context)}. Respond concisely, smartly, and conversationally in plain text."
                
                body = json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": message}]
                })
                
                response = client.invoke_model(
                    body=body,
                    modelId='anthropic.claude-3-5-haiku-20241022-v1:0',
                    accept='application/json',
                    contentType='application/json'
                )
                
                response_body = json.loads(response.get('body').read())
                llm_response = response_body.get('content', [{}])[0].get('text', '')
                
                return {
                    "text": llm_response + "\n\n*(Powered by AWS Bedrock)*",
                    "type": "llm_response",
                    "cards": [],
                }
            except Exception as e:
                print(f"Bedrock Error: {e}")
                # Fallback to Gemini if AWS fails
                if os.environ.get("GEMINI_API_KEY"):
                    try:
                        import urllib.request
                        gemini_key = os.environ.get("GEMINI_API_KEY")
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
                        
                        system_prompt = f"You are LifeSync, an AI personal operations center. User context: {json.dumps(context)}. Respond concisely and smartly in plain text."
                        
                        payload = json.dumps({
                            "contents": [{"parts": [{"text": f"System context: {system_prompt}\nUser message: {message}"}]}]
                        }).encode('utf-8')
                        
                        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req) as response:
                            resp_body = json.loads(response.read().decode('utf-8'))
                            gemini_text = resp_body['candidates'][0]['content']['parts'][0]['text']
                            
                            return {
                                "text": gemini_text + "\n\n*(Powered by Gemini)*",
                                "type": "llm_response",
                                "cards": [],
                            }
                    except Exception as ge:
                        print(f"Gemini Error: {ge}")
        # Check if we can make a smart response based on memory
        memories = self.kg.search_memories(session_id, message)
        if memories:
            memory_context = "; ".join([m["value"] for m in memories[:3]])
            return {
                "text": f"Based on what I know about you: {memory_context}\n\nHow can I help with this?",
                "type": "contextual",
                "cards": [],
            }

        # Fallback if no LLM APIs are configured or if they fail
        msg_lower = message.lower()
        if "what is this" in msg_lower or "platform" in msg_lower or "who are you" in msg_lower:
            return {
                "text": "I am LifeSync, your AI personal operations center! I help you manage your daily schedule, track tasks, monitor fitness goals, and handle Amazon smart shopping—all from one unified dashboard.",
                "type": "general",
                "cards": []
            }
        elif "how" in msg_lower and ("work" in msg_lower or "use" in msg_lower):
            return {
                "text": "You can type commands like 'add milk to shopping list', 'log 5000 steps', 'what is my schedule today', or use the Quick Action buttons in the sidebar to interact with me.",
                "type": "general",
                "cards": []
            }

        return {
            "text": f"You asked: *\"{message}\"*\n\nI'm currently running in local-only mode (no LLM API key detected), so I can't generate a custom conversational response right now. But I can still manage your schedule, track tasks, suggest smart shopping, and monitor fitness goals. What would you like to do?",
            "type": "general",
            "cards": [
                {
                    "type": "action_card",
                    "title": "Quick Actions",
                    "body": "Here's what I can do for you:",
                    "actions": [
                        {"label": "☀️ Morning Briefing", "value": "morning_briefing"},
                        {"label": "📅 My Schedule", "value": "show_schedule"},
                        {"label": "✅ My Tasks", "value": "show_tasks"},
                        {"label": "🏋️ Fitness Status", "value": "fitness_status"},
                    ],
                }
            ],
        }

    def _synthesize_response(self, agent_responses: list, session_id: str) -> dict:
        """Combine multiple agent responses into a coherent response."""
        if not agent_responses:
            return {
                "text": "I'm ready to help!",
                "type": "general",
                "cards": [],
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
            }

        # For now, use the primary response
        primary = agent_responses[0]
        primary["session_id"] = session_id
        primary["timestamp"] = datetime.now().isoformat()

        return primary

    def _check_proactive_triggers(self, session_id: str) -> list:
        """Check for proactive suggestions based on patterns and context."""
        suggestions = []
        context = self.kg.get_user_context(session_id)
        patterns = self.kg.get_patterns(session_id)

        # Check for reorder patterns
        reorder = patterns.get("shopping_reorder")
        if reorder:
            suggestions.append({
                "text": f"I noticed you typically reorder {reorder['item']} every {reorder['interval']}. Want me to set that up?",
                "type": "shopping",
                "actions": [
                    {"label": "Set Up Auto-Reorder", "value": "auto_reorder"},
                    {"label": "Remind Me Later", "value": "dismiss"},
                ],
            })

        # Check for fitness goal progress
        fitness_goal = context.get("fitness_goal")
        if fitness_goal and int(fitness_goal) != 10000:
            suggestions.append({
                "text": f"You mentioned your goal: {fitness_goal}. I've identified optimal time slots this week. Want me to block them?",
                "type": "fitness",
                "actions": [
                    {"label": "Block Time", "value": "block_fitness"},
                    {"label": "Show Plan", "value": "show_plan"},
                ],
            })

        return suggestions
