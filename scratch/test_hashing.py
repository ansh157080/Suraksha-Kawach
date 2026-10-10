import auth_db
import sqlite3

# Register a new user
print("Registering new user 'testuser'...")
res = auth_db.register_user("testuser", "test@example.com", "secret123")
print(res)

# Verify existing "normal form" user
print("\nVerifying existing user 'ansh' (plain text 'ansh17')...")
user = auth_db.verify_user("ansh", "ansh17")
print(f"Success: {user is not None}")

# Verify new hashed user
print("\nVerifying new user 'testuser' (hashed 'secret123')...")
user = auth_db.verify_user("testuser", "secret123")
print(f"Success: {user is not None}")

# Check DB content
conn = sqlite3.connect("users.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM users WHERE user_name IN ('ansh', 'testuser')").fetchall()
for row in rows:
    print(f"\nUser: {row['user_name']}, Password in DB: {row['password']}")
conn.close()
