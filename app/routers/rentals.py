"""
Rentals and escrow lifecycle HTTP router.
Coordinates booking requests, approvals, returns, condition grading, disputes, and passport event logging.
"""

import json
import sqlite3
from datetime import datetime, timezone, date, date
from dateutil.parser import parse as parse_date
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from app.database import get_db
from app.schemas import (
    ConfirmReturnRequest,
    DisputeRequest,
    RentalCreate,
    RentalResponse,
    ResolveDisputeRequest,
    ReturnRequest,
)
from app.services.deposit import (
    InvalidDepositTransitionError,
    transition_on_accept,
    transition_on_confirm_return,
    transition_on_dispute,
    transition_on_resolve,
)
from app.services.passport import append_event


router = APIRouter(prefix="/api/rentals", tags=["Rentals"])


def _row_to_rental_dict(row: sqlite3.Row) -> dict:
    """Converts a rental row into a dictionary formatted for RentalResponse."""
    d = dict(row)
    d["return_on_time"] = bool(d.get("return_on_time", 1))
    return d



from pydantic import BaseModel
class AvailabilityCheck(BaseModel):
    item_id: int
    start_date: str
    end_date: str

@router.post("/check-availability")
def check_availability(payload: AvailabilityCheck, db: sqlite3.Connection = Depends(get_db)):
    try:
        start_d = datetime.strptime(payload.start_date, "%Y-%m-%d").date()
        end_d = datetime.strptime(payload.end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format.")

    if start_d < datetime.now(timezone.utc).date():
        return {"available": False, "message": "Start date cannot be in the past."}
        
    if end_d < start_d:
        return {"available": False, "message": "End date cannot be before start date."}

    cursor = db.cursor()
    cursor.execute("SELECT available FROM items WHERE id = ?", (payload.item_id,))
    item = cursor.fetchone()
    if not item or not item["available"]:
        return {"available": False, "message": "Item does not exist or is marked unavailable globally."}
    if "is_listed" in item.keys() and not item["is_listed"]:
        return {"available": False, "message": "Item is currently unlisted and unavailable for new rentals."}

    cursor.execute('''
        SELECT id FROM rentals 
        WHERE item_id = ? 
          AND booking_status IN ('approved', 'active')
          AND start_date <= ? 
          AND end_date >= ?
    ''', (payload.item_id, payload.end_date, payload.start_date))
    
    if cursor.fetchone():
        return {"available": False, "message": "Item is currently unavailable or already rented out for the selected dates."}
        
    calc_days = (end_d - start_d).days + 1
    return {"available": True, "message": "Available for these dates.", "days": calc_days}

@router.get("", response_model=list[RentalResponse])
def list_rentals(
    as_renter: Optional[bool] = Query(None, description="Filter for rentals where current user is renter"),
    as_owner: Optional[bool] = Query(None, description="Filter for bookings where current user is owner"),
    booking_status: Optional[str] = Query(None, description="Filter by booking status"),
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Lists rental transactions with joined item and user information.
    Supports filtering by role (as_renter vs as_owner) for UI tabs.
    """
    user_id = x_user_id if x_user_id is not None else 1

    query = """
        SELECT
            r.*,
            i.title as item_title,
            i.category as item_category,
            renter.name as renter_name,
            owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE 1=1
    """
    params: list = []

    if as_renter:
        query += " AND r.renter_id = ?"
        params.append(user_id)
    elif as_owner:
        query += " AND r.owner_id = ?"
        params.append(user_id)
    else:
        # Default: show any rental involving this user if header present
        if x_user_id is not None:
            query += " AND (r.renter_id = ? OR r.owner_id = ?)"
            params.extend([user_id, user_id])

    if booking_status:
        query += " AND r.booking_status = ?"
        params.append(booking_status)

    query += " ORDER BY r.id DESC"

    cursor = db.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [_row_to_rental_dict(r) for r in rows]


@router.post("", response_model=RentalResponse, status_code=status.HTTP_201_CREATED)
def create_rental_request(
    payload: RentalCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Creates a new rental booking request for an available item.
    Validations:
      - Item exists and is currently marked available
      - Renter cannot borrow their own equipment
      - Duration between 1 and 30 days
    """
    renter_id = x_user_id if x_user_id is not None else 1

    cursor = db.cursor()
    cursor.execute("SELECT * FROM items WHERE id = ?", (payload.item_id,))
    item = cursor.fetchone()
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {payload.item_id} not found.",
        )

    if not item["available"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item is currently unavailable or already rented out.",
        )
    if "is_listed" in item.keys() and not item["is_listed"]:
        raise HTTPException(
            status_code=400,
            detail="Item is currently unlisted and unavailable for new rentals.",
        )

    if item["owner_id"] == renter_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot rent your own listed equipment.",
        )

    # Check that renter exists
    cursor.execute("SELECT id FROM users WHERE id = ?", (renter_id,))
    if not cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Renter user with ID {renter_id} not found.",
        )

