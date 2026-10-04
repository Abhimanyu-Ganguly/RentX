"""
Tests for Reputation math verification with hand-calculated expected values and zero-division edge cases.
"""

from app.services.reputation import (
    calculate_renter_reputation,
    calculate_owner_reputation,
    get_user_reputation,
)


def _seed_users(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name, email, created_at) VALUES ('Renter Bob', 'bob@campus.edu', '2026-10-01T00:00:00Z')")
    renter_id = cur.lastrowid
    cur.execute("INSERT INTO users (name, email, created_at) VALUES ('Owner Alice', 'alice@campus.edu', '2026-10-01T00:00:00Z')")
    owner_id = cur.lastrowid
    return renter_id, owner_id


def test_empty_reputation_history(db_conn):
    """Verify that a newly created user with no rental history returns clean nulls and doesn't crash."""
    renter_id, owner_id = _seed_users(db_conn)

    rep = get_user_reputation(db_conn, renter_id)
    assert rep["renter"]["has_history"] is False
    assert rep["renter"]["return_punctuality_pct"] is None
    assert rep["renter"]["item_care_pct"] is None
    assert rep["renter"]["dispute_count"] == 0
    assert rep["renter"]["successful_rentals"] == 0

    assert rep["owner"]["has_history"] is False
    assert rep["owner"]["reliability_pct"] is None
    assert rep["owner"]["avg_response_hours"] is None
    assert rep["owner"]["dispute_count"] == 0


def test_hand_computed_renter_reputation(db_conn):
    """
    Verify hand-computed renter metrics:
    - Rental 1: on_time=1, rating=5, released, no dispute
    - Rental 2: on_time=1, rating=4, released, no dispute
    - Rental 3: on_time=0 (late), rating=3, disputed, dispute_reason='scratched'
    Hand calculation:
    - total completed = 3
    - punctuality = 2 / 3 = 66.7%
    - avg rating = (5 + 4 + 3) / 3 = 4.0 -> item care = (4.0 / 5.0) * 100 = 80.0%
    - dispute_count = 1
    - successful_rentals = 2
    """
    renter_id, owner_id = _seed_users(db_conn)

    # Insert test item
    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT INTO items (owner_id, title, category, value, price_per_day, deposit_amount, serial,
                           photo_path, photo_hash, item_hash, condition_checklist, created_at)
        VALUES (?, 'Test Item', 'tools', 100, 10, 50, 'SN123', 'p.jpg', 'ph', 'ih', '{}', '2026-10-01T00:00:00Z')
        """,
        (owner_id,),
    )
    item_id = cur.lastrowid

    # Rental 1
    cur.execute(
        """
        INSERT INTO rentals (item_id, renter_id, owner_id, days, total_price, deposit_amount,
                             booking_status, deposit_status, condition_rating, return_on_time, requested_at, completed_at)
        VALUES (?, ?, ?, 2, 20, 50, 'completed', 'released', 5, 1, '2026-10-01T10:00:00Z', '2026-10-03T10:00:00Z')
        """,
        (item_id, renter_id, owner_id),
    )

    # Rental 2
    cur.execute(
        """
        INSERT INTO rentals (item_id, renter_id, owner_id, days, total_price, deposit_amount,
                             booking_status, deposit_status, condition_rating, return_on_time, requested_at, completed_at)
        VALUES (?, ?, ?, 1, 10, 50, 'completed', 'released', 4, 1, '2026-10-04T10:00:00Z', '2026-10-05T10:00:00Z')
        """,
        (item_id, renter_id, owner_id),
    )

    # Rental 3 (Late & Disputed)
    cur.execute(
        """
        INSERT INTO rentals (item_id, renter_id, owner_id, days, total_price, deposit_amount,
                             booking_status, deposit_status, condition_rating, return_on_time,
                             dispute_reason, requested_at, completed_at)
        VALUES (?, ?, ?, 3, 30, 50, 'completed', 'disputed', 3, 0, 'scratched', '2026-10-06T10:00:00Z', '2026-10-09T10:00:00Z')
        """,
        (item_id, renter_id, owner_id),
    )

    renter_metrics = calculate_renter_reputation(db_conn, renter_id)
    assert renter_metrics["has_history"] is True
    assert renter_metrics["return_punctuality_pct"] == 66.7
    assert renter_metrics["item_care_pct"] == 80.0
    assert renter_metrics["dispute_count"] == 1
    assert renter_metrics["successful_rentals"] == 2
    assert renter_metrics["total_completed"] == 3


def test_hand_computed_owner_reputation(db_conn):
    """
    Verify hand-computed owner metrics:
    - Booking 1: response delay = 2.0 hrs (10:00 to 12:00), completed
    - Booking 2: response delay = 4.0 hrs (08:00 to 12:00), completed
    - Booking 3: response delay = 6.0 hrs (09:00 to 15:00), accepted (in progress)
    Hand calculation:
    - total received = 3
    - total accepted = 3
    - total completed = 2
    - reliability = (2 / 3) * 100 = 66.7%
    - avg response time = (2.0 + 4.0 + 6.0) / 3 = 4.0 hours
    - dispute count = 0
    """
    renter_id, owner_id = _seed_users(db_conn)

    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT INTO items (owner_id, title, category, value, price_per_day, deposit_amount, serial,
                           photo_path, photo_hash, item_hash, condition_checklist, created_at)
        VALUES (?, 'Projector', 'projector', 400, 25, 100, 'PJ1', 'p.jpg', 'ph', 'ih', '{}', '2026-10-01T00:00:00Z')
        """,
        (owner_id,),
    )
    item_id = cur.lastrowid

    # Booking 1
    cur.execute(
        """
        INSERT INTO rentals (item_id, renter_id, owner_id, days, total_price, deposit_amount,
                             booking_status, deposit_status, requested_at, responded_at, completed_at)
        VALUES (?, ?, ?, 1, 25, 100, 'completed', 'released', '2026-10-01T10:00:00Z', '2026-10-01T12:00:00Z', '2026-10-02T12:00:00Z')
        """,
        (item_id, renter_id, owner_id),
    )

    # Booking 2
    cur.execute(
        """
        INSERT INTO rentals (item_id, renter_id, owner_id, days, total_price, deposit_amount,
                             booking_status, deposit_status, requested_at, responded_at, completed_at)
        VALUES (?, ?, ?, 2, 50, 100, 'completed', 'released', '2026-10-02T08:00:00Z', '2026-10-02T12:00:00Z', '2026-10-04T12:00:00Z')
        """,
        (item_id, renter_id, owner_id),
    )

    # Booking 3
    cur.execute(
        """
        INSERT INTO rentals (item_id, renter_id, owner_id, days, total_price, deposit_amount,
                             booking_status, deposit_status, requested_at, responded_at)
        VALUES (?, ?, ?, 1, 25, 100, 'accepted', 'held', '2026-10-03T09:00:00Z', '2026-10-03T15:00:00Z')
        """,
        (item_id, renter_id, owner_id),
    )

    owner_metrics = calculate_owner_reputation(db_conn, owner_id)
    assert owner_metrics["has_history"] is True
    assert owner_metrics["total_bookings_received"] == 3
    assert owner_metrics["total_accepted"] == 3
    assert owner_metrics["total_completed"] == 2
    assert owner_metrics["reliability_pct"] == 66.7
    assert owner_metrics["avg_response_hours"] == 4.0
    assert owner_metrics["dispute_count"] == 0
