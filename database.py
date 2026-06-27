"""DB connection helpers and raw SQL queries using sqlite3."""

import os
import sqlite3
from contextlib import contextmanager
from typing import List, Optional

from models import FoodEntry, DailyGoal, AiResponseAuditLog, PromptVersion

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "calorie_tracker.db"))


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


@contextmanager
def get_db():
    """Yield a sqlite3 connection with row_factory set, auto-close on exit."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema initialisation — called once at app startup
# ---------------------------------------------------------------------------


def init_db():
    """Create tables if they don't already exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS food_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                date        TEXT    NOT NULL,
                name        TEXT    NOT NULL,
                calories    INTEGER NOT NULL,
                protein     REAL    NOT NULL DEFAULT 0,
                carbs       REAL    NOT NULL DEFAULT 0,
                fat         REAL    NOT NULL DEFAULT 0,
                timestamp   TEXT    NOT NULL
            )
        """)
        # Migrate existing DBs that lack user_id column
        try:
            conn.execute("ALTER TABLE food_entries ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
        except Exception:
            pass  # column already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_goals (
                user_id       INTEGER NOT NULL,
                date          TEXT    NOT NULL,
                calorie_goal  INTEGER NOT NULL,
                protein_goal  REAL    NOT NULL DEFAULT 0,
                carbs_goal    REAL    NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, date)
            )
        """)
        # Migrate existing DBs that lack user_id column
        try:
            conn.execute("ALTER TABLE daily_goals ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
        except Exception:
            pass  # column already exists
        # Migrate existing DBs where user_id was added via ALTER TABLE (no composite PK).
        # Detect by checking if a UNIQUE index on (user_id, date) exists; if not, rebuild.
        idx_exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='daily_goals' "
            "AND (sql LIKE '%user_id%date%' OR sql LIKE '%date%user_id%')"
        ).fetchone()[0]
        pk_is_composite = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='daily_goals' "
            "AND sql LIKE '%PRIMARY KEY (user_id, date)%'"
        ).fetchone()[0]
        if not idx_exists and not pk_is_composite:
            conn.execute("""
                CREATE TABLE daily_goals_new (
                    user_id       INTEGER NOT NULL,
                    date          TEXT    NOT NULL,
                    calorie_goal  INTEGER NOT NULL,
                    protein_goal  REAL    NOT NULL DEFAULT 0,
                    carbs_goal    REAL    NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO daily_goals_new (user_id, date, calorie_goal, protein_goal, carbs_goal)
                SELECT user_id, date, calorie_goal, protein_goal, carbs_goal FROM daily_goals
            """)
            conn.execute("DROP TABLE daily_goals")
            conn.execute("ALTER TABLE daily_goals_new RENAME TO daily_goals")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_response_audit_logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp        TEXT    NOT NULL,
                input_text       TEXT    NOT NULL,
                response_payload TEXT    NOT NULL,
                provider         TEXT    NOT NULL,
                status           TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prompt_versions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                content     TEXT    NOT NULL,
                created_at  TEXT    NOT NULL,
                is_active   INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT    NOT NULL UNIQUE,
                created_at TEXT    NOT NULL,
                is_admin   INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Migrate existing DBs that lack is_admin column
        try:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass  # column already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS otp_sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT    NOT NULL,
                code       TEXT    NOT NULL,
                attempts   INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT    NOT NULL,
                used       INTEGER NOT NULL DEFAULT 0
            )
        """)



# ---------------------------------------------------------------------------
# Food entry queries
# ---------------------------------------------------------------------------


def insert_entry(entry: FoodEntry, user_id: int) -> int:
    """Insert a food entry and return its new row id."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO food_entries
               (user_id, date, name, calories, protein, carbs, fat, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                entry.date,
                entry.name,
                entry.calories,
                entry.protein,
                entry.carbs,
                entry.fat,
                entry.timestamp,
            ),
        )
        return cur.lastrowid


def delete_entry(entry_id: int, user_id: int):
    """Delete a food entry by id (only if owned by user)."""
    with get_db() as conn:
        conn.execute("DELETE FROM food_entries WHERE id = ? AND user_id = ?", (entry_id, user_id))


