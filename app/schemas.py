"""
Pydantic v2 request and response validation models for all API endpoints.
Provides strong type-checking, default values, and serialization for API inputs/outputs.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


# ==========================================
# User Models
# ==========================================

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of student/user")
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="Campus email address")
    phone: Optional[str] = Field(default="", description="Phone number for SMS alerts")
    dorm: Optional[str] = Field(default="", max_length=100, description="Campus residence / dorm hall")
    avatar_url: Optional[str] = Field(default="", description="Optional avatar image URL")
    auth_provider: Optional[str] = Field(default="campus", description="google, phone, or campus")



class UserSignupRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$")
    password: str = Field(..., min_length=8)

class UserLoginRequest(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str] = ""
    dorm: str
    avatar_url: str
    auth_provider: Optional[str] = "campus"
    created_at: str
    is_admin: Optional[int] = 0
    manual_rating: Optional[float] = None


class GoogleAuthRequest(BaseModel):
    email: str = Field(..., description="Google account email")
    name: str = Field(..., description="Google account full name")
    avatar_url: Optional[str] = Field(default="", description="Google profile picture URL")
    dorm: Optional[str] = Field(default="Campus Resident", description="Campus dorm residence")
    token: Optional[str] = Field(default="mock_google_oauth_token", description="OAuth credential token")


class PhoneOtpSendRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20, description="Mobile phone number with country code")


class PhoneOtpVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20, description="Mobile phone number")
    otp: str = Field(..., min_length=4, max_length=10, description="6-digit verification code (e.g. 123456)")
    name: Optional[str] = Field(default="", description="Name for new account registration")
    dorm: Optional[str] = Field(default="Campus Dorm", description="Dorm hall for new account")


# ==========================================
# Item Models
# ==========================================

class ItemCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    category: str = Field(...)
    description: Optional[str] = Field(default="")
    value: float = Field(..., gt=0, description="Estimated replacement value in dollars")
    price_per_day: float = Field(..., ge=0, description="Daily rental fee in dollars")
    deposit_amount: float = Field(..., ge=0, description="Refundable security deposit in dollars")
    serial: str = Field(..., min_length=1, description="Serial number or campus asset tag")
    tags: Optional[str] = Field(default="", description="Comma-separated tags (e.g. 'tent,hiking,4-person')")
    mode: Optional[str] = Field(default="commercial", pattern="^(commercial|community)$")
    condition_checklist: dict[str, str] = Field(
        ...,
        description="Dictionary mapping item component names to condition grade ('good', 'fair', 'poor')"
    )


class ItemResponse(BaseModel):
    id: int
    owner_id: int
    owner_name: Optional[str] = None
    owner_dorm: Optional[str] = None
    title: str
    category: str
    description: str
    value: float
    price_per_day: float
    deposit_amount: float
    serial: str
    photo_path: str
    photo_hash: str
    item_hash: str
    condition_checklist: dict[str, str]
    tags: str
    mode: str
    available: bool
    is_listed: bool = True
    created_at: str


# ==========================================
# Passport & Event Models
# ==========================================

class PassportEventResponse(BaseModel):
    id: int
    item_id: int
    seq: int
    prev_hash: str
    event_type: str
    actor_id: int
    actor_name: Optional[str] = None
    details: dict[str, Any]
    timestamp: str
    event_hash: str


class PassportVerifyResponse(BaseModel):
    item_id: int
    is_valid: bool
    broken_at_seq: Optional[int] = None
    total_events: int
    events: list[PassportEventResponse]


# ==========================================
# Rental Lifecycle Models
# ==========================================

class RentalCreate(BaseModel):
    item_id: int
    start_date: str = Field(..., description="Rental start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="Rental end date (YYYY-MM-DD)")
    days: int = Field(..., ge=1, le=30, description="Rental duration in days (1-30)")


class ReturnRequest(BaseModel):
    condition_after: dict[str, str] = Field(
        default_factory=dict,
        description="Component-by-component condition check by renter upon return"
    )
    return_on_time: bool = Field(default=True, description="Whether returned on or before agreed time")


class ConfirmReturnRequest(BaseModel):
    condition_rating: int = Field(..., ge=1, le=5, description="Owner rating of returned item condition (1-5 stars)")
    condition_notes: Optional[str] = Field(default="", description="Optional feedback on item condition")


class DisputeRequest(BaseModel):
    reason: str = Field(..., min_length=5, description="Detailed explanation of the issue or damage")


class ResolveDisputeRequest(BaseModel):
    resolution: str = Field(..., pattern="^(refund_renter|keep_deposit|split)$", description="Deposit allocation rule")
    notes: Optional[str] = Field(default="", description="Arbitration / settlement notes")


class RentalResponse(BaseModel):
    id: int
    item_id: int
    item_title: Optional[str] = None
    item_category: Optional[str] = None
    renter_id: int
    renter_name: Optional[str] = None
    owner_id: int
    owner_name: Optional[str] = None
    owner_dorm: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days: int
    total_price: float
    deposit_amount: float
    booking_status: str
    deposit_status: str
    condition_rating: Optional[int] = None
    return_on_time: bool
    dispute_reason: str
    dispute_resolution: str
    requested_at: str
    responded_at: Optional[str] = None
    returned_at: Optional[str] = None
    completed_at: Optional[str] = None



# ==========================================
# Review Models
# ==========================================

class ReviewCreate(BaseModel):
    rental_id: int
    rating: int = Field(..., ge=1, le=5, description="Rating from 1 to 5")
    comment: Optional[str] = Field(default="", description="Optional text review")

class ReviewResponse(BaseModel):
    id: int
    rental_id: int
    reviewer_id: int
    reviewer_name: Optional[str] = None
    reviewed_user_id: int
    item_id: int
    item_title: Optional[str] = None
    rating: int
    comment: str
    created_at: str

# ==========================================
# Reputation Models
# ==========================================

class RenterReputation(BaseModel):
    has_history: bool
    return_punctuality_pct: Optional[float] = None
    item_care_pct: Optional[float] = None
    dispute_count: int
    successful_rentals: int
    total_completed: int
    average_service_rating: Optional[float] = 0.0
    total_reviews: Optional[int] = 0
    reviews: Optional[list] = []


class OwnerReputation(BaseModel):
    has_history: bool
    reliability_pct: Optional[float] = None
    avg_response_hours: Optional[float] = None
    dispute_count: int
    total_bookings_received: int
    total_accepted: int
    total_completed: int
    average_service_rating: Optional[float] = 0.0
    total_reviews: Optional[int] = 0
    reviews: Optional[list] = []


class UserReputationResponse(BaseModel):
    user_id: int
    user_name: str
    renter: RenterReputation
    owner: OwnerReputation


# ==========================================
# Need-Based Matching Models
# ==========================================

class NeedQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="What are you trying to do? e.g. 'going camping with friends'")


class BundleTagItem(BaseModel):
    tag: str
    matched: bool
    item: Optional[ItemResponse] = None


class NeedMatchResponse(BaseModel):
    query: str
    matched_need_key: Optional[str] = None
    need_title: Optional[str] = None
    required_tags: list[str]
    bundle: list[BundleTagItem]
    missing_tags: list[str]
    total_bundle_price_per_day: float
    total_bundle_deposit: float


class AdminRatingUpdate(BaseModel):
    rating: float


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
    item_reviews: Optional[list] = []


class MessageCreate(BaseModel):
    message_text: str = Field(..., description="The message content")

class MessageResponse(BaseModel):
    id: int
    rental_id: int
    item_id: int
    sender_id: int
    recipient_id: int
    sender_name: str
    message_text: str
    created_at: str
    is_read: int

class OwnerReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    product_condition: str
    price_fairness: str
    comment: Optional[str] = ""

class ItemReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    product_condition: str
    comment: Optional[str] = ""

class OwnerReviewResponse(BaseModel):
    id: int
    rental_id: int
    reviewer_id: int
    reviewer_name: str
    rating: int
    product_condition: str
    price_fairness: str
    comment: str
    created_at: str

class ItemReviewResponse(BaseModel):
    id: int
    rental_id: int
    reviewer_id: int
    reviewer_name: str
    rating: int
    product_condition: str
    comment: str
    created_at: str

class NotificationResponse(BaseModel):
    id: int
    recipient_id: int
    type: str
    title: str
    message: str
    rental_id: Optional[int]
    item_id: Optional[int]
    created_at: str
    is_read: int

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)
