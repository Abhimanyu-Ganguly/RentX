import sqlite3
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from app.database import get_db
from app.schemas import ReviewCreate, ReviewResponse

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])

def _row_to_review_dict(row: sqlite3.Row) -> dict:
    if not row:
        return None
    d = dict(row)
    return d

@router.post("", response_model=ReviewResponse)
def create_review(
    payload: ReviewCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Creates a new review (1-5 stars + optional comment) for a completed rental.
    Renter can review the item/owner, or Owner can review the renter.
    """
    reviewer_id = x_user_id if x_user_id is not None else 1
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (payload.rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found.")
        
    if rental["booking_status"] != "completed":
        raise HTTPException(status_code=400, detail="Cannot review an incomplete rental.")
        
    if reviewer_id not in (rental["renter_id"], rental["owner_id"]):
        raise HTTPException(status_code=403, detail="You are not a participant in this rental.")
        
    # Determine who is being reviewed
    reviewed_user_id = rental["owner_id"] if reviewer_id == rental["renter_id"] else rental["renter_id"]
    
    # Check if a review already exists from this user for this rental
    cursor.execute("SELECT id FROM reviews WHERE rental_id = ? AND reviewer_id = ?", (payload.rental_id, reviewer_id))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="You have already submitted a review for this rental.")
        
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO reviews (rental_id, reviewer_id, reviewed_user_id, item_id, rating, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (payload.rental_id, reviewer_id, reviewed_user_id, rental["item_id"], payload.rating, payload.comment, now_iso)
    )
    review_id = cursor.lastrowid
    
    cursor.execute(
        """
        SELECT r.*, reviewer.name as reviewer_name, i.title as item_title
        FROM reviews r
        LEFT JOIN users reviewer ON r.reviewer_id = reviewer.id
        LEFT JOIN items i ON r.item_id = i.id
        WHERE r.id = ?
        """,
        (review_id,)
    )
    return _row_to_review_dict(cursor.fetchone())

@router.get("/user/{user_id}", response_model=List[ReviewResponse])
def get_user_reviews(user_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Get all reviews for a specific user (either as owner or renter).
    """
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT r.*, reviewer.name as reviewer_name, i.title as item_title
        FROM reviews r
        LEFT JOIN users reviewer ON r.reviewer_id = reviewer.id
        LEFT JOIN items i ON r.item_id = i.id
        WHERE r.reviewed_user_id = ?
        ORDER BY r.created_at DESC
        """,
        (user_id,)
    )
    rows = cursor.fetchall()
    return [_row_to_review_dict(r) for r in rows]

@router.get("/item/{item_id}", response_model=List[ReviewResponse])
def get_item_reviews(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Get all reviews for a specific item (from renters who borrowed it).
    """
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT r.*, reviewer.name as reviewer_name, i.title as item_title
        FROM reviews r
        LEFT JOIN users reviewer ON r.reviewer_id = reviewer.id
        LEFT JOIN items i ON r.item_id = i.id
        WHERE r.item_id = ? AND r.reviewer_id != i.owner_id
        ORDER BY r.created_at DESC
        """,
        (item_id,)
    )
    rows = cursor.fetchall()
    return [_row_to_review_dict(r) for r in rows]