# Date Validation
    try:
        start_d = datetime.strptime(payload.start_date, "%Y-%m-%d").date()
        end_d = datetime.strptime(payload.end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

    if start_d < datetime.now(timezone.utc).date():
        raise HTTPException(status_code=422, detail="Start date cannot be in the past.")
        
    if end_d < start_d:
        raise HTTPException(status_code=422, detail="End date cannot be before start date.")

    # Inclusive calculation (e.g., 10th to 10th is 1 day, 10th to 11th is 2 days)
    calc_days = (end_d - start_d).days + 1

    # Overlap Check
    cursor.execute('''
        SELECT id FROM rentals 
        WHERE item_id = ? 
          AND booking_status IN ('approved', 'active')
          AND start_date <= ? 
          AND end_date >= ?
    ''', (payload.item_id, payload.end_date, payload.start_date))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="Item is currently unavailable or already rented out for the selected dates.")

    total_price = round(item["price_per_day"] * calc_days, 2)
    deposit_amount = item["deposit_amount"]
    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        """
        INSERT INTO rentals (
            item_id, renter_id, owner_id, start_date, end_date, days, total_price, deposit_amount,
            booking_status, deposit_status, return_on_time, requested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'pending', 1, ?)
        """,
        (item["id"], renter_id, item["owner_id"], payload.start_date, payload.end_date, calc_days, total_price, deposit_amount, now_iso),
    )
    rental_id = cursor.lastrowid

    # Retrieve created record with joined metadata
    cursor.execute(
        """
        SELECT r.*, i.title as item_title, i.category as item_category,
               renter.name as renter_name, owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    res = _row_to_rental_dict(cursor.fetchone())
    if res['booking_status'] == 'pending':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'new_request', 'New rental request', f"New rental request for your {res['item_title']} from {res['renter_name']}.", res['id'], res['item_id'], res['requested_at'])
        )
    elif res['booking_status'] == 'approved':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_accepted', 'Rental request accepted', f"Your rental request for {res['item_title']} was accepted by {res['owner_name']}.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'rejected':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_rejected', 'Rental request rejected', f"Your rental request for {res['item_title']} was rejected.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'returned':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'return_request', 'Return requested', f"{res['renter_name']} requested to return {res['item_title']}.", res['id'], res['item_id'], res['returned_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'completed':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
    return res


@router.post("/{rental_id}/accept", response_model=RentalResponse)
def accept_rental_request(
    rental_id: int,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Owner accepts booking request.
    Transitions deposit state: pending -> held (escrow locked).
    Marks item available = 0.
    Appends 'rented' block to item's passport chain.
    """
    owner_id = x_user_id if x_user_id is not None else 1

    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental not found.")

    if rental["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the item owner can accept this booking.")

    if rental["booking_status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot accept booking in '{rental['booking_status']}' status.",
        )

    # State Machine Transition: pending -> held
    try:
        new_deposit_status = transition_on_accept(rental["deposit_status"])
    except InvalidDepositTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    now_iso = datetime.now(timezone.utc).isoformat()

    
    # AVAILABILITY OVERLAP CHECK
    cursor.execute('''
        SELECT id FROM rentals 
        WHERE item_id = ? 
          AND booking_status IN ('approved', 'active')
          AND start_date <= ? 
          AND end_date >= ?
          AND id != ?
    ''', (rental["item_id"], rental["end_date"], rental["start_date"], rental_id))
    
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot accept this request because another approved rental overlaps with these dates."
        )

    # Update rental & item availability
    cursor.execute(
        """
        UPDATE rentals
        SET booking_status = 'approved',
            deposit_status = ?,
            responded_at = ?
        WHERE id = ?
        """,
        (new_deposit_status, now_iso, rental_id),
    )
    cursor.execute("UPDATE items SET available = 0 WHERE id = ?", (rental["item_id"],))

    # Fetch item checklist to record condition_before in passport event
    cursor.execute("SELECT * FROM items WHERE id = ?", (rental["item_id"],))
    item = cursor.fetchone()
    try:
        condition_before = json.loads(item["condition_checklist"]) if isinstance(item["condition_checklist"], str) else item["condition_checklist"]
    except Exception:
        condition_before = {}

    # Append 'rented' event to Item Passport hash chain
    append_event(
        conn=db,
        item_id=rental["item_id"],
        event_type="rented",
        actor_id=owner_id,
        details={
            "action": "Rental approved and handed over",
            "rental_id": rental_id,
            "renter_id": rental["renter_id"],
            "days": rental["days"],
            "deposit_status": "held",
            "condition_before": condition_before,
        },
        timestamp=now_iso,
    )

    cursor.execute(
        """
        SELECT r.*, i.title as item_title, i.category as item_category,
               renter.name as renter_name, owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    res = _row_to_rental_dict(cursor.fetchone())
    if res['booking_status'] == 'pending':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'new_request', 'New rental request', f"New rental request for your {res['item_title']} from {res['renter_name']}.", res['id'], res['item_id'], res['requested_at'])
        )
    elif res['booking_status'] == 'approved':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_accepted', 'Rental request accepted', f"Your rental request for {res['item_title']} was accepted by {res['owner_name']}.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'rejected':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_rejected', 'Rental request rejected', f"Your rental request for {res['item_title']} was rejected.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'returned':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'return_request', 'Return requested', f"{res['renter_name']} requested to return {res['item_title']}.", res['id'], res['item_id'], res['returned_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'completed':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
    return res


@router.post("/{rental_id}/reject", response_model=RentalResponse)
def reject_rental_request(
    rental_id: int,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Owner rejects booking request.
    """
    owner_id = x_user_id if x_user_id is not None else 1

    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental not found.")

    if rental["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the item owner can reject this booking.")

    if rental["booking_status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reject booking in '{rental['booking_status']}' status.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE rentals
        SET booking_status = 'rejected',
            responded_at = ?
        WHERE id = ?
        """,
        (now_iso, rental_id),
    )

    append_event(
        conn=db,
        item_id=rental["item_id"],
        event_type="booking_rejected",
        actor_id=owner_id,
        details={
            "action": "Owner declined the booking request",
            "rental_id": rental_id,
        },
        timestamp=now_iso,
    )

    cursor.execute(
        """
        SELECT r.*, i.title as item_title, i.category as item_category,
               renter.name as renter_name, owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    res = _row_to_rental_dict(cursor.fetchone())
    if res['booking_status'] == 'pending':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'new_request', 'New rental request', f"New rental request for your {res['item_title']} from {res['renter_name']}.", res['id'], res['item_id'], res['requested_at'])
        )
    elif res['booking_status'] == 'approved':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_accepted', 'Rental request accepted', f"Your rental request for {res['item_title']} was accepted by {res['owner_name']}.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'rejected':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_rejected', 'Rental request rejected', f"Your rental request for {res['item_title']} was rejected.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'returned':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'return_request', 'Return requested', f"{res['renter_name']} requested to return {res['item_title']}.", res['id'], res['item_id'], res['returned_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'completed':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
    return res


