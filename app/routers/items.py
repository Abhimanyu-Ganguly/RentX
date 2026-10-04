"""
Items and Item Passport HTTP router.
Handles item listings, photo hashing, item search/filtering, and passport chain verification.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from app.config import CATEGORIES, CATEGORY_CHECKLISTS, UPLOADS_DIR
from app.database import get_db
from app.schemas import ItemResponse, PassportVerifyResponse
from app.services.passport import (
    append_event,
    compute_item_hash,
    hash_bytes,
    verify_chain,
)


router = APIRouter(prefix="/api/items", tags=["Items"])


def _row_to_item_dict(row: sqlite3.Row) -> dict:
    """Helper to convert an SQLite row into an ItemResponse compatible dictionary."""
    d = dict(row)
    # Parse condition checklist JSON string
    if isinstance(d.get("condition_checklist"), str):
        try:
            d["condition_checklist"] = json.loads(d["condition_checklist"])
        except Exception:
            d["condition_checklist"] = {}
    d["available"] = bool(d.get("available", 1))
    return d


@router.get("/config")
def get_marketplace_config():
    """
    Returns available categories and default condition checklists for each category.
    Allows frontend to dynamically render the appropriate inspection checklist during item creation.
    """
    return {
        "categories": CATEGORIES,
        "checklists": CATEGORY_CHECKLISTS,
    }


@router.get("", response_model=list[ItemResponse])
def list_items(
    category: Optional[str] = Query(None, description="Filter by category"),
    q: Optional[str] = Query(None, description="Keyword search in title, tags, and description"),
    available_only: Optional[bool] = Query(None, description="Filter by availability"),
    mode: Optional[str] = Query(None, description="Filter by commercial or community mode"),
    owner_id: Optional[int] = Query(None, description="Filter by owner"),
    include_unlisted: Optional[bool] = Query(False, description="Include unlisted items"),
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Lists marketplace items with optional search and category filters.
    """
    query = """
        SELECT i.*, u.name as owner_name, u.dorm as owner_dorm
        FROM items i
        LEFT JOIN users u ON i.owner_id = u.id
        WHERE 1=1
    """
    params: list = []

    if category and category.lower() != "all":
        query += " AND LOWER(i.category) = ?"
        params.append(category.lower())

    if owner_id is not None:
        query += " AND i.owner_id = ?"
        params.append(owner_id)

    # By default, only show listed items, unless include_unlisted is true AND the user requesting it is the owner
    if not (include_unlisted and x_user_id is not None and x_user_id == owner_id):
        query += " AND i.is_listed = 1"


    if q and q.strip():
        search_term = f"%{q.strip().lower()}%"
        query += " AND (LOWER(i.title) LIKE ? OR LOWER(i.description) LIKE ? OR LOWER(i.tags) LIKE ?)"
        params.extend([search_term, search_term, search_term])

    if available_only is not None:
        query += " AND i.available = ?"
        params.append(1 if available_only else 0)

    if mode:
        query += " AND i.mode = ?"
        params.append(mode)

    query += " ORDER BY i.id DESC"

    cursor = db.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    return [_row_to_item_dict(r) for r in rows]


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    title: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    value: float = Form(...),
    price_per_day: float = Form(...),
    deposit_amount: float = Form(...),
    serial: str = Form(...),
    tags: str = Form(""),
    mode: str = Form("commercial"),
    condition_checklist: str = Form("{}"),
    photo: Optional[UploadFile] = File(None),
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Creates a new equipment listing with real SHA-256 photo & item hashing,
    and initializes its tamper-verifiable Item Passport (genesis block).
    """
    owner_id = x_user_id if x_user_id is not None else 1

    # Verify owner exists
    cursor = db.cursor()
    cursor.execute("SELECT id, name FROM users WHERE id = ?", (owner_id,))
    owner = cursor.fetchone()
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Owner user with ID {owner_id} does not exist.",
        )

    # Validate or parse checklist JSON
    try:
        checklist_dict = json.loads(condition_checklist) if isinstance(condition_checklist, str) else condition_checklist
    except Exception:
        checklist_dict = {"body": "good"}

    if category.lower() not in [c.lower() for c in CATEGORIES]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid category '{category}'. Allowed: {', '.join(CATEGORIES)}",
        )

    if value <= 0 or price_per_day < 0 or deposit_amount < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Value must be positive. Price and deposit must be non-negative.",
        )

    # Process photo & calculate cryptographic hash
    if photo and photo.filename:
        ext = Path(photo.filename).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid file type '{ext}'. Allowed: .jpg, .jpeg, .png, .webp",
            )
        file_bytes = await photo.read()
        if len(file_bytes) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="File too large. Maximum upload size is 5 MB.",
            )
        photo_hash = hash_bytes(file_bytes)
        safe_serial = "".join(c for c in serial if c.isalnum() or c in "-_")
        photo_filename = f"item_{safe_serial}_{photo_hash[:12]}{ext}"
        saved_path = UPLOADS_DIR / photo_filename
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
        photo_path = f"/uploads/{photo_filename}"
    else:
        # Generate deterministic mock bytes based on serial & title for demo photo
        placeholder_bytes = f"placeholder-photo-for-{title}-{serial}".encode("utf-8")
        photo_hash = hash_bytes(placeholder_bytes)
        photo_path = "/static/img/placeholder.svg"

    # Compute composite item fingerprint
    item_hash = compute_item_hash(photo_hash, serial, title)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Insert item record
    cursor.execute(
        """
        INSERT INTO items (
            owner_id, title, category, description, value, price_per_day, deposit_amount,
            serial, photo_path, photo_hash, item_hash, condition_checklist, tags, mode, available, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            owner_id,
            title,
            category,
            description,
            value,
            price_per_day,
            deposit_amount,
            serial,
            photo_path,
            photo_hash,
            item_hash,
            json.dumps(checklist_dict, sort_keys=True),
            tags,
            mode,
            now_iso,
        ),
    )
    item_id = cursor.lastrowid

    # Append Genesis Event #1 (Registered) to Item Passport chain inside same transaction
    append_event(
        conn=db,
        item_id=item_id,
        event_type="registered",
        actor_id=owner_id,
        details={
            "action": "Item registered on campus network",
            "owner": owner["name"],
            "serial": serial,
            "photo_hash": photo_hash,
            "item_hash": item_hash,
            "initial_condition": checklist_dict,
            "stated_value": value,
            "daily_rate": price_per_day,
            "deposit_required": deposit_amount,
        },
        timestamp=now_iso,
    )

    # Return created item with joined owner name
    cursor.execute(
        """
        SELECT i.*, u.name as owner_name, u.dorm as owner_dorm
        FROM items i
        LEFT JOIN users u ON i.owner_id = u.id
        WHERE i.id = ?
        """,
        (item_id,),
    )
    item_row = cursor.fetchone()
    return _row_to_item_dict(item_row)


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Retrieves a single item by ID.
    """
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT i.*, u.name as owner_name, u.dorm as owner_dorm
        FROM items i
        LEFT JOIN users u ON i.owner_id = u.id
        WHERE i.id = ?
        """,
        (item_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found.",
        )
    return _row_to_item_dict(row)


