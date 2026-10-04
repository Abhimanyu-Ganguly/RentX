"""
Database connection and transaction management using Python's built-in sqlite3.
Implements a clean per-request transaction lifecycle (BEGIN IMMEDIATE -> Commit on success -> Rollback on error).
"""

import sqlite3
from typing import Generator
from app.config import DATABASE_PATH


def get_db_connection(db_path: str = DATABASE_PATH) -> sqlite3.Connection:
    """
    Creates a new SQLite connection configured for reliability and row dict access.
    Foreign key constraints are strictly enforced.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # Enable accessing columns by name (row['title'])
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON;")
    # Enable WAL mode for better concurrency during reads/writes
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(db_path: str = DATABASE_PATH) -> None:
    """
    Initializes database tables if they do not already exist.
    """
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT DEFAULT '',
                    phone TEXT DEFAULT '',
                    dorm TEXT DEFAULT '',
                    avatar_url TEXT DEFAULT '',
                    auth_provider TEXT DEFAULT 'campus',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL REFERENCES users(id),
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    value REAL NOT NULL,
                    price_per_day REAL NOT NULL,
                    deposit_amount REAL NOT NULL,
                    serial TEXT NOT NULL,
                    photo_path TEXT NOT NULL,
                    photo_hash TEXT NOT NULL,
                    item_hash TEXT NOT NULL,
                    condition_checklist TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    mode TEXT NOT NULL DEFAULT 'commercial',
                    available INTEGER NOT NULL DEFAULT 1,
                    is_listed INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS passport_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL REFERENCES items(id),
                    seq INTEGER NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor_id INTEGER NOT NULL REFERENCES users(id),
                    details TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    UNIQUE(item_id, seq)
                );

                CREATE TABLE IF NOT EXISTS rentals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL REFERENCES items(id),
                    renter_id INTEGER NOT NULL REFERENCES users(id),
                    owner_id INTEGER NOT NULL REFERENCES users(id),
                    start_date TEXT,
                    end_date TEXT,
                    days INTEGER NOT NULL,
                    total_price REAL NOT NULL,
                    deposit_amount REAL NOT NULL,
                    booking_status TEXT NOT NULL DEFAULT 'pending',
                    deposit_status TEXT NOT NULL DEFAULT 'pending',
                    condition_rating INTEGER,
                    return_on_time INTEGER DEFAULT 1,
                    dispute_reason TEXT DEFAULT '',
                    dispute_resolution TEXT DEFAULT '',
                    requested_at TEXT NOT NULL,
                    responded_at TEXT,
                    returned_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_id INTEGER NOT NULL REFERENCES rentals(id),
                    reviewer_id INTEGER NOT NULL REFERENCES users(id),
                    reviewed_user_id INTEGER NOT NULL REFERENCES users(id),
                    item_id INTEGER NOT NULL REFERENCES items(id),
                    rating INTEGER NOT NULL,
                    comment TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_id INTEGER NOT NULL REFERENCES rentals(id),
                    item_id INTEGER NOT NULL REFERENCES items(id),
                    sender_id INTEGER NOT NULL REFERENCES users(id),
                    recipient_id INTEGER NOT NULL REFERENCES users(id),
                    message_text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS item_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rental_id INTEGER NOT NULL REFERENCES rentals(id),
                    reviewer_id INTEGER NOT NULL REFERENCES users(id),
                    item_id INTEGER NOT NULL REFERENCES items(id),
                    rating INTEGER NOT NULL,
                    product_condition TEXT DEFAULT '',
                    comment TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipient_id INTEGER NOT NULL REFERENCES users(id),
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    rental_id INTEGER REFERENCES rentals(id),
                    item_id INTEGER REFERENCES items(id),
                    created_at TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS password_resets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    token_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
                CREATE INDEX IF NOT EXISTS idx_items_available ON items(available);
                CREATE INDEX IF NOT EXISTS idx_passport_item ON passport_events(item_id);
                CREATE INDEX IF NOT EXISTS idx_rentals_item ON rentals(item_id);
                CREATE INDEX IF NOT EXISTS idx_rentals_renter ON rentals(renter_id);
                CREATE INDEX IF NOT EXISTS idx_rentals_owner ON rentals(owner_id);
                CREATE INDEX IF NOT EXISTS idx_reviews_reviewed_user ON reviews(reviewed_user_id);
                CREATE INDEX IF NOT EXISTS idx_reviews_rental ON reviews(rental_id);
                """
            )
            # Safe migration checks for existing tables
            try:
                conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT '';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE users ADD COLUMN auth_provider TEXT DEFAULT 'campus';")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE users ADD COLUMN manual_rating REAL;")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE items ADD COLUMN is_listed INTEGER NOT NULL DEFAULT 1;")
            except Exception:
                pass
    finally:
        conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    FastAPI dependency that provides a transaction per request.
    Acquires an immediate lock at start so concurrent writes never interleave incorrectly,
    commits automatically if no exception occurs, and rolls back cleanly on any failure.
    """
    conn = get_db_connection()
    # BEGIN IMMEDIATE reserves a write lock immediately to prevent concurrency deadlocks
    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
