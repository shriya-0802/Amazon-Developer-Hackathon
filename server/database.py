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
    conn = sqlite3.connect(DB_PATH)
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

    conn.commit()
    conn.close()
    print("📦 Database initialized: lifesync.db")


# ── User Management ─────────────────────────────────────────────────

def create_user(email: str, name: str, password: str, role: str = "user") -> dict:
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
    now = datetime.utcnow().isoformat()

    cursor.execute("""
        INSERT INTO users (id, email, name, password_hash, role, created_at, avatar_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, email.lower(), name, password_hash, role, now,
        f"https://ui-avatars.com/api/?name={name.replace(' ', '+')}&background=FF9900&color=fff&bold=true"
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
    now = datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()

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
    now = datetime.utcnow().isoformat()
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
    now = datetime.utcnow().isoformat()
    conn.execute("UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?", (now, task_id))
    conn.commit()
    conn.close()
    return {"status": "completed"}


# ── Fitness ──────────────────────────────────────────────────────────

def log_fitness(user_id: str, entry: dict) -> dict:
    """Log a fitness entry."""
    conn = get_db()
    entry_id = str(uuid.uuid4())
    today = datetime.utcnow().strftime("%Y-%m-%d")
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
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
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
    now = datetime.utcnow().isoformat()
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
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
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
    """Seed demo data for a new user."""
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Sample tasks
    tasks = [
        ("Review PR #847", "Code review for backend changes", "high", "work", today),
        ("Prepare sprint demo slides", "Q4 sprint demo presentation", "high", "work",
         (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")),
        ("Book dentist appointment", "Regular checkup", "medium", "personal",
         (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d")),
        ("Buy birthday gift for Mom", "Her birthday is Oct 15", "medium", "personal", "2026-10-15"),
    ]
    for title, desc, pri, cat, due in tasks:
        cursor.execute("""
            INSERT INTO tasks (id, user_id, title, description, priority, category, due_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """, (str(uuid.uuid4()), user_id, title, desc, pri, cat, due, now))

    # Sample events
    events = [
        ("Team Standup", "Daily sync", f"{today}T09:30:00", f"{today}T09:45:00", "Zoom", "meeting"),
        ("Sprint Planning", "Q4 sprint", f"{today}T11:00:00", f"{today}T12:00:00", "Conference Room A", "meeting"),
        ("Lunch Break", "", f"{today}T12:30:00", f"{today}T13:30:00", "", "personal"),
        ("1:1 with Manager", "Weekly check-in", f"{today}T15:00:00", f"{today}T15:30:00", "Zoom", "meeting"),
    ]
    for title, desc, start, end, loc, etype in events:
        cursor.execute("""
            INSERT INTO events (id, user_id, title, description, start_time, end_time, location, event_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), user_id, title, desc, start, end, loc, etype, now))

    # Sample shopping items
    items = [
        ("Tide Pods 42ct", "household", 1, 15.99, "B07QS7GYPF", 1, 30),
        ("Oat Milk (Oatly)", "grocery", 2, 5.49, "B07NQDSM45", 1, 14),
        ("Wireless Earbuds", "electronics", 1, 29.99, "B09JQ7J5Q5", 0, None),
        ("Protein Bars (12pk)", "grocery", 1, 24.99, "B07K3HLBZ1", 1, 21),
    ]
    for name, cat, qty, price, asin, auto, freq in items:
        cursor.execute("""
            INSERT INTO shopping_items (id, user_id, product_name, category, quantity, estimated_price,
                amazon_asin, amazon_url, is_auto_reorder, reorder_frequency_days, added_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), user_id, name, cat, qty, price, asin,
            f"https://www.amazon.com/dp/{asin}", auto, freq, now,
        ))

    # Sample fitness entry
    cursor.execute("""
        INSERT INTO fitness_entries (id, user_id, date, steps, calories_burned, active_minutes, water_glasses, sleep_hours, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), user_id, today, 8901, 420, 45, 6, 7.5, "Good day overall"))


# Initialize on import
init_db()
