"""
LifeSync Database — SQLite User & Data Storage
Simulates a production-grade DynamoDB-style user store using SQLite.
Stores users, sessions, shopping lists, tasks, and activity logs.
"""

import sqlite3
import os
import uuid
import json
from datetime import datetime, timedelta
import bcrypt
from jose import jwt

# JWT Config
SECRET_KEY = os.environ.get("JWT_SECRET", "lifesync-hackathon-secret-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

DB_PATH = os.path.join(os.path.dirname(__file__), "lifesync.db")


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize all database tables."""
    conn = get_db()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            avatar_url TEXT,
            preferences TEXT DEFAULT '{}',
            fitness_goal INTEGER DEFAULT 10000,
            diet_preference TEXT DEFAULT 'none',
            created_at TEXT NOT NULL,
            last_login TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # Sessions / activity log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Shopping list items
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shopping_items (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            quantity INTEGER DEFAULT 1,
            estimated_price REAL,
            amazon_asin TEXT,
            amazon_url TEXT,
            is_purchased INTEGER DEFAULT 0,
            is_auto_reorder INTEGER DEFAULT 0,
            reorder_frequency_days INTEGER,
            last_ordered TEXT,
            next_reorder TEXT,
            added_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # User tasks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'medium',
            category TEXT DEFAULT 'personal',
            due_date TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Fitness tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fitness_entries (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            steps INTEGER DEFAULT 0,
            calories_burned INTEGER DEFAULT 0,
            active_minutes INTEGER DEFAULT 0,
            water_glasses INTEGER DEFAULT 0,
            sleep_hours REAL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Schedule / Calendar events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_time TEXT NOT NULL,
            end_time TEXT,
            location TEXT,
            event_type TEXT DEFAULT 'meeting',
            is_recurring INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Complaints system
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            order_id TEXT,
            category TEXT DEFAULT 'general',
            description TEXT NOT NULL,
            status TEXT DEFAULT 'open',
            resolution TEXT,
            resolved_by TEXT,
            created_at TEXT NOT NULL,
            resolved_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Order tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            amazon_url TEXT,
            quantity INTEGER DEFAULT 1,
            total_price REAL,
            status TEXT DEFAULT 'processing',
            estimated_delivery TEXT,
            tracking_id TEXT,
            ordered_at TEXT NOT NULL,
            delivered_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print("📦 Database initialized: lifesync.db")


# ── User Management ─────────────────────────────────────────────────

def create_user(email: str, name: str, password: str, role: str = "user", phone: str = "", **kwargs) -> dict:
    """Create a new user with hashed password."""
    conn = get_db()
    cursor = conn.cursor()

    # Check if email already exists
    existing = cursor.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return {"error": "Email already registered"}

    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    
    prefs_dict = {"phone": phone} if phone else {}
    for k in ["age", "sex", "height_cm", "weight_kg", "diet", "location"]:
        if kwargs.get(k):
            prefs_dict[k] = kwargs.get(k)
            
    preferences = json.dumps(prefs_dict)

    cursor.execute("""
        INSERT INTO users (id, email, name, password_hash, role, created_at, avatar_url, preferences)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, email.lower(), name, password_hash, role, now,
        f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=FF9900&color=fff&bold=true",
        preferences
    ))

    # Log the activity
    cursor.execute("""
        INSERT INTO activity_log (id, user_id, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), user_id, "account_created", json.dumps({"role": role}), now))

    # Seed some default data for demo
    _seed_user_data(cursor, user_id, now)

    conn.commit()
    conn.close()

    token = create_access_token({"sub": user_id, "email": email, "role": role, "name": name})

    return {
        "user_id": user_id,
        "email": email,
        "name": name,
        "role": role,
        "token": token,
        "created_at": now,
    }


def authenticate_user(email: str, password: str) -> dict:
    """Authenticate a user and return a JWT token."""
    conn = get_db()
    cursor = conn.cursor()

    user = cursor.execute("SELECT * FROM users WHERE email = ? AND is_active = 1", (email.lower(),)).fetchone()
    if not user:
        conn.close()
        return {"error": "Invalid email or password"}

    if not bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
        conn.close()
        return {"error": "Invalid email or password"}

    # Update last login
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    cursor.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, user["id"]))

    # Log activity
    cursor.execute("""
        INSERT INTO activity_log (id, user_id, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), user["id"], "login", "{}", now))

    conn.commit()
    conn.close()

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
    })

    return {
        "user_id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "token": token,
        "avatar_url": user["avatar_url"],
    }


