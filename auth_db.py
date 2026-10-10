"""
auth_db.py — SQLite authentication database layer for Suraksha Kawach.
Handles user registration, login verification, and Google OAuth user management.
"""

import sqlite3
import hashlib
import secrets
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")


def _get_conn():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str, salt: str = None) -> str:
    """Hash a password with a salt using SHA-256."""
    if not salt:
        salt = secrets.token_hex(8)
    hash_obj = hashlib.sha256((salt + password).encode())
    return f"{salt}:{hash_obj.hexdigest()}"


def init_db():
    """Create the users table and migrate existing plain text passwords if necessary."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name   TEXT NOT NULL UNIQUE,
            email       TEXT NOT NULL UNIQUE,
            password    TEXT,
            google_id   TEXT UNIQUE,
            auth_method TEXT NOT NULL DEFAULT 'local',
            created_at  TEXT NOT NULL
        )
    """)
    conn.commit()
    
    # Migrate any plain text passwords to hashes
    migrate_plain_passwords(conn)
    
    conn.close()


def migrate_plain_passwords(conn):
    """Find users with plain text passwords and hash them."""
    rows = conn.execute("SELECT id, password FROM users WHERE auth_method = 'local'").fetchall()
    for row in rows:
        stored_pwd = row["password"]
        if stored_pwd and ":" not in stored_pwd:
            # This is a plain text password, hash it
            new_hash = _hash_password(stored_pwd)
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_hash, row["id"]))
    conn.commit()


def register_user(user_name: str, email: str, password: str) -> dict:
    """
    Register a new local user.
    Returns {"success": True, "message": "..."} or {"success": False, "message": "..."}.
    """
    conn = _get_conn()
    try:
        # Check if user_name already exists
        existing = conn.execute(
            "SELECT id FROM users WHERE user_name = ?", (user_name.lower().strip(),)
        ).fetchone()
        if existing:
            return {"success": False, "message": "User Name already exists. Choose a different one."}

        # Check if email already exists
        existing_email = conn.execute(
            "SELECT id FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        if existing_email:
            return {"success": False, "message": "Email already registered. Try logging in."}

        hashed_password = _hash_password(password)

        conn.execute(
            """INSERT INTO users (user_name, email, password, auth_method, created_at)
               VALUES (?, ?, ?, 'local', ?)""",
            (user_name.strip(), email.lower().strip(), hashed_password, datetime.now().isoformat())
        )
        conn.commit()
        return {"success": True, "message": "Account created successfully!"}

    except sqlite3.IntegrityError as e:
        return {"success": False, "message": f"Registration failed: {str(e)}"}
    finally:
        conn.close()


def verify_user(identifier: str, password: str) -> dict | None:
    """
    Verify local user credentials using either User Name or Email.
    Returns user dict on success, None on failure.
    """
    conn = _get_conn()
    # Check against both user_name and email
    row = conn.execute(
        "SELECT * FROM users WHERE (user_name = ? OR email = ?) AND auth_method = 'local'",
        (identifier.lower().strip(), identifier.lower().strip())
    ).fetchone()
    conn.close()

    if not row:
        return None

    stored_password = row["password"]
    is_valid = False

    if stored_password and ":" in stored_password:
        # Hashed format (salt:hash)
        try:
            salt, _ = stored_password.split(":", 1)
            if _hash_password(password, salt) == stored_password:
                is_valid = True
        except ValueError:
            # Fallback if the colon was part of a plain text password (unlikely but safe)
            if password == stored_password:
                is_valid = True
    else:
        # "Normal form" (plain text) compatibility
        if password == stored_password:
            is_valid = True

    if is_valid:
        return {
            "id": row["id"],
            "user_name": row["user_name"],
            "email": row["email"],
            "auth_method": row["auth_method"],
        }
    return None


def get_or_create_demo_user(demo_id: str, user_name: str, email: str) -> dict:
    """
    Find an existing Demo user or create a new one.
    Returns user dict.
    """
    conn = _get_conn()

    # Check if this Demo ID already exists
    row = conn.execute(
        "SELECT * FROM users WHERE google_id = ?", (demo_id,)
    ).fetchone()

    if row:
        # If user_name has changed, update it
        if row["user_name"] != user_name:
            conn.execute(
                "UPDATE users SET user_name = ? WHERE google_id = ?",
                (user_name, demo_id)
            )
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE google_id = ?", (demo_id,)).fetchone()
            
        conn.close()
        return {
            "id": row["id"],
            "user_name": row["user_name"],
            "email": row["email"],
            "auth_method": row["auth_method"],
        }

    # Ensure unique user_name for Demo user if it conflicts
    base_name = user_name.strip()
    final_name = base_name
    counter = 1
    while conn.execute("SELECT id FROM users WHERE user_name = ?", (final_name,)).fetchone():
        final_name = f"{base_name} {counter}"
        counter += 1

    conn.execute(
        """INSERT INTO users (user_name, email, google_id, auth_method, created_at)
           VALUES (?, ?, ?, 'demo', ?)""",
        (final_name, email.lower().strip(), demo_id, datetime.now().isoformat())
    )
    conn.commit()

    row = conn.execute("SELECT * FROM users WHERE google_id = ?", (demo_id,)).fetchone()
    conn.close()

    return {
        "id": row["id"],
        "user_name": row["user_name"],
        "email": row["email"],
        "auth_method": row["auth_method"],
    }


def get_all_users_count() -> int:
    """Return total number of registered users."""
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def update_password(identifier: str, new_password: str) -> bool:
    """Update password for a local user identified by user_name or email."""
    conn = _get_conn()
    try:
        hashed_password = _hash_password(new_password)
        res = conn.execute(
            "UPDATE users SET password = ? WHERE (user_name = ? OR email = ?) AND auth_method = 'local'",
            (hashed_password, identifier.lower().strip(), identifier.lower().strip())
        )
        conn.commit()
        return res.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


def user_exists(identifier: str) -> bool:
    """Check if a local user exists with the given user_name or email."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id FROM users WHERE (user_name = ? OR email = ?) AND auth_method = 'local'",
        (identifier.lower().strip(), identifier.lower().strip())
    ).fetchone()
    conn.close()
    return row is not None


# Initialize the database on import
init_db()
