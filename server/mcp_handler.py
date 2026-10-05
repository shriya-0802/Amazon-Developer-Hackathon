"""
MCP Protocol Handler — Implements MCP spec 2025-11-25
Handles JSON-RPC messages over Streamable HTTP transport.
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

from agents.orchestrator import AgentOrchestrator


class MCPHandler:
    """
    Model Context Protocol handler implementing spec 2025-11-25.
    Supports: initialize, tools/list, tools/call, resources/list,
    resources/read, prompts/list, prompts/get, notifications.
    """

    SERVER_INFO = {
        "name": "lifesync",
        "version": "1.0.0",
    }

    CAPABILITIES = {
        "tools": {"listChanged": True},
        "resources": {"subscribe": True, "listChanged": True},
        "prompts": {"listChanged": True},
        "logging": {},
    }

    def __init__(self, orchestrator: AgentOrchestrator):
        self.orchestrator = orchestrator
        self._notification_queue: asyncio.Queue = asyncio.Queue()
        self._initialized = False

    async def handle_message(self, message: dict) -> dict:
        """Route incoming JSON-RPC message to appropriate handler."""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        handlers = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
            "ping": self._handle_ping,
        }

        handler = handlers.get(method)
        if handler is None:
            return self._error_response(msg_id, -32601, f"Method not found: {method}")

        try:
            result = await handler(params)
            return self._success_response(msg_id, result)
        except Exception as e:
            return self._error_response(msg_id, -32603, str(e))

    async def get_notifications(self) -> AsyncGenerator[dict, None]:
        """Yield server-initiated notifications (for SSE stream)."""
        while True:
            notification = await self._notification_queue.get()
            yield notification

    # ─── Protocol Handlers ──────────────────────────────────────────────

    async def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request — negotiate capabilities."""
        self._initialized = True
        return {
            "protocolVersion": "2025-11-25",
            "capabilities": self.CAPABILITIES,
            "serverInfo": self.SERVER_INFO,
        }

    async def _handle_initialized(self, params: dict) -> dict:
        """Handle initialized notification from client."""
        return {}

    async def _handle_ping(self, params: dict) -> dict:
        """Handle ping request."""
        return {}

    async def _handle_tools_list(self, params: dict) -> dict:
        """List available MCP tools."""
        return {
            "tools": [
                {
                    "name": "morning_briefing",
                    "description": "Generate a proactive morning briefing with calendar, weather, tasks, fitness, and smart suggestions.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "user_name": {
                                "type": "string",
                                "description": "The user's name for personalization",
                            },
                            "include_fitness": {
                                "type": "boolean",
                                "description": "Whether to include fitness data",
                                "default": True,
                            },
                        },
                    },
                },
                {
                    "name": "smart_schedule",
                    "description": "Intelligently analyze and optimize the user's schedule, suggesting time blocks for goals and detecting conflicts.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["analyze", "optimize", "block_time"],
                                "description": "The scheduling action to perform",
                            },
                            "goal": {
                                "type": "string",
                                "description": "A goal to schedule time for (e.g., 'train for half marathon')",
                            },
                        },
                        "required": ["action"],
                    },
                },
                {
                    "name": "smart_shopping",
                    "description": "Manage shopping with pattern recognition, reorder suggestions, and price tracking.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "item": {
                                "type": "string",
                                "description": "Item to shop for",
                            },
                            "action": {
                                "type": "string",
                                "enum": ["search", "reorder", "track", "suggest"],
                                "description": "Shopping action",
                            },
                        },
                        "required": ["action"],
                    },
                },
                {
                    "name": "manage_tasks",
                    "description": "Create, prioritize, and intelligently manage tasks with context-aware scheduling.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["add", "list", "prioritize", "complete", "suggest"],
                                "description": "Task management action",
                            },
                            "task": {
                                "type": "string",
                                "description": "Task description",
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Task priority",
                            },
                        },
                        "required": ["action"],
                    },
                },
                {
                    "name": "fitness_insights",
                    "description": "Track fitness goals, analyze patterns, and provide coaching suggestions.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["status", "set_goal", "log_activity", "weekly_report"],
                                "description": "Fitness action",
                            },
                            "goal": {
                                "type": "string",
                                "description": "Fitness goal description",
                            },
                            "activity": {
                                "type": "string",
                                "description": "Activity to log",
                            },
                        },
                        "required": ["action"],
                    },
                },
                {
                    "name": "remember",
                    "description": "Store information in persistent memory for cross-session context.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "What to remember (category)",
                            },
                            "value": {
                                "type": "string",
                                "description": "The information to store",
                            },
                            "importance": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "default": "medium",
                            },
                        },
                        "required": ["key", "value"],
                    },
                },
            ]
        }

    async def _handle_tools_call(self, params: dict) -> dict:
        """Execute an MCP tool call."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        result = await self.orchestrator.execute_tool(tool_name, arguments)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2) if isinstance(result, dict) else str(result),
                }
            ],
            "isError": False,
        }

    async def _handle_resources_list(self, params: dict) -> dict:
        """List available MCP resources."""
        return {
            "resources": [
                {
                    "uri": "lifesync://user/profile",
                    "name": "User Profile",
                    "description": "Current user profile and preferences",
                    "mimeType": "application/json",
                },
                {
                    "uri": "lifesync://user/memory",
                    "name": "User Memory",
                    "description": "Persistent knowledge graph and learned patterns",
                    "mimeType": "application/json",
                },
                {
                    "uri": "lifesync://schedule/today",
                    "name": "Today's Schedule",
                    "description": "Current day's calendar and optimized schedule",
                    "mimeType": "application/json",
                },
                {
                    "uri": "lifesync://insights/weekly",
                    "name": "Weekly Insights",
                    "description": "Aggregated weekly productivity and wellness insights",
                    "mimeType": "application/json",
                },
            ]
        }

    async def _handle_resources_read(self, params: dict) -> dict:
        """Read an MCP resource."""
        uri = params.get("uri", "")
        result = await self.orchestrator.read_resource(uri)

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(result, indent=2),
                }
            ]
        }

    async def _handle_prompts_list(self, params: dict) -> dict:
        """List available MCP prompts."""
        return {
            "prompts": [
                {
                    "name": "morning_routine",
                    "description": "Start your day with a personalized morning briefing and action plan",
                    "arguments": [
                        {
                            "name": "mood",
                            "description": "How are you feeling today?",
                            "required": False,
                        }
                    ],
                },
                {
                    "name": "weekly_review",
                    "description": "Review your week's accomplishments and plan ahead",
                },
                {
                    "name": "goal_planning",
                    "description": "Set and break down a new personal or professional goal",
                    "arguments": [
                        {
                            "name": "goal",
                            "description": "What goal would you like to achieve?",
                            "required": True,
                        }
                    ],
                },
            ]
        }

    async def _handle_prompts_get(self, params: dict) -> dict:
        """Get a specific MCP prompt."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        prompt = await self.orchestrator.get_prompt(name, arguments)

        return {
            "description": prompt.get("description", ""),
            "messages": prompt.get("messages", []),
        }

    # ─── Response Helpers ───────────────────────────────────────────────

    def _success_response(self, msg_id: Any, result: dict) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }

    def _error_response(self, msg_id: Any, code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