def get_entries_for_date(date: str, user_id: int) -> List[FoodEntry]:
    """Return all food entries for a given date and user, ordered by timestamp."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM food_entries WHERE date = ? AND user_id = ? ORDER BY timestamp", (date, user_id)
        ).fetchall()
    return [FoodEntry(**dict(r)) for r in rows]


def get_entries_in_range(start_date: str, end_date: str, user_id: int) -> List[FoodEntry]:
    """Return all food entries between two dates inclusive for a user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM food_entries WHERE date BETWEEN ? AND ? AND user_id = ? ORDER BY date, timestamp",
            (start_date, end_date, user_id),
        ).fetchall()
    return [FoodEntry(**dict(r)) for r in rows]


def search_food_entries(query: str, user_id: int, limit: int = 20):
    """Search historic food entries by name for a user."""
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT name,
                   ROUND(AVG(calories)) AS calories,
                   ROUND(AVG(protein), 1) AS protein,
                   ROUND(AVG(carbs), 1) AS carbs,
                   ROUND(AVG(fat), 1) AS fat
            FROM food_entries
            WHERE user_id = ? AND name LIKE ?
            GROUP BY name
            ORDER BY MAX(timestamp) DESC
            LIMIT ?
            """,
            (user_id, f"%{query}%", limit),
        ).fetchall()
    return [
        {
            "name": row["name"],
            "calories": int(row["calories"] or 0),
            "protein": float(row["protein"] or 0.0),
            "carbs": float(row["carbs"] or 0.0),
            "fat": float(row["fat"] or 0.0),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Daily goal queries
# ---------------------------------------------------------------------------


def upsert_goal(goal: DailyGoal, user_id: int):
    """Insert or replace the goal for a date and user (upsert)."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO daily_goals (user_id, date, calorie_goal, protein_goal, carbs_goal)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, date) DO UPDATE SET
                 calorie_goal = excluded.calorie_goal,
                 protein_goal = excluded.protein_goal,
                 carbs_goal   = excluded.carbs_goal""",
            (user_id, goal.date, goal.calorie_goal, goal.protein_goal, goal.carbs_goal),
        )


def get_goal_for_date(date: str, user_id: int) -> Optional[DailyGoal]:
    """Return the DailyGoal for a date and user, or None if not set."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_goals WHERE date = ? AND user_id = ?", (date, user_id)
        ).fetchone()
    if row is None:
        return None
    return DailyGoal(**dict(row))


def get_goals_in_range(start_date: str, end_date: str, user_id: int) -> List[DailyGoal]:
    """Return all daily goal records within a date range for a user."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_goals WHERE date BETWEEN ? AND ? AND user_id = ? ORDER BY date",
            (start_date, end_date, user_id),
        ).fetchall()
    return [DailyGoal(**dict(r)) for r in rows]


def get_goal_for_date_or_default(date: str, user_id: int, default: int = 2000) -> DailyGoal:
    """Return the goal for a date and user, falling back to a default if not set."""
    goal = get_goal_for_date(date, user_id)
    if goal is None:
        return DailyGoal(user_id=user_id, date=date, calorie_goal=default, protein_goal=0.0, carbs_goal=0.0)
    return goal


def insert_ai_response_log(log: AiResponseAuditLog) -> int:
    """Insert an AI response audit log row and return its new id."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO ai_response_audit_logs
               (timestamp, input_text, response_payload, provider, status)
               VALUES (?, ?, ?, ?, ?)""",
            (
                log.timestamp,
                log.input_text,
                log.response_payload,
                log.provider,
                log.status,
            ),
        )
        return cur.lastrowid


def get_ai_response_logs(limit: int = 50) -> List[AiResponseAuditLog]:
    """Return the most recent AI response audit logs."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM ai_response_audit_logs
               ORDER BY timestamp DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [AiResponseAuditLog(**dict(r)) for r in rows]


def delete_ai_response_log(log_id: int):
    """Delete an AI response audit log by id."""
    with get_db() as conn:
        conn.execute("DELETE FROM ai_response_audit_logs WHERE id = ?", (log_id,))


