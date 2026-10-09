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
from fastapi.staticfiles import StaticFiles
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


# ─── Real-time Reminder Endpoint ────────────────────────────────────────────

@app.get("/api/reminders/{user_id}")
async def get_active_reminders(user_id: str):
    """Check for upcoming events within the next 60 minutes and return them as reminders."""
    now = datetime.now()
    window_end = now + timedelta(minutes=60)
    
    events = db.get_events(user_id)
    reminders = []
    
    for event in events:
        try:
            # Parse start_time — handles both "2026-10-05T16:42" and "2026-10-05T16:42:00"
            start_str = event.get("start_time", "")
            if not start_str:
                continue
            
            # Try multiple formats
            event_time = None
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    event_time = datetime.strptime(start_str, fmt)
                    break
                except ValueError:
                    continue
            
            if event_time is None:
                continue
            
            # Check if event is within the reminder window (now to 60 min from now)
            if now <= event_time <= window_end:
                mins_left = int((event_time - now).total_seconds() / 60)
                reminders.append({
                    "id": event.get("id"),
                    "title": event.get("title", "Event"),
                    "time": start_str,
                    "minutes_until": mins_left,
                    "message": f"⏰ \"{event.get('title')}\" starts in {mins_left} minute{'s' if mins_left != 1 else ''}!",
                    "type": "event_reminder"
                })
            
            # Also check for events happening today that haven't passed
            if event_time.date() == now.date() and event_time > now:
                hrs_left = int((event_time - now).total_seconds() / 3600)
                if hrs_left > 1 and hrs_left <= 24:
                    reminders.append({
                        "id": event.get("id"),
                        "title": event.get("title", "Event"),
                        "time": start_str,
                        "hours_until": hrs_left,
                        "message": f"📅 \"{event.get('title')}\" is scheduled for today at {event_time.strftime('%I:%M %p')} ({hrs_left}h away)",
                        "type": "today_event"
                    })
        except Exception as e:
            print(f"Reminder parse error: {e}")
            continue
    
    return JSONResponse(content={"reminders": reminders, "total": len(reminders), "checked_at": now.isoformat()})


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
        "timestamp": (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat(),
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

    phone = body.get("phone", "").strip()
    age = body.get("age")
    sex = body.get("sex")
    height_cm = body.get("height_cm")
    weight_kg = body.get("weight_kg")
    diet = body.get("diet")
    location = body.get("location")

    if not email or not name or not password:
        raise HTTPException(status_code=400, detail="Email, name, and password are required")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    result = db.create_user(email, name, password, role, phone, age=age, sex=sex, height_cm=height_cm, weight_kg=weight_kg, diet=diet, location=location)
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


@app.delete("/api/shopping/{item_id}")
async def delete_shopping_item(item_id: str):
    """Delete item from shopping list."""
    result = db.delete_shopping_item(item_id)
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


@app.delete("/api/events/{event_id}")
async def delete_user_event(event_id: str):
    """Delete a calendar event."""
    conn = db.get_db()
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return JSONResponse(content={"status": "deleted"})


@app.put("/api/auth/me")
async def update_profile(request: Request):
    """Update user profile/preferences."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ")[1]
    payload = db.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    body = await request.json()
    db.update_user_preferences(payload["sub"], body)
    return JSONResponse(content={"status": "updated"})


# ─── Activity Log API ──────────────────────────────────────────────────────

@app.get("/api/activity/{user_id}")
async def get_user_activity(user_id: str, limit: int = 20):
    """Get user activity log."""
    log = db.get_activity_log(user_id, limit)
    return JSONResponse(content={"activities": log, "total": len(log)})


# ─── Orders / Tracking API ──────────────────────────────────────────────────

@app.get("/api/orders/{user_id}")
async def get_user_orders(user_id: str):
    """Get user's Amazon orders for tracking."""
    orders = db.get_orders(user_id)
    return JSONResponse(content={"orders": orders, "total": len(orders)})


# ─── Complaints API ─────────────────────────────────────────────────────────

@app.get("/api/complaints/{user_id}")
async def get_user_complaints(user_id: str):
    """Get complaints for a user."""
    complaints = db.get_complaints(user_id)
    return JSONResponse(content={"complaints": complaints, "total": len(complaints)})

@app.post("/api/complaints/{user_id}")
async def file_complaint(user_id: str, request: Request):
    """File a new complaint."""
    body = await request.json()
    result = db.add_complaint(user_id, body)
    return JSONResponse(content=result)


# ─── Admin / Maintenance Endpoints ──────────────────────────────────────────

@app.get("/api/admin/complaints")
async def get_all_complaints():
    """Admin dashboard: get all complaints."""
    # In a real app, this would be protected by an admin token
    complaints = db.get_complaints()
    return JSONResponse(content={"complaints": complaints, "total": len(complaints)})

@app.put("/api/admin/complaints/{complaint_id}/resolve")
async def admin_resolve_complaint(complaint_id: str, request: Request):
    """Admin dashboard: resolve a complaint."""
    body = await request.json()
    resolution = body.get("resolution", "Resolved by Admin")
    result = db.resolve_complaint(complaint_id, resolution)
    return JSONResponse(content=result)


@app.post("/api/users/{user_id}/reset")
async def reset_user_data(user_id: str):
    """Reset all data for a specific user, keeping their account."""
    conn = db.get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM shopping_items WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM fitness_entries WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM activity_log WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM complaints WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
    
    return JSONResponse(content={"message": "User data has been completely reset"})

@app.delete("/api/users/{user_id}")
async def delete_user_account(user_id: str):
    """Delete a user account and all associated data."""
    conn = db.get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM events WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM shopping_items WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM fitness_entries WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM activity_log WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()
        
    return JSONResponse(content={"message": "Account successfully deleted"})


# ─── Amazon Product Search (Simulated) ──────────────────────────────────────

import urllib.parse

@app.get("/api/amazon/search")
async def amazon_product_search(q: str = "", category: str = ""):
    """Simulated Amazon Product Search — returns realistic product data with live Amazon links."""
    products = [
        # Grocery
        {"asin": "B07NQDSM45", "title": "Oatly Oat Milk Original, 32 fl oz (Pack of 6)",
         "price": 32.99, "rating": 4.5, "reviews": 34821, "category": "Grocery",
         "image": "https://m.media-amazon.com/images/I/71VBwnLRfPL._SL1500_.jpg", "prime": True,
         "badge": "Best Seller"},
        {"asin": "B07K3HLBZ1", "title": "RXBAR Protein Bars Variety Pack, 12 Count",
         "price": 24.99, "rating": 4.6, "reviews": 45213, "category": "Grocery",
         "image": "https://m.media-amazon.com/images/I/81Y7nVGi0QL._SL1500_.jpg", "prime": True,
         "badge": "Amazon's Choice"},
        {"asin": "B077ZJ3MQB", "title": "Nescafé Gold Blend Instant Coffee, 200g",
         "price": 14.99, "rating": 4.7, "reviews": 89234, "category": "Grocery",
         "image": "https://m.media-amazon.com/images/I/71nxWEQdaEL._SL1500_.jpg", "prime": True,
         "badge": None},
        # Electronics
        {"asin": "B0B5F54Z3Q", "title": "Amazon Echo Dot (5th Gen) Smart Speaker with Alexa",
         "price": 49.99, "rating": 4.7, "reviews": 298456, "category": "Electronics",
         "image": "https://m.media-amazon.com/images/I/71xoR4A6q-L._AC_SL1000_.jpg", "prime": True,
         "badge": "Best Seller"},
        {"asin": "B09JQ7J5Q5", "title": "Samsung Galaxy Buds2 Pro Wireless Earbuds, 3D Audio",
         "price": 149.99, "rating": 4.4, "reviews": 15678, "category": "Electronics",
         "image": "https://m.media-amazon.com/images/I/51cVeGfdkHL._AC_SL1500_.jpg", "prime": True,
         "badge": None},
        {"asin": "B08C1W5N87", "title": "Anker 65W Fast Charger, USB C Charger",
         "price": 19.99, "rating": 4.8, "reviews": 67432, "category": "Electronics",
         "image": "https://m.media-amazon.com/images/I/51YIkFNNs5L._AC_SL1500_.jpg", "prime": True,
         "badge": "Amazon's Choice"},
        # Household
        {"asin": "B07QS7GYPF", "title": "Tide PODS 3-in-1 HE Turbo Laundry Detergent, 42 Count",
         "price": 15.99, "rating": 4.7, "reviews": 128453, "category": "Household",
         "image": "https://m.media-amazon.com/images/I/71VU5LMQL3L._AC_SL1500_.jpg", "prime": True,
         "badge": "Best Seller"},
        {"asin": "B081VH5J1X", "title": "Bounty Select-A-Size Paper Towels, 12 Double Rolls",
         "price": 29.99, "rating": 4.6, "reviews": 213421, "category": "Household",
         "image": "https://m.media-amazon.com/images/I/81mZmQqOdJL._SL1500_.jpg", "prime": True,
         "badge": None},
        # Health
        {"asin": "B001GCU6F2", "title": "Garden of Life Vitamin Code Raw D3, 2000 IU, 60 Capsules",
         "price": 19.99, "rating": 4.5, "reviews": 28743, "category": "Health",
         "image": "https://m.media-amazon.com/images/I/71m0wA1BWKL._SL1500_.jpg", "prime": True,
         "badge": None},
        {"asin": "B07D9N5PGM", "title": "Optimum Nutrition Gold Standard 100% Whey Protein, Vanilla, 5 lb",
         "price": 69.99, "rating": 4.7, "reviews": 184321, "category": "Health",
         "image": "https://m.media-amazon.com/images/I/716bRiXRtaL._SL1500_.jpg", "prime": True,
         "badge": "Best Seller"},
        # Books
        {"asin": "1984740965", "title": "Atomic Habits by James Clear — Paperback",
         "price": 13.79, "rating": 4.8, "reviews": 534219, "category": "Books",
         "image": "https://m.media-amazon.com/images/I/81bGKUa1e0L._SL1500_.jpg", "prime": True,
         "badge": "Best Seller"},
        {"asin": "0593185684", "title": "The Psychology of Money by Morgan Housel",
         "price": 12.99, "rating": 4.7, "reviews": 298431, "category": "Books",
         "image": "https://m.media-amazon.com/images/I/71g2ednj0JL._SL1500_.jpg", "prime": True,
         "badge": None},
    ]

    for p in products:
        # Live Amazon search link
        p["url"] = f"https://www.amazon.com/s?k={urllib.parse.quote(p['title'])}&tag=lifesync-20"

    # Category filter
    if category:
        products = [p for p in products if p["category"].lower() == category.lower()]

    # Search filter
    if q:
        q_lower = q.lower()
        filtered = [p for p in products if q_lower in p["title"].lower() or q_lower in p["category"].lower()]
        return JSONResponse(content={"products": filtered or products[:4], "query": q, "total": len(filtered or products[:4])})

    return JSONResponse(content={"products": products[:8], "query": q, "total": len(products)})


# ─── Static Frontend Serving (For Render Deployment) ───────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
web_dir = os.path.join(BASE_DIR, "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")

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