@router.get("/{item_id}/passport", response_model=PassportVerifyResponse)
def get_item_passport(item_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Computes real-time cryptographic verification of the item's append-only hash chain.
    Returns:
      - is_valid: bool (true if all cryptographic hashes and parent pointers match)
      - broken_at_seq: int | null (sequence number where tamper occurred if invalid)
      - events: complete verifiable timeline of events
    """
    cursor = db.cursor()
    cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
    if not cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item with ID {item_id} not found.",
        )

    is_valid, broken_at_seq, events = verify_chain(db, item_id)
    return {
        "item_id": item_id,
        "is_valid": is_valid,
        "broken_at_seq": broken_at_seq,
        "total_events": len(events),
        "events": events,
    }


from pydantic import BaseModel
class ListingUpdate(BaseModel):
    is_listed: bool

@router.patch("/{item_id}/listing", response_model=ItemResponse)
def update_listing_status(
    item_id: int,
    listing_update: ListingUpdate,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    owner_id = x_user_id if x_user_id is not None else 1
    cursor = db.cursor()
    cursor.execute("SELECT owner_id, is_listed FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    if row["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this item")
    
    current_listed = bool(row["is_listed"])
    target_listed = listing_update.is_listed
    
    if current_listed != target_listed:
        cursor.execute(
            "UPDATE items SET is_listed = ? WHERE id = ?",
            (1 if target_listed else 0, item_id)
        )
        
        event_type = "listed" if target_listed else "unlisted"
        action_msg = "Item listed" if target_listed else "Item unlisted"
        
        append_event(
            conn=db, item_id=item_id, event_type=event_type,
            actor_id=owner_id, details={"action": action_msg},
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    
    cursor.execute(
        """
        SELECT i.*, u.name as owner_name, u.dorm as owner_dorm
        FROM items i
        LEFT JOIN users u ON i.owner_id = u.id
        WHERE i.id = ?
        """,
        (item_id,),
    )
    return _row_to_item_dict(cursor.fetchone())


from app.schemas import ItemHistoryResponse, ItemHistoryStats, HistoricalRentalInfo

@router.get("/{item_id}/history", response_model=ItemHistoryResponse)
def get_item_history(
    item_id: int,
    x_user_id: Optional[int] = Header(None, alias="X-User-Id"),
    db: sqlite3.Connection = Depends(get_db),
):
    """
    Retrieves the complete historical record of the item.
    Returns stats based on the database and conditionally returns private
    rental history if the requester is the item's owner.
    """
    user_id = x_user_id

    cursor = db.cursor()
    cursor.execute(
        """
        SELECT i.*, u.name as owner_name, u.dorm as owner_dorm
        FROM items i
        LEFT JOIN users u ON i.owner_id = u.id
        WHERE i.id = ?
        """,
        (item_id,),
    )
    item_row = cursor.fetchone()
    if not item_row:
        raise HTTPException(status_code=404, detail="Item not found")

    is_owner = (user_id == item_row["owner_id"])

    # Fetch stats
    cursor.execute(
        """
        SELECT 
            COUNT(*) as total_requests,
            SUM(CASE WHEN booking_status = 'completed' THEN 1 ELSE 0 END) as total_completed,
            SUM(CASE WHEN booking_status IN ('approved', 'active', 'completed', 'return_requested') THEN 1 ELSE 0 END) as total_approved,
            SUM(CASE WHEN booking_status = 'completed' THEN days ELSE 0 END) as total_days,
            COUNT(DISTINCT renter_id) as unique_borrowers,
            MAX(CASE WHEN booking_status = 'completed' THEN completed_at ELSE NULL END) as last_completed
        FROM rentals
        WHERE item_id = ?
        """,
        (item_id,)
    )
    stats_row = cursor.fetchone()

    cursor.execute(
        """
        SELECT booking_status FROM rentals 
        WHERE item_id = ? AND booking_status IN ('active', 'return_requested')
        ORDER BY id DESC LIMIT 1
        """,
        (item_id,)
    )
    active_row = cursor.fetchone()
    active_status = active_row["booking_status"] if active_row else None

    cursor.execute(
        "SELECT AVG(rating) as avg_rating, COUNT(id) as review_count FROM item_reviews WHERE item_id = ?",
        (item_id,)
    )
    review_row = cursor.fetchone()
    
    # Also fetch the actual reviews
    cursor.execute(
        '''
        SELECT r.rating, r.comment, r.product_condition, r.created_at, u.name as reviewer_name
        FROM item_reviews r
        JOIN users u ON r.reviewer_id = u.id
        WHERE r.item_id = ?
        ORDER BY r.created_at DESC
        ''',
        (item_id,)
    )
    item_reviews_list = [dict(r) for r in cursor.fetchall()]
    avg_rating = round(review_row["avg_rating"], 1) if review_row and review_row["avg_rating"] else 0.0
    review_count = review_row["review_count"] if review_row else 0

    stats = ItemHistoryStats(
        total_completed_rentals=stats_row["total_completed"] or 0,
        total_rental_requests=stats_row["total_requests"] or 0,
        total_approved_rentals=stats_row["total_approved"] or 0,
        total_rental_days=stats_row["total_days"] or 0,
        unique_borrowers=stats_row["unique_borrowers"] or 0,
        last_completed_rental_date=stats_row["last_completed"],
        active_rental_status=active_status,
        average_rating=avg_rating,
        review_count=review_count
    )

    # Fetch passport events
    is_valid, broken_at, events = verify_chain(db, item_id)
    activity_events = events
    
    rental_history = None
    if is_owner:
        cursor.execute(
            """
            SELECT r.id, r.start_date, r.end_date, r.days, r.total_price, r.booking_status, r.completed_at, u.name as renter_name
            FROM rentals r
            JOIN users u ON r.renter_id = u.id
            WHERE r.item_id = ?
            ORDER BY r.start_date DESC
            """,
            (item_id,)
        )
        rental_history = []
        for row in cursor.fetchall():
            rental_history.append(HistoricalRentalInfo(
                rental_id=row["id"],
                start_date=row["start_date"] or "",
                end_date=row["end_date"] or "",
                days=row["days"],
                total_price=row["total_price"],
                booking_status=row["booking_status"],
                completed_at=row["completed_at"],
                renter_name=row["renter_name"]
            ))

    return ItemHistoryResponse(
        item_id=item_row["id"],
        title=item_row["title"],
        category=item_row["category"],
        description=item_row["description"],
        owner_name=item_row["owner_name"] or "Unknown",
        is_listed=bool(item_row["is_listed"]),
        available=bool(item_row["available"]),
        created_at=item_row["created_at"],
        stats=stats,
        activity_events=activity_events,
        rental_history=rental_history,
        item_reviews=item_reviews_list
    )
