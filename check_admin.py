import database as db

user = db.get_or_create_user('saurabhluv07@gmail')
print(f"Email: {user['email']}")
print(f"Is Admin: {user.get('is_admin', 'NOT FOUND')}")
