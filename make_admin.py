#!/usr/bin/env python3
"""
Script to make a user admin.
Usage: python make_admin.py <email>
"""

import sys
import os

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python make_admin.py <email>")
        sys.exit(1)
    
    email = sys.argv[1].strip().lower()
    
    # Get or create the user
    user = db.get_or_create_user(email)
    
    # Make them admin
    db.set_user_admin(user["id"], True)
    
    print(f"✓ User {email} is now an admin!")
