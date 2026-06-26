#!/usr/bin/env python3
"""
Migration script to add user_id columns to food_entries and daily_goals tables.
"""

import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_PATH = "calorie_tracker.db"

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    try:
        # Add user_id to food_entries
        try:
            conn.execute("ALTER TABLE food_entries ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            print("✓ Added user_id column to food_entries table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e) or "already exists" in str(e):
                print("✓ user_id column already exists in food_entries")
            else:
                raise

        # Add user_id to daily_goals and recreate primary key
        try:
            conn.execute("ALTER TABLE daily_goals ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
            print("✓ Added user_id column to daily_goals table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e) or "already exists" in str(e):
                print("✓ user_id column already exists in daily_goals")
            else:
                raise

        conn.commit()
        print("\n✓ Migration complete! All users now isolated by user_id.")
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        conn.close()