def create_prompt_version(prompt: PromptVersion) -> int:
    """Create a new prompt version and return its id."""
    with get_db() as conn:
        if prompt.is_active:
            conn.execute("UPDATE prompt_versions SET is_active = 0")
        cur = conn.execute(
            """INSERT INTO prompt_versions (name, content, created_at, is_active)
               VALUES (?, ?, ?, ?)""",
            (prompt.name, prompt.content, prompt.created_at, int(prompt.is_active)),
        )
        return cur.lastrowid


def get_prompt_versions() -> List[PromptVersion]:
    """Return all prompt versions ordered by newest first."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM prompt_versions ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [PromptVersion(**dict(r)) for r in rows]


def get_active_prompt_version() -> Optional[PromptVersion]:
    """Return the currently active prompt version if present."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM prompt_versions WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return PromptVersion(**dict(row))


def set_active_prompt_version(version_id: int):
    """Activate a prompt version and deactivate the others."""
    with get_db() as conn:
        conn.execute("UPDATE prompt_versions SET is_active = 0")
        conn.execute("UPDATE prompt_versions SET is_active = 1 WHERE id = ?", (version_id,))


def delete_prompt_version(version_id: int):
    """Delete a prompt version by id."""
    with get_db() as conn:
        conn.execute("DELETE FROM prompt_versions WHERE id = ?", (version_id,))


def update_prompt_version(version_id: int, name: str, content: str):
    """Update the name or content of a prompt version."""
    with get_db() as conn:
        conn.execute(
            "UPDATE prompt_versions SET name = ?, content = ? WHERE id = ?",
            (name, content, version_id),
        )


# ---------------------------------------------------------------------------
# User queries
# ---------------------------------------------------------------------------

def get_or_create_user(email: str) -> dict:
    """Return the user row for email, creating it if it doesn't exist."""
    from datetime import datetime
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return dict(row)
        conn.execute(
            "INSERT INTO users (email, created_at) VALUES (?, ?)",
            (email, datetime.now().isoformat()),
        )
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row)


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_all_users() -> List[dict]:
    """Return all users ordered by created_at descending."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, email, created_at, is_admin FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def set_user_admin(user_id: int, is_admin: bool):
    """Set admin status for a user."""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?",
            (1 if is_admin else 0, user_id),
        )


def delete_user(user_id: int):
    """Delete a user by id."""
    with get_db() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# ---------------------------------------------------------------------------
# OTP session queries
# ---------------------------------------------------------------------------

def create_otp(email: str, code: str, expires_at: str) -> int:
    """Insert a new OTP record and return its id."""
    with get_db() as conn:
        # Invalidate previous unused OTPs for this email
        conn.execute("UPDATE otp_sessions SET used = 1 WHERE email = ? AND used = 0", (email,))
        cur = conn.execute(
            "INSERT INTO otp_sessions (email, code, expires_at) VALUES (?, ?, ?)",
            (email, code, expires_at),
        )
        return cur.lastrowid


def get_active_otp(email: str) -> dict | None:
    """Return the latest unused, unexpired OTP row for email."""
    from datetime import datetime
    now = datetime.now().isoformat()
    with get_db() as conn:
        row = conn.execute(
            """SELECT * FROM otp_sessions
               WHERE email = ? AND used = 0 AND expires_at > ?
               ORDER BY id DESC LIMIT 1""",
            (email, now),
        ).fetchone()
        return dict(row) if row else None


def increment_otp_attempts(otp_id: int) -> int:
    """Bump attempt counter; return new count."""
    with get_db() as conn:
        conn.execute("UPDATE otp_sessions SET attempts = attempts + 1 WHERE id = ?", (otp_id,))
        row = conn.execute("SELECT attempts FROM otp_sessions WHERE id = ?", (otp_id,)).fetchone()
        return row["attempts"]


def mark_otp_used(otp_id: int):
    with get_db() as conn:
        conn.execute("UPDATE otp_sessions SET used = 1 WHERE id = ?", (otp_id,))
