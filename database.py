"""DB connection helpers and raw SQL queries using sqlite3."""

import sqlite3
from contextlib import contextmanager
from typing import List, Optional

from models import FoodEntry, DailyGoal, AiResponseAuditLog, PromptVersion

DB_PATH = "calorie_tracker.db"


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
                date        TEXT    NOT NULL,
                name        TEXT    NOT NULL,
                calories    INTEGER NOT NULL,
                protein     REAL    NOT NULL DEFAULT 0,
                carbs       REAL    NOT NULL DEFAULT 0,
                fat         REAL    NOT NULL DEFAULT 0,
                timestamp   TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_goals (
                date          TEXT PRIMARY KEY,
                calorie_goal  INTEGER NOT NULL
            )
        """)
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



# ---------------------------------------------------------------------------
# Food entry queries
# ---------------------------------------------------------------------------


def insert_entry(entry: FoodEntry) -> int:
    """Insert a food entry and return its new row id."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO food_entries
               (date, name, calories, protein, carbs, fat, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
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


def delete_entry(entry_id: int):
    """Delete a food entry by id."""
    with get_db() as conn:
        conn.execute("DELETE FROM food_entries WHERE id = ?", (entry_id,))


def get_entries_for_date(date: str) -> List[FoodEntry]:
    """Return all food entries for a given date, ordered by timestamp."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM food_entries WHERE date = ? ORDER BY timestamp", (date,)
        ).fetchall()
    return [FoodEntry(**dict(r)) for r in rows]


def get_entries_in_range(start_date: str, end_date: str) -> List[FoodEntry]:
    """Return all food entries between two dates inclusive."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM food_entries WHERE date BETWEEN ? AND ? ORDER BY date, timestamp",
            (start_date, end_date),
        ).fetchall()
    return [FoodEntry(**dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# Daily goal queries
# ---------------------------------------------------------------------------


def upsert_goal(goal: DailyGoal):
    """Insert or replace the calorie goal for a date (upsert)."""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO daily_goals (date, calorie_goal)
               VALUES (?, ?)
               ON CONFLICT(date) DO UPDATE SET calorie_goal = excluded.calorie_goal""",
            (goal.date, goal.calorie_goal),
        )


def get_goal_for_date(date: str) -> Optional[DailyGoal]:
    """Return the DailyGoal for a date, or None if not set."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM daily_goals WHERE date = ?", (date,)
        ).fetchone()
    if row is None:
        return None
    return DailyGoal(**dict(row))


def get_goals_in_range(start_date: str, end_date: str) -> List[DailyGoal]:
    """Return all daily goal records within a date range."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_goals WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date, end_date),
        ).fetchall()
    return [DailyGoal(**dict(r)) for r in rows]


def get_goal_for_date_or_default(date: str, default: int = 2000) -> DailyGoal:
    """Return the goal for a date, falling back to a default if not set."""
    goal = get_goal_for_date(date)
    if goal is None:
        return DailyGoal(date=date, calorie_goal=default)
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
