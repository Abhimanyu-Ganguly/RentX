"""
Pytest configuration and test database fixtures.
Provides an isolated, in-memory SQLite database per test function.
"""

import sqlite3
import pytest

@pytest.fixture
def db_conn():
    """
    Creates an isolated in-memory SQLite database initialized with all tables.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # Run the table schema creation on this in-memory instance
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
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
            price_fairness TEXT DEFAULT '',
                    product_condition TEXT DEFAULT '',
                    comment TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );
"""
    )
    yield conn
    conn.close()
