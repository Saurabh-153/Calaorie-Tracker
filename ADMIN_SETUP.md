# Admin User Management — Setup & Usage

## What was implemented:

### 1. Database Changes
- Added `is_admin` column to `users` table (default: 0/false)
- Migration script (`migrate.py`) handles existing databases

### 2. Backend (app.py)
- Updated `User` class to track `is_admin` status
- Added `@admin_required` decorator to protect admin routes
- New admin routes:
  - `/admin/users` — View all users (admin only)
  - `/admin/users/make-admin/<user_id>` — Toggle admin status (admin only)  
  - `/admin/users/delete/<user_id>` — Delete a user (admin only)

### 3. Frontend
- Updated dropdown menu in `base.html` to show "Users" link (admins only)
- Created `admin_users.html` template with:
  - List of all users with email, join date, and status
  - Toggle button to make/remove admin (⭐ = admin, ☆ = regular user)
  - Delete button for each user (with confirmation)
  - Prevents self-deletion

### 4. Database Functions (database.py)
- `get_all_users()` — Get all users ordered by join date
- `set_user_admin(user_id, is_admin)` — Toggle admin status
- `delete_user(user_id)` — Delete a user

### 5. Utility Scripts
- `make_admin.py` — Make an email address admin: `python make_admin.py <email>`
- `migrate.py` — Add is_admin column to existing databases

---

## Setup Instructions:

### Step 1: Run Migration
```bash
python migrate.py
```
This adds the `is_admin` column to existing databases.

### Step 2: Make saurabhluv07@gmail an Admin
```bash
python make_admin.py saurabhluv07@gmail
```

### Step 3: Start the App
```bash
python app.py
```

---

## Usage:

### As an Admin:
1. Log in with the admin email (saurabhluv07@gmail)
2. Click the **gear icon** (⚙) in the top-right navigation
3. Click **"Users"** in the dropdown
4. You can now:
   - **See all users** with their join dates
   - **Make other users admins** by clicking ⭐
   - **Remove admin status** by clicking ☆
   - **Delete users** by clicking 🗑

### As a Regular User:
- The "Users" option doesn't appear in the dropdown
- Can only see their own email and logout option

---

## Key Features:

✅ **Admin-only access** — Users menu only visible to admins  
✅ **Toggle admin status** — Make/remove admins with one click  
✅ **Delete users** — Admins can remove any user from the system  
✅ **Self-protection** — Admins cannot delete themselves  
✅ **Persistent** — Admin status is stored in database  
✅ **Easy setup** — Single command to make user admin

---

## File Changes:
- `database.py` — Added user management functions & migration
- `app.py` — Added admin routes & User class update
- `templates/base.html` — Updated dropdown menu
- `templates/admin_users.html` — New user management page (created)
- `make_admin.py` — Utility script to make user admin (created)
- `migrate.py` — Database migration script (created)
- `static/style.css` — Dropdown styles (already added)
