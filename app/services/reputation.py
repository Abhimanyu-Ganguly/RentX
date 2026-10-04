"""
Reputation Computation Service.
Computes multi-dimensional reputation scores on-demand from rental transaction history.
No heavy ML or black-box algorithms: uses transparent, deterministic arithmetic.
"""

import sqlite3
from datetime import datetime
from typing import Any, Optional


def _parse_iso(timestamp_str: Optional[str]) -> Optional[datetime]:
    """
    Safely parses an ISO 8601 timestamp string into a Python datetime object.
    Handles UTC 'Z' suffixes and standard timezone offsets.
    """
    if not timestamp_str:
        return None
    try:
        clean_str = timestamp_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


def calculate_renter_reputation(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """
    Calculates performance and trust metrics when the user acts as a RENTER.
    - Return Punctuality: % of rentals returned on or before agreed time.
    - Item Care: Average condition score awarded by owners (out of 5.0 scaled to 100%).
    - Dispute Count: Number of rentals resulting in damage/missing disputes.
    - Successful Rentals: Cleanly completed rentals without disputes.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            booking_status,
            deposit_status,
            condition_rating,
            return_on_time,
            dispute_reason
        FROM rentals
        WHERE renter_id = ?
        """,
        (user_id,),
    )
    rentals = cursor.fetchall()

    if not rentals:
        return {
            "has_history": False,
            "return_punctuality_pct": None,
            "item_care_pct": None,
            "dispute_count": 0,
            "successful_rentals": 0,
            "total_completed": 0,
        }

    # Analyze completed rentals (returned or resolved)
    completed_rentals = [
        r for r in rentals
        if r["booking_status"] == "completed" or r["condition_rating"] is not None or r["deposit_status"] in ("released", "resolved")
    ]

    if not completed_rentals:
        return {
            "has_history": False,
            "return_punctuality_pct": None,
            "item_care_pct": None,
            "dispute_count": sum(1 for r in rentals if r["deposit_status"] in ("disputed", "resolved") and r["dispute_reason"]),
            "successful_rentals": 0,
            "total_completed": 0,
        }

    # 1. Return Punctuality %
    total_returns = len(completed_rentals)
    on_time_returns = sum(1 for r in completed_rentals if r["return_on_time"] == 1 or r["return_on_time"] is True)
    punctuality_pct = round((on_time_returns / total_returns) * 100.0, 1)

    # 2. Item Care % (Average owner rating / 5.0 * 100)
    ratings = [r["condition_rating"] for r in completed_rentals if r["condition_rating"] is not None]
    if ratings:
        avg_rating = sum(ratings) / len(ratings)
        item_care_pct = round((avg_rating / 5.0) * 100.0, 1)
    else:
        item_care_pct = None

    # 3. Disputes & Successful Rentals
    disputes = sum(1 for r in rentals if r["deposit_status"] in ("disputed", "resolved") and r["dispute_reason"])
    successful = sum(1 for r in completed_rentals if r["deposit_status"] == "released" and not r["dispute_reason"])

    return {
        "has_history": True,
        "return_punctuality_pct": punctuality_pct,
        "item_care_pct": item_care_pct,
        "dispute_count": disputes,
        "successful_rentals": successful,
        "total_completed": total_returns,
    }


def calculate_owner_reputation(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """
    Calculates performance and trust metrics when the user acts as an OWNER.
    - Reliability: % of accepted bookings that were successfully fulfilled and completed.
    - Avg Response Time: Mean elapsed time (hours) between request receipt and owner action.
    - Dispute Count: Number of bookings where owner had to initiate dispute arbitration.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            booking_status,
            deposit_status,
            dispute_reason,
            requested_at,
            responded_at
        FROM rentals
        WHERE owner_id = ?
        """,
        (user_id,),
    )
    bookings = cursor.fetchall()

    if not bookings:
        return {
            "has_history": False,
            "reliability_pct": None,
            "avg_response_hours": None,
            "dispute_count": 0,
            "total_bookings_received": 0,
            "total_accepted": 0,
            "total_completed": 0,
        }

    total_received = len(bookings)
    accepted_bookings = [b for b in bookings if b["booking_status"] in ("approved", "active", "completed")]
    completed_bookings = [b for b in bookings if b["booking_status"] == "completed"]

    total_accepted = len(accepted_bookings)
    total_completed = len(completed_bookings)

    # 1. Reliability %
    if total_accepted > 0:
        reliability_pct = round((total_completed / total_accepted) * 100.0, 1)
    else:
        reliability_pct = None

    # 2. Avg Response Hours
    response_durations_hours: list[float] = []
    for b in bookings:
        if b["responded_at"] and b["requested_at"]:
            t_req = _parse_iso(b["requested_at"])
            t_res = _parse_iso(b["responded_at"])
            if t_req and t_res:
                delta = t_res - t_req
                hours = max(0.0, delta.total_seconds() / 3600.0)
                response_durations_hours.append(hours)

    if response_durations_hours:
        avg_response_hours = round(sum(response_durations_hours) / len(response_durations_hours), 1)
    else:
        avg_response_hours = None

    # 3. Dispute Count
    dispute_count = sum(1 for b in bookings if b["deposit_status"] in ("disputed", "resolved") and b["dispute_reason"])

    has_history = total_received > 0

    # Fetch reviews
    cursor.execute(
        '''
        SELECT r.rating, r.comment, r.product_condition, r.price_fairness, r.created_at, u.name as reviewer_name
        FROM reviews r
        JOIN users u ON r.reviewer_id = u.id
        WHERE r.reviewed_user_id = ?
        ORDER BY r.created_at DESC
        ''',
        (user_id,)
    )
    reviews_list = [dict(r) for r in cursor.fetchall()]
    total_reviews = len(reviews_list)
    avg_service_rating = round(sum(r["rating"] for r in reviews_list) / total_reviews, 1) if total_reviews > 0 else 0.0

    return {
        "has_history": has_history,
        "reliability_pct": reliability_pct,
        "avg_response_hours": avg_response_hours,
        "dispute_count": dispute_count,
        "total_bookings_received": total_received,
        "total_accepted": total_accepted,
        "total_completed": total_completed,
        "average_service_rating": avg_service_rating,
        "total_reviews": total_reviews,
        "reviews": reviews_list
    }


def get_user_reputation(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    """
    Returns the comprehensive reputation profile for a user across both Renter and Owner roles.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
    user_row = cursor.fetchone()
    user_name = user_row["name"] if user_row else f"User #{user_id}"

    return {
        "user_id": user_id,
        "user_name": user_name,
        "renter": calculate_renter_reputation(conn, user_id),
        "owner": calculate_owner_reputation(conn, user_id),
    }
