import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from datetime import datetime, timezone
from app.database import get_db
from app.schemas import MessageCreate, MessageResponse, OwnerReviewCreate, OwnerReviewResponse, ItemReviewCreate, ItemReviewResponse, NotificationResponse

router = APIRouter(prefix="/api/rentals", tags=["Rental Extras"])

@router.get("/{rental_id}/messages", response_model=list[MessageResponse])
def get_rental_messages(
    rental_id: int,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = x_user_id if x_user_id is not None else 1
    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
        
    if user_id not in (rental["owner_id"], rental["renter_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to view these messages")
        
    cursor.execute("UPDATE messages SET is_read = 1 WHERE rental_id = ? AND recipient_id = ?", (rental_id, user_id))
    
    query = """
        SELECT m.*, u.name as sender_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.rental_id = ?
        ORDER BY m.created_at ASC
    """
    cursor.execute(query, (rental_id,))
    rows = cursor.fetchall()
    return [dict(r) for r in rows]

@router.post("/{rental_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_rental_message(
    rental_id: int,
    payload: MessageCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = x_user_id if x_user_id is not None else 1
    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
        
    if user_id not in (rental["owner_id"], rental["renter_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to send messages for this rental")
        
    recipient_id = rental["owner_id"] if user_id == rental["renter_id"] else rental["renter_id"]
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute(
        """
        INSERT INTO messages (rental_id, item_id, sender_id, recipient_id, message_text, created_at, is_read)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (rental_id, rental["item_id"], user_id, recipient_id, payload.message_text, now_iso)
    )
    msg_id = cursor.lastrowid
    
    cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
    sender_name = cursor.fetchone()["name"]
    cursor.execute(
        "INSERT INTO notifications (recipient_id, type, title, message, rental_id, item_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (recipient_id, "new_message", f"New message from {sender_name}", f"{payload.message_text[:50]}{'...' if len(payload.message_text) > 50 else ''}", rental_id, rental["item_id"], now_iso)
    )
    
    cursor.execute(
        """
        SELECT m.*, u.name as sender_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.id = ?
        """,
        (msg_id,)
    )
    return dict(cursor.fetchone())

@router.post("/{rental_id}/reviews/owner", response_model=OwnerReviewResponse, status_code=status.HTTP_201_CREATED)
def submit_owner_review(
    rental_id: int,
    payload: OwnerReviewCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = x_user_id if x_user_id is not None else 1
    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
        
    if rental["renter_id"] != user_id:
        raise HTTPException(status_code=403, detail="Only the borrower can review the owner")
        
    if rental["booking_status"] != "completed":
        raise HTTPException(status_code=400, detail="Rental must be completed before reviewing")
        
    cursor.execute("SELECT id FROM reviews WHERE rental_id = ? AND reviewer_id = ?", (rental_id, user_id))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="Review already submitted")
        
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute(
        """
        INSERT INTO reviews (rental_id, reviewer_id, reviewed_user_id, item_id, rating, product_condition, price_fairness, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (rental_id, user_id, rental["owner_id"], rental["item_id"], payload.rating, payload.product_condition, payload.price_fairness, payload.comment or "", now_iso)
    )
    rev_id = cursor.lastrowid
    
    cursor.execute(
        """
        SELECT r.*, u.name as reviewer_name
        FROM reviews r
        JOIN users u ON r.reviewer_id = u.id
        WHERE r.id = ?
        """,
        (rev_id,)
    )
    return dict(cursor.fetchone())

@router.post("/{rental_id}/reviews/item", response_model=ItemReviewResponse, status_code=status.HTTP_201_CREATED)
def submit_item_review(
    rental_id: int,
    payload: ItemReviewCreate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    user_id = x_user_id if x_user_id is not None else 1
    cursor = db.cursor()
    cursor.execute("SELECT * FROM rentals WHERE id = ?", (rental_id,))
    rental = cursor.fetchone()
    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")
        
    if rental["renter_id"] != user_id:
        raise HTTPException(status_code=403, detail="Only the borrower can review the item")
        
    if rental["booking_status"] != "completed":
        raise HTTPException(status_code=400, detail="Rental must be completed before reviewing")
        
    cursor.execute("SELECT id FROM item_reviews WHERE rental_id = ? AND reviewer_id = ?", (rental_id, user_id))
    if cursor.fetchone():
        raise HTTPException(status_code=409, detail="Item review already submitted")
        
    now_iso = datetime.now(timezone.utc).isoformat()
    
    cursor.execute(
        """
        INSERT INTO item_reviews (rental_id, reviewer_id, item_id, rating, product_condition, comment, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (rental_id, user_id, rental["item_id"], payload.rating, payload.product_condition, payload.comment or "", now_iso)
    )
    rev_id = cursor.lastrowid
    
    cursor.execute(
        """
        SELECT r.*, u.name as reviewer_name
        FROM item_reviews r
        JOIN users u ON r.reviewer_id = u.id
        WHERE r.id = ?
        """,
        (rev_id,)
    )
    return dict(cursor.fetchone())

@router.get("/notifications", response_model=list[NotificationResponse])
def get_notifications(
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db)
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    cursor = db.cursor()
    cursor.execute(
        "SELECT * FROM notifications WHERE recipient_id = ? ORDER BY created_at DESC", 
        (x_user_id,)
    )
    rows = cursor.fetchall()
    return [dict(r) for r in rows]

@router.post("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db)
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    cursor = db.cursor()
    cursor.execute("SELECT recipient_id FROM notifications WHERE id = ?", (notification_id,))
    notif = cursor.fetchone()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    if notif["recipient_id"] != x_user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    return {"status": "success"}

@router.post("/notifications/read-all")
def mark_all_notifications_read(
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db)
):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    cursor = db.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE recipient_id = ?", (x_user_id,))
    return {"status": "success"}