def get_user_by_id(user_id: str) -> dict:
    """Get user profile by ID."""
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user:
        return None
    return dict(user)


def get_all_users() -> list:
    """Admin: Get all users."""
    conn = get_db()
    users = conn.execute("SELECT id, email, name, role, created_at, last_login, is_active FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(u) for u in users]


def update_user_preferences(user_id: str, preferences: dict) -> dict:
    """Update user preferences."""
    conn = get_db()
    conn.execute("UPDATE users SET preferences = ? WHERE id = ?", (json.dumps(preferences), user_id))
    conn.commit()
    conn.close()
    return {"status": "updated"}


# ── Shopping / Amazon Store ──────────────────────────────────────────

def get_shopping_list(user_id: str) -> list:
    """Get user's shopping list."""
    conn = get_db()
    items = conn.execute(
        "SELECT * FROM shopping_items WHERE user_id = ? ORDER BY added_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(i) for i in items]


def add_shopping_item(user_id: str, item: dict) -> dict:
    """Add item to shopping list."""
    conn = get_db()
    item_id = str(uuid.uuid4())
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()

    conn.execute("""
        INSERT INTO shopping_items (id, user_id, product_name, category, quantity, estimated_price,
            amazon_asin, amazon_url, is_auto_reorder, reorder_frequency_days, added_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item_id, user_id,
        item.get("product_name", ""),
        item.get("category", "general"),
        item.get("quantity", 1),
        item.get("estimated_price"),
        item.get("amazon_asin"),
        item.get("amazon_url"),
        item.get("is_auto_reorder", 0),
        item.get("reorder_frequency_days"),
        now,
    ))
    conn.commit()
    conn.close()
    return {"id": item_id, "status": "added"}


def toggle_purchased(item_id: str) -> dict:
    """Toggle purchased status of a shopping item."""
    conn = get_db()
    item = conn.execute("SELECT is_purchased FROM shopping_items WHERE id = ?", (item_id,)).fetchone()
    if not item:
        conn.close()
        return {"error": "Item not found"}
    new_status = 0 if item["is_purchased"] else 1
    conn.execute("UPDATE shopping_items SET is_purchased = ? WHERE id = ?", (new_status, item_id))
    conn.commit()
    conn.close()
    return {"status": "toggled", "is_purchased": bool(new_status)}


# ── Tasks ────────────────────────────────────────────────────────────

def get_tasks(user_id: str, status: str = None) -> list:
    """Get user tasks, optionally filtered by status."""
    conn = get_db()
    if status:
        rows = conn.execute("SELECT * FROM tasks WHERE user_id = ? AND status = ? ORDER BY due_date", (user_id, status)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tasks WHERE user_id = ? ORDER BY due_date", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_task(user_id: str, task: dict) -> dict:
    """Add a new task."""
    conn = get_db()
    task_id = str(uuid.uuid4())
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    conn.execute("""
        INSERT INTO tasks (id, user_id, title, description, priority, category, due_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        task_id, user_id,
        task.get("title", ""),
        task.get("description", ""),
        task.get("priority", "medium"),
        task.get("category", "personal"),
        task.get("due_date"),
        "pending",
        now,
    ))
    conn.commit()
    conn.close()
    return {"id": task_id, "status": "created"}


def complete_task(task_id: str) -> dict:
    """Mark a task as completed."""
    conn = get_db()
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    conn.execute("UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?", (now, task_id))
    conn.commit()
    conn.close()
    return {"status": "completed"}


# ── Fitness ──────────────────────────────────────────────────────────

def log_fitness(user_id: str, entry: dict) -> dict:
    """Log a fitness entry."""
    conn = get_db()
    entry_id = str(uuid.uuid4())
    today = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d")
    conn.execute("""
        INSERT OR REPLACE INTO fitness_entries (id, user_id, date, steps, calories_burned, active_minutes, water_glasses, sleep_hours, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entry_id, user_id, entry.get("date", today),
        entry.get("steps", 0), entry.get("calories_burned", 0),
        entry.get("active_minutes", 0), entry.get("water_glasses", 0),
        entry.get("sleep_hours", 0), entry.get("notes", ""),
    ))
    conn.commit()
    conn.close()
    return {"id": entry_id, "status": "logged"}


def get_fitness_history(user_id: str, days: int = 7) -> list:
    """Get fitness history for the last N days."""
    conn = get_db()
    cutoff = ((datetime.utcnow() + timedelta(hours=5, minutes=30)) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        "SELECT * FROM fitness_entries WHERE user_id = ? AND date >= ? ORDER BY date DESC",
        (user_id, cutoff)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Events / Schedule ────────────────────────────────────────────────

def get_events(user_id: str, date: str = None) -> list:
    """Get events, optionally for a specific date."""
    conn = get_db()
    if date:
        rows = conn.execute(
            "SELECT * FROM events WHERE user_id = ? AND start_time LIKE ? ORDER BY start_time",
            (user_id, f"{date}%")
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM events WHERE user_id = ? ORDER BY start_time", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_event(user_id: str, event: dict) -> dict:
    """Add a calendar event."""
    conn = get_db()
    event_id = str(uuid.uuid4())
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    conn.execute("""
        INSERT INTO events (id, user_id, title, description, start_time, end_time, location, event_type, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_id, user_id,
        event.get("title", ""),
        event.get("description", ""),
        event.get("start_time", ""),
        event.get("end_time", ""),
        event.get("location", ""),
        event.get("event_type", "meeting"),
        now,
    ))
    conn.commit()
    conn.close()
    return {"id": event_id, "status": "created"}


# ── Activity Log ─────────────────────────────────────────────────────

def get_activity_log(user_id: str, limit: int = 20) -> list:
    """Get recent activity log for a user."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM activity_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── JWT Helpers ──────────────────────────────────────────────────────

def create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = (datetime.utcnow() + timedelta(hours=5, minutes=30)) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify a JWT token and return the payload."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None


# ── Seed Data ────────────────────────────────────────────────────────

def _seed_user_data(cursor, user_id: str, now: str):
    """No pre-seeded data. All data comes from real user input."""
    pass


# ── Complaints ───────────────────────────────────────────────────────

def add_complaint(user_id: str, complaint: dict) -> dict:
    """Lodge a new complaint."""
    conn = get_db()
    complaint_id = str(uuid.uuid4())
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    conn.execute("""
        INSERT INTO complaints (id, user_id, product_name, order_id, category, description, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id, user_id,
        complaint.get("product_name", ""),
        complaint.get("order_id", ""),
        complaint.get("category", "general"),
        complaint.get("description", ""),
        "open",
        now,
    ))
    conn.commit()
    conn.close()
    return {"id": complaint_id, "status": "filed"}


def get_complaints(user_id: str = None) -> list:
    """Get complaints — all if admin, or for specific user."""
    conn = get_db()
    if user_id:
        rows = conn.execute("SELECT * FROM complaints WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM complaints ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_complaint(complaint_id: str, resolution: str, resolved_by: str = "admin") -> dict:
    """Resolve a complaint."""
    conn = get_db()
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    conn.execute("UPDATE complaints SET status = 'resolved', resolution = ?, resolved_by = ?, resolved_at = ? WHERE id = ?",
                 (resolution, resolved_by, now, complaint_id))
    conn.commit()
    conn.close()
    return {"status": "resolved"}


# ── Orders ───────────────────────────────────────────────────────────

def add_order(user_id: str, order: dict) -> dict:
    """Create a new order."""
    conn = get_db()
    order_id = str(uuid.uuid4())[:8].upper()
    now = (datetime.utcnow() + timedelta(hours=5, minutes=30)).isoformat()
    est_delivery = (datetime.utcnow() + timedelta(hours=5, minutes=30) + timedelta(days=3)).strftime("%Y-%m-%d")
    tracking_id = 'AMZ-' + str(uuid.uuid4())[:8].upper()
    conn.execute("""
        INSERT INTO orders (id, user_id, product_name, amazon_url, quantity, total_price, status, estimated_delivery, tracking_id, ordered_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        order_id, user_id,
        order.get("product_name", ""),
        order.get("amazon_url", ""),
        order.get("quantity", 1),
        order.get("total_price", 0),
        "processing",
        est_delivery,
        tracking_id,
        now,
    ))
    conn.commit()
    conn.close()
    return {"id": order_id, "tracking_id": tracking_id, "estimated_delivery": est_delivery, "status": "processing"}


def get_orders(user_id: str) -> list:
    """Get all orders for a user."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY ordered_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_shopping_item(item_id: str) -> dict:
    """Delete a shopping item."""
    conn = get_db()
    conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


# Initialize on import
init_db()