@router.post("/{rental_id}/return", response_model=RentalResponse)
def return_rental_item(
    rental_id: int,
    payload: ReturnRequest,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Renter initiates return of the equipment.
    Records return timestamp, whether it was returned on time, and renter's condition self-assessment.
    """
    renter_id = x_user_id if x_user_id is not None else 1

    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental not found.")

    if rental["renter_id"] != renter_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the renter can initiate item return.")

    if rental["booking_status"] != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot return booking in '{rental['booking_status']}' status.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE rentals
        SET booking_status = 'returned',
            returned_at = ?,
            return_on_time = ?
        WHERE id = ?
        """,
        (now_iso, 1 if payload.return_on_time else 0, rental_id),
    )

    append_event(
        conn=db,
        item_id=rental["item_id"],
        event_type="return_initiated",
        actor_id=renter_id,
        details={
            "action": "Renter initiated equipment return",
            "rental_id": rental_id,
            "return_on_time": payload.return_on_time,
            "condition_after": payload.condition_after,
        },
        timestamp=now_iso,
    )

    cursor.execute(
        """
        SELECT r.*, i.title as item_title, i.category as item_category,
               renter.name as renter_name, owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    res = _row_to_rental_dict(cursor.fetchone())
    if res['booking_status'] == 'pending':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'new_request', 'New rental request', f"New rental request for your {res['item_title']} from {res['renter_name']}.", res['id'], res['item_id'], res['requested_at'])
        )
    elif res['booking_status'] == 'approved':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_accepted', 'Rental request accepted', f"Your rental request for {res['item_title']} was accepted by {res['owner_name']}.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'rejected':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_rejected', 'Rental request rejected', f"Your rental request for {res['item_title']} was rejected.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'returned':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'return_request', 'Return requested', f"{res['renter_name']} requested to return {res['item_title']}.", res['id'], res['item_id'], res['returned_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'completed':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
    return res


@router.post("/{rental_id}/confirm", response_model=RentalResponse)
def confirm_rental_return(
    rental_id: int,
    payload: ConfirmReturnRequest,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Owner inspects equipment, confirms successful return, and rates condition (1-5 stars).
    Transitions deposit state: held -> released (escrow unlocked).
    Restores item availability = 1.
    Appends 'returned' block to item's passport chain.
    """
    owner_id = x_user_id if x_user_id is not None else 1

    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental not found.")

    if rental["owner_id"] != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can confirm return and release deposit.")

    if rental["booking_status"] not in ("approved", "returned"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot confirm return in '{rental['booking_status']}' status.",
        )

    # State Machine Transition: held -> released
    try:
        new_deposit_status = transition_on_confirm_return(rental["deposit_status"])
    except InvalidDepositTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    now_iso = datetime.now(timezone.utc).isoformat()

    cursor.execute(
        """
        UPDATE rentals
        SET booking_status = 'completed',
            deposit_status = ?,
            condition_rating = ?,
            completed_at = ?
        WHERE id = ?
        """,
        (new_deposit_status, payload.condition_rating, now_iso, rental_id),
    )
    cursor.execute("UPDATE items SET available = 1 WHERE id = ?", (rental["item_id"],))

    # Append 'returned' event to Item Passport hash chain
    append_event(
        conn=db,
        item_id=rental["item_id"],
        event_type="returned",
        actor_id=owner_id,
        details={
            "action": "Return inspected and confirmed by owner",
            "rental_id": rental_id,
            "condition_rating": payload.condition_rating,
            "condition_notes": payload.condition_notes or "",
            "deposit_status": "released",
            "returned_on_time": bool(rental["return_on_time"]),
        },
        timestamp=now_iso,
    )

    cursor.execute(
        """
        SELECT r.*, i.title as item_title, i.category as item_category,
               renter.name as renter_name, owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    res = _row_to_rental_dict(cursor.fetchone())
    if res['booking_status'] == 'pending':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'new_request', 'New rental request', f"New rental request for your {res['item_title']} from {res['renter_name']}.", res['id'], res['item_id'], res['requested_at'])
        )
    elif res['booking_status'] == 'approved':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_accepted', 'Rental request accepted', f"Your rental request for {res['item_title']} was accepted by {res['owner_name']}.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'rejected':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_rejected', 'Rental request rejected', f"Your rental request for {res['item_title']} was rejected.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'returned':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'return_request', 'Return requested', f"{res['renter_name']} requested to return {res['item_title']}.", res['id'], res['item_id'], res['returned_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'completed':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
    return res


@router.post("/{rental_id}/dispute", response_model=RentalResponse)
def open_rental_dispute(
    rental_id: int,
    payload: DisputeRequest,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Owner or renter opens a formal dispute (e.g. damaged tool, missing accessories).
    Transitions deposit state: held -> disputed (escrow frozen).
    Appends 'dispute_opened' event to item's passport chain.
    """
    user_id = x_user_id if x_user_id is not None else 1

    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental not found.")

    if user_id not in (rental["owner_id"], rental["renter_id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only participants can open a dispute.")

    # State Machine Transition: held -> disputed
    try:
        new_deposit_status = transition_on_dispute(rental["deposit_status"])
    except InvalidDepositTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE rentals
        SET deposit_status = ?,
            dispute_reason = ?
        WHERE id = ?
        """,
        (new_deposit_status, payload.reason, rental_id),
    )

    # Append 'dispute_opened' event to Item Passport hash chain
    append_event(
        conn=db,
        item_id=rental["item_id"],
        event_type="dispute_opened",
        actor_id=user_id,
        details={
            "action": "Security deposit frozen under dispute",
            "rental_id": rental_id,
            "dispute_reason": payload.reason,
            "disputed_by_user_id": user_id,
        },
        timestamp=now_iso,
    )

    cursor.execute(
        """
        SELECT r.*, i.title as item_title, i.category as item_category,
               renter.name as renter_name, owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    res = _row_to_rental_dict(cursor.fetchone())
    if res['booking_status'] == 'pending':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'new_request', 'New rental request', f"New rental request for your {res['item_title']} from {res['renter_name']}.", res['id'], res['item_id'], res['requested_at'])
        )
    elif res['booking_status'] == 'approved':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_accepted', 'Rental request accepted', f"Your rental request for {res['item_title']} was accepted by {res['owner_name']}.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'rejected':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_rejected', 'Rental request rejected', f"Your rental request for {res['item_title']} was rejected.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'returned':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'return_request', 'Return requested', f"{res['renter_name']} requested to return {res['item_title']}.", res['id'], res['item_id'], res['returned_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'completed':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
    return res


@router.post("/{rental_id}/resolve", response_model=RentalResponse)
def resolve_rental_dispute(
    rental_id: int,
    payload: ResolveDisputeRequest,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Arbitrates and settles a disputed deposit (refund_renter | keep_deposit | split).
    Transitions deposit state: disputed -> resolved.
    Re-enables item availability.
    Appends 'dispute_resolved' event to item's passport chain.
    """
    user_id = x_user_id if x_user_id is not None else 1

    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rental not found.")

    # State Machine Transition: disputed -> resolved
    try:
        new_deposit_status = transition_on_resolve(rental["deposit_status"], payload.resolution)
    except (InvalidDepositTransitionError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        UPDATE rentals
        SET booking_status = 'completed',
            deposit_status = ?,
            dispute_resolution = ?,
            completed_at = ?
        WHERE id = ?
        """,
        (new_deposit_status, payload.resolution, now_iso, rental_id),
    )
    cursor.execute("UPDATE items SET available = 1 WHERE id = ?", (rental["item_id"],))

    # Append 'dispute_resolved' event to Item Passport hash chain
    append_event(
        conn=db,
        item_id=rental["item_id"],
        event_type="dispute_resolved",
        actor_id=user_id,
        details={
            "action": "Dispute settled and escrow resolved",
            "rental_id": rental_id,
            "resolution": payload.resolution,
            "notes": payload.notes or "",
        },
        timestamp=now_iso,
    )

    cursor.execute(
        """
        SELECT r.*, i.title as item_title, i.category as item_category,
               renter.name as renter_name, owner.name as owner_name
        FROM rentals r
        LEFT JOIN items i ON r.item_id = i.id
        LEFT JOIN users renter ON r.renter_id = renter.id
        LEFT JOIN users owner ON r.owner_id = owner.id
        WHERE r.id = ?
        """,
        (rental_id,),
    )
    res = _row_to_rental_dict(cursor.fetchone())
    if res['booking_status'] == 'pending':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'new_request', 'New rental request', f"New rental request for your {res['item_title']} from {res['renter_name']}.", res['id'], res['item_id'], res['requested_at'])
        )
    elif res['booking_status'] == 'approved':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_accepted', 'Rental request accepted', f"Your rental request for {res['item_title']} was accepted by {res['owner_name']}.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'rejected':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_rejected', 'Rental request rejected', f"Your rental request for {res['item_title']} was rejected.", res['id'], res['item_id'], res['responded_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'returned':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'return_request', 'Return requested', f"{res['renter_name']} requested to return {res['item_title']}.", res['id'], res['item_id'], res['returned_at'] or res['requested_at'])
        )
    elif res['booking_status'] == 'completed':
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['renter_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
        cursor.execute(
            "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (res['owner_id'], 'rental_completed', 'Rental completed', f"Your rental for {res['item_title']} is now completed.", res['id'], res['item_id'], res['completed_at'] or res['requested_at'])
        )
    return res
