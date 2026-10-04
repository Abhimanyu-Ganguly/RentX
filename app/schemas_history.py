import sqlite3
from typing import Optional, List, Any
from pydantic import BaseModel, Field

class HistoricalRentalInfo(BaseModel):
    rental_id: int
    start_date: str
    end_date: str
    days: int
    total_price: float
    booking_status: str
    completed_at: Optional[str]
    # Do not expose renter_name publicly unless it's owner. We will handle in logic.
    renter_name: Optional[str] = None

class ItemHistoryStats(BaseModel):
    total_completed_rentals: int
    total_rental_requests: int
    total_approved_rentals: int
    total_rental_days: int
    unique_borrowers: int
    last_completed_rental_date: Optional[str]
    active_rental_status: Optional[str]
    average_rating: float
    review_count: int

class ItemHistoryResponse(BaseModel):
    item_id: int
    title: str
    category: str
    description: str
    owner_name: str
    is_listed: bool
    available: bool
    created_at: str
    
    stats: ItemHistoryStats
    activity_events: list[dict] # Use dict for simplicity
    rental_history: Optional[list[HistoricalRentalInfo]] = None
