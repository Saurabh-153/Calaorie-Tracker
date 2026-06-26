#!/usr/bin/env python3
"""
Migration script to add is_admin column to users table if it doesn't exist.
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = "calorie_tracker.db"

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        print("✓ Added is_admin column to users table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e) or "already exists" in str(e):
            print("✓ is_admin column already exists")
        else:
            print(f"✗ Error: {e}")
            sys.exit(1)
    finally:
        conn.close()
