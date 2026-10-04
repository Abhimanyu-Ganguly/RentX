"""
Tests for Item Passport SHA-256 hash chains, tamper detection, and cross-item isolation.
"""

import json
from app.services.passport import (
    hash_bytes,
    compute_item_hash,
    append_event,
    verify_chain,
    GENESIS_PREV_HASH,
)


def _seed_test_user_and_item(conn, item_title="DeWalt 20V Drill", serial="DW-10023"):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, dorm, created_at) VALUES (?, ?, ?, ?)",
        ("Alice Chen", f"alice_{serial}@campus.edu", "West Hall", "2026-10-01T10:00:00Z"),
    )
    user_id = cur.lastrowid

    cur.execute(
        """
        INSERT INTO items (
            owner_id, title, category, description, value, price_per_day, deposit_amount,
            serial, photo_path, photo_hash, item_hash, condition_checklist, tags, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            item_title,
            "tools",
            "Great cordless drill",
            120.0,
            10.0,
            50.0,
            serial,
            "/static/img/sample.jpg",
            "dummy_photo_hash",
            "dummy_item_hash",
            json.dumps({"chuck": "good", "battery": "good"}),
            "drill,tools",
            "2026-10-01T10:00:00Z",
        ),
    )
    item_id = cur.lastrowid
    return user_id, item_id


def test_hash_computation():
    """Verify SHA-256 computation over raw bytes and composite item metadata."""
    sample_bytes = b"fake-camera-image-bytes"
    photo_hash = hash_bytes(sample_bytes)
    assert len(photo_hash) == 64
    assert photo_hash == hash_bytes(sample_bytes)  # Deterministic

    item_hash = compute_item_hash(photo_hash, "SN-998877", "Sony A7 IV")
    assert len(item_hash) == 64
    # Ensure changing serial changes hash
    diff_item_hash = compute_item_hash(photo_hash, "SN-998878", "Sony A7 IV")
    assert item_hash != diff_item_hash


def test_valid_passport_hash_chain(db_conn):
    """Verify that a sequence of valid events builds a mathematically sound chain."""
    user_id, item_id = _seed_test_user_and_item(db_conn)

    # 1. Genesis event: Registered
    ev1 = append_event(
        db_conn,
        item_id=item_id,
        event_type="registered",
        actor_id=user_id,
        details={"owner": "Alice Chen", "condition": {"chuck": "good"}},
        timestamp="2026-10-01T10:00:00Z",
    )
    assert ev1["seq"] == 1
    assert ev1["prev_hash"] == GENESIS_PREV_HASH

    # 2. Event 2: Rented
    ev2 = append_event(
        db_conn,
        item_id=item_id,
        event_type="rented",
        actor_id=user_id,
        details={"renter_id": 2, "days": 3, "condition_before": {"chuck": "good"}},
        timestamp="2026-10-02T12:00:00Z",
    )
    assert ev2["seq"] == 2
    assert ev2["prev_hash"] == ev1["event_hash"]

    # 3. Event 3: Returned
    ev3 = append_event(
        db_conn,
        item_id=item_id,
        event_type="returned",
        actor_id=user_id,
        details={"condition_after": {"chuck": "good"}, "rating": 5},
        timestamp="2026-10-05T14:00:00Z",
    )
    assert ev3["seq"] == 3
    assert ev3["prev_hash"] == ev2["event_hash"]

    # Verify the entire chain
    is_valid, broken_at, events = verify_chain(db_conn, item_id)
    assert is_valid is True
    assert broken_at is None
    assert len(events) == 3


def test_tamper_detection_at_exact_seq(db_conn):
    """
    Verify that tampering with an event's details in SQLite is caught immediately
    and pinpoints the exact sequence number where the tamper happened.
    """
    user_id, item_id = _seed_test_user_and_item(db_conn)

    # Build 4 events
    append_event(db_conn, item_id, "registered", user_id, {"msg": "genesis"}, "2026-10-01T10:00:00Z")
    append_event(db_conn, item_id, "rented", user_id, {"msg": "rental 1"}, "2026-10-02T10:00:00Z")
    append_event(db_conn, item_id, "returned", user_id, {"msg": "return 1"}, "2026-10-03T10:00:00Z")
    append_event(db_conn, item_id, "rented", user_id, {"msg": "rental 2"}, "2026-10-04T10:00:00Z")

    # Confirm initially valid
    is_valid, broken_at, _ = verify_chain(db_conn, item_id)
    assert is_valid is True

    # Tamper with Event #2's details directly in SQLite (simulate database breach or malicious edit)
    tampered_details = json.dumps({"msg": "MALICIOUSLY TAMPERED DETAILS", "hacked": True})
    db_conn.execute(
        "UPDATE passport_events SET details = ? WHERE item_id = ? AND seq = 2",
        (tampered_details, item_id),
    )

    # Verification must fail at sequence 2
    is_valid, broken_at, events = verify_chain(db_conn, item_id)
    assert is_valid is False
    assert broken_at == 2


def test_independent_per_item_chains(db_conn):
    """Verify that multiple items maintain completely independent hash chains without crosstalk."""
    user_id, item1_id = _seed_test_user_and_item(db_conn, "Tent 4-Person", "TNT-001")
    _, item2_id = _seed_test_user_and_item(db_conn, "Camp Stove", "STV-002")

    # Add events to Item 1
    append_event(db_conn, item1_id, "registered", user_id, {"item": 1}, "2026-10-01T10:00:00Z")
    append_event(db_conn, item1_id, "rented", user_id, {"item": 1}, "2026-10-02T10:00:00Z")

    # Add events to Item 2
    append_event(db_conn, item2_id, "registered", user_id, {"item": 2}, "2026-10-01T11:00:00Z")

    # Both chains should be valid and have lengths 2 and 1 respectively
    valid1, broken1, events1 = verify_chain(db_conn, item1_id)
    valid2, broken2, events2 = verify_chain(db_conn, item2_id)

    assert valid1 is True and len(events1) == 2
    assert valid2 is True and len(events2) == 1
    assert events1[0]["prev_hash"] == GENESIS_PREV_HASH
    assert events2[0]["prev_hash"] == GENESIS_PREV_HASH
    assert events1[0]["event_hash"] != events2[0]["event_hash"]
