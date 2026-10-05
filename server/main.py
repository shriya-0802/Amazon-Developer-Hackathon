"""
LifeSync MCP Server — AI-Powered Proactive Personal Operations Center
Main entry point with FastAPI + MCP Streamable HTTP transport
"""

import asyncio
import json
import uuid
import os
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, timedelta
from typing import Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from mcp_handler import MCPHandler
from agents.orchestrator import AgentOrchestrator
from memory.knowledge_graph import KnowledgeGraph
from memory.session_store import SessionStore
import database as db


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    # Initialize core components
    app.state.knowledge_graph = KnowledgeGraph()
    app.state.session_store = SessionStore()
    app.state.orchestrator = AgentOrchestrator(
        knowledge_graph=app.state.knowledge_graph,
        session_store=app.state.session_store,
    )
    app.state.mcp_handler = MCPHandler(orchestrator=app.state.orchestrator)

    print("🧠 LifeSync MCP Server initialized")
    print("📡 Streamable HTTP transport ready")
    print(f"🔗 Server running at http://localhost:8000")

    yield

    # Cleanup
    print("👋 LifeSync MCP Server shutting down")


app = FastAPI(
    title="LifeSync MCP Server",
    description="AI-Powered Proactive Personal Operations Center",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for web simulation
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── MCP Streamable HTTP Endpoint ───────────────────────────────────────────

@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """
    MCP Streamable HTTP transport endpoint.
    Implements MCP spec 2025-11-25 over Streamable HTTP.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    handler: MCPHandler = request.app.state.mcp_handler
    response = await handler.handle_message(body)

    return JSONResponse(content=response)


@app.get("/mcp")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for server-initiated notifications (proactive behaviors)."""
    handler: MCPHandler = request.app.state.mcp_handler

    async def event_stream():
        async for event in handler.get_notifications():
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ─── REST API for Web Simulation ────────────────────────────────────────────

@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """
    REST endpoint for the web simulation UI.
    Processes user messages and returns agent responses.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = body.get("message", "")
    session_id = body.get("session_id", str(uuid.uuid4()))

    orchestrator: AgentOrchestrator = request.app.state.orchestrator

    # Process the message through the agent orchestrator
    response = await orchestrator.process_message(
        message=message,
        session_id=session_id,
    )

    return JSONResponse(content=response)


@app.get("/api/briefing")
async def get_briefing(request: Request):
    """Generate a proactive morning briefing."""
    orchestrator: AgentOrchestrator = request.app.state.orchestrator
    session_id = request.query_params.get("session_id", "default")

    briefing = await orchestrator.generate_briefing(session_id=session_id)
    return JSONResponse(content=briefing)


@app.get("/api/memory/{session_id}")
async def get_memory(session_id: str, request: Request):
    """Get the knowledge graph for a session (for demo visualization)."""
    kg: KnowledgeGraph = request.app.state.knowledge_graph
    memory = kg.get_user_context(session_id)
    return JSONResponse(content=memory)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "LifeSync MCP Server",
        "version": "1.0.0",
        "mcp_spec": "2025-11-25",
        "transport": "Streamable HTTP",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── Auth API ───────────────────────────────────────────────────────────────

@app.post("/api/auth/signup")
async def signup(request: Request):
    """Register a new user."""
    body = await request.json()
    email = body.get("email", "").strip()
    name = body.get("name", "").strip()
    password = body.get("password", "")
    role = body.get("role", "user")

    if not email or not name or not password:
        raise HTTPException(status_code=400, detail="Email, name, and password are required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    result = db.create_user(email, name, password, role)
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return JSONResponse(content=result)


@app.post("/api/auth/login")
async def login(request: Request):
    """Authenticate a user."""
    body = await request.json()
    email = body.get("email", "").strip()
    password = body.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    result = db.authenticate_user(email, password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return JSONResponse(content=result)


@app.get("/api/auth/me")
async def get_current_user(request: Request):
    """Get current user from token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ")[1]
    payload = db.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Don't return password hash
    user.pop("password_hash", None)
    return JSONResponse(content=user)


# ─── Admin API ──────────────────────────────────────────────────────────────

@app.get("/api/admin/users")
async def admin_list_users(request: Request):
    """Admin: List all users."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = db.verify_token(auth.split(" ")[1])
    if not payload or payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    users = db.get_all_users()
    return JSONResponse(content={"users": users, "total": len(users)})


# ─── Shopping API ───────────────────────────────────────────────────────────

@app.get("/api/shopping/{user_id}")
async def get_shopping(user_id: str):
    """Get user's shopping list."""
    items = db.get_shopping_list(user_id)
    return JSONResponse(content={"items": items, "total": len(items)})


@app.post("/api/shopping/{user_id}")
async def add_shopping(user_id: str, request: Request):
    """Add item to shopping list."""
    body = await request.json()
    result = db.add_shopping_item(user_id, body)
    return JSONResponse(content=result)


@app.put("/api/shopping/toggle/{item_id}")
async def toggle_shopping_item(item_id: str):
    """Toggle purchased status."""
    result = db.toggle_purchased(item_id)
    return JSONResponse(content=result)


# ─── Tasks API ──────────────────────────────────────────────────────────────

@app.get("/api/tasks/{user_id}")
async def get_user_tasks(user_id: str, status: str = None):
    """Get user tasks."""
    tasks = db.get_tasks(user_id, status)
    return JSONResponse(content={"tasks": tasks, "total": len(tasks)})


@app.post("/api/tasks/{user_id}")
async def add_user_task(user_id: str, request: Request):
    """Add a new task."""
    body = await request.json()
    result = db.add_task(user_id, body)
    return JSONResponse(content=result)


@app.put("/api/tasks/complete/{task_id}")
async def complete_user_task(task_id: str):
    """Mark task as completed."""
    result = db.complete_task(task_id)
    return JSONResponse(content=result)


# ─── Fitness API ────────────────────────────────────────────────────────────

@app.post("/api/fitness/{user_id}")
async def log_user_fitness(user_id: str, request: Request):
    """Log a fitness entry."""
    body = await request.json()
    result = db.log_fitness(user_id, body)
    return JSONResponse(content=result)


@app.get("/api/fitness/{user_id}")
async def get_user_fitness(user_id: str, days: int = 7):
    """Get fitness history."""
    entries = db.get_fitness_history(user_id, days)
    return JSONResponse(content={"entries": entries, "total": len(entries)})


# ─── Events / Schedule API ──────────────────────────────────────────────────

@app.get("/api/events/{user_id}")
async def get_user_events(user_id: str, date: str = None):
    """Get user events."""
    events = db.get_events(user_id, date)
    return JSONResponse(content={"events": events, "total": len(events)})


@app.post("/api/events/{user_id}")
async def add_user_event(user_id: str, request: Request):
    """Add a calendar event."""
    body = await request.json()
    result = db.add_event(user_id, body)
    return JSONResponse(content=result)


# ─── Activity Log API ──────────────────────────────────────────────────────

@app.get("/api/activity/{user_id}")
async def get_user_activity(user_id: str, limit: int = 20):
    """Get user activity log."""
    log = db.get_activity_log(user_id, limit)
    return JSONResponse(content={"activities": log, "total": len(log)})


# ─── Amazon Product Search (Simulated) ──────────────────────────────────────

@app.get("/api/amazon/search")
async def amazon_product_search(q: str = ""):
    """Simulated Amazon Product Search — returns realistic product data."""
    # In production, this would use Amazon Product Advertising API (PA-API 5.0)
    products = [
        {"asin": "B07QS7GYPF", "title": "Tide PODS Laundry Detergent Soap Pods, 42ct",
         "price": 15.99, "rating": 4.7, "reviews": 128453, "category": "Household",
         "image": "https://m.media-amazon.com/images/I/71VU5LMQL3L._AC_SL1500_.jpg",
         "url": "https://www.amazon.com/dp/B07QS7GYPF", "prime": True},
        {"asin": "B07NQDSM45", "title": "Oatly Original Oat Milk, 32 fl oz",
         "price": 5.49, "rating": 4.5, "reviews": 34821, "category": "Grocery",
         "image": "https://m.media-amazon.com/images/I/61FZ09Q4JwL._SL1500_.jpg",
         "url": "https://www.amazon.com/dp/B07NQDSM45", "prime": True},
        {"asin": "B09JQ7J5Q5", "title": "Samsung Galaxy Buds2 Pro Wireless Earbuds",
         "price": 149.99, "rating": 4.4, "reviews": 15678, "category": "Electronics",
         "image": "https://m.media-amazon.com/images/I/51cVeGfdkHL._AC_SL1500_.jpg",
         "url": "https://www.amazon.com/dp/B09JQ7J5Q5", "prime": True},
        {"asin": "B07K3HLBZ1", "title": "RXBAR Protein Bars, Variety Pack, 12 Count",
         "price": 24.99, "rating": 4.6, "reviews": 45213, "category": "Grocery",
         "image": "https://m.media-amazon.com/images/I/81Y7nVGi0QL._SL1500_.jpg",
         "url": "https://www.amazon.com/dp/B07K3HLBZ1", "prime": True},
        {"asin": "B0B5F54Z3Q", "title": "Amazon Echo Dot (5th Gen) Smart Speaker with Alexa",
         "price": 49.99, "rating": 4.7, "reviews": 298456, "category": "Electronics",
         "image": "https://m.media-amazon.com/images/I/71xoR4A6q-L._AC_SL1000_.jpg",
         "url": "https://www.amazon.com/dp/B0B5F54Z3Q", "prime": True},
    ]

    if q:
        q_lower = q.lower()
        filtered = [p for p in products if q_lower in p["title"].lower() or q_lower in p["category"].lower()]
        return JSONResponse(content={"products": filtered or products[:3], "query": q})

    return JSONResponse(content={"products": products, "query": q})


# ─── Main ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info",
    )
