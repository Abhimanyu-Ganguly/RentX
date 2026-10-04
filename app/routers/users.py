"""
User management and reputation HTTP router.
Contains only HTTP routing and request parameter extraction; business logic is delegated to services.
"""

import sqlite3
import secrets
import hashlib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from app.database import get_db
from app.schemas import (
    GoogleAuthRequest,
    PhoneOtpSendRequest,
    PhoneOtpVerifyRequest,
    UserCreate,
    UserReputationResponse,
    UserResponse,
)
from app.services.reputation import get_user_reputation


router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("", response_model=list[UserResponse])
def list_users(db: sqlite3.Connection = Depends(get_db)):
    """
    Returns all registered campus users.
    Used for demo profile switcher in the top navigation bar.
    """
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users ORDER BY id ASC")
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: sqlite3.Connection = Depends(get_db)):
    """
    Creates a new campus user profile.
    """
    cursor = db.cursor()
    # Check if email is already in use
    cursor.execute("SELECT id FROM users WHERE email = ?", (payload.email,))
    if cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{payload.email}' already exists.",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute(
        """
        INSERT INTO users (name, email, phone, dorm, avatar_url, auth_provider, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.name,
            payload.email,
            payload.phone or "",
            payload.dorm or "",
            payload.avatar_url or "",
            payload.auth_provider or "campus",
            now_iso,
        ),
    )
    user_id = cursor.lastrowid
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    return dict(row)


@router.post("/auth/google", response_model=UserResponse)
def sign_in_with_google(payload: GoogleAuthRequest, db: sqlite3.Connection = Depends(get_db)):
    """
    Simulates Google Account OAuth sign-in.
    Finds existing user by Google email or creates a new student profile.
    """
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (payload.email,))
    existing = cursor.fetchone()

    now_iso = datetime.now(timezone.utc).isoformat()

    if existing:
        cursor.execute(
            """
            UPDATE users
            SET name = ?, avatar_url = COALESCE(NULLIF(?, ''), avatar_url), auth_provider = 'google'
            WHERE id = ?
            """,
            (payload.name, payload.avatar_url, existing["id"]),
        )
        cursor.execute("SELECT * FROM users WHERE id = ?", (existing["id"],))
        return dict(cursor.fetchone())

    # Create new user via Google
    cursor.execute(
        """
        INSERT INTO users (name, email, phone, dorm, avatar_url, auth_provider, created_at)
        VALUES (?, ?, '', ?, ?, 'google', ?)
        """,
        (payload.name, payload.email, payload.dorm or "Campus Resident", payload.avatar_url or "", now_iso),
    )
    new_id = cursor.lastrowid
    cursor.execute("SELECT * FROM users WHERE id = ?", (new_id,))
    return dict(cursor.fetchone())


@router.post("/auth/phone/send-otp")
def send_phone_otp(payload: PhoneOtpSendRequest):
    """
    Sends a simulated 6-digit SMS verification code to the phone number.
    Returns demo OTP code '123456' for immediate testing.
    """
    return {
        "success": True,
        "phone": payload.phone,
        "demo_otp": "123456",
        "message": f"Verification code sent to {payload.phone}. Use demo code: 123456",
    }


@router.post("/auth/phone/verify-otp", response_model=UserResponse)
def verify_phone_otp(payload: PhoneOtpVerifyRequest, db: sqlite3.Connection = Depends(get_db)):
    """
    Verifies SMS OTP code and signs in or creates a new phone-verified account.
    """
    # Verify OTP (accept standard demo OTP 123456)
    if payload.otp != "123456":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code. (Hint: Demo code is 123456)",
        )

    clean_phone = "".join(filter(str.isdigit, payload.phone)) or "0000"
    cursor = db.cursor()

    # Search for existing user with this phone number
    cursor.execute("SELECT * FROM users WHERE phone = ?", (payload.phone,))
    existing = cursor.fetchone()
    if existing:
        return dict(existing)

    # Check if a synthetic email already exists
    synthetic_email = f"user_{clean_phone}@phone.rentx.app"
    cursor.execute("SELECT * FROM users WHERE email = ?", (synthetic_email,))
    existing_by_email = cursor.fetchone()
    if existing_by_email:
        return dict(existing_by_email)

    # Register new phone user
    now_iso = datetime.now(timezone.utc).isoformat()
    name = payload.name.strip() if payload.name and payload.name.strip() else f"Student (+{clean_phone[-4:]})"
    avatar = f"https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150"

    cursor.execute(
        """
        INSERT INTO users (name, email, phone, dorm, avatar_url, auth_provider, created_at)
        VALUES (?, ?, ?, ?, ?, 'phone', ?)
        """,
        (name, synthetic_email, payload.phone, payload.dorm or "Campus Dorm", avatar, now_iso),
    )
    new_id = cursor.lastrowid
    cursor.execute("SELECT * FROM users WHERE id = ?", (new_id,))
    return dict(cursor.fetchone())


@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Retrieves user profile details by ID.
    """
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )
    return dict(row)


@router.get("/{user_id}/reputation", response_model=UserReputationResponse)
def get_user_reputation_endpoint(user_id: int, db: sqlite3.Connection = Depends(get_db)):
    """
    Computes and returns transparent, on-demand reputation statistics for the user
    separated across both Renter and Owner dimensions.
    """
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found.",
        )

    return get_user_reputation(db, user_id)

from pydantic import BaseModel
class UserLocationUpdate(BaseModel):
    dorm: str

@router.put("/{user_id}/location", response_model=UserResponse)
def update_user_location(user_id: int, payload: UserLocationUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    cursor.execute("UPDATE users SET dorm = ? WHERE id = ?", (payload.dorm, user_id))
    db.commit()
    
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return dict(cursor.fetchone())

from app.schemas import UserSignupRequest, UserLoginRequest
@router.post("/signup", response_model=UserResponse)
def signup_user(payload: UserSignupRequest, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password, created_at) VALUES (?, ?, ?, ?)",
            (payload.name, payload.email, payload.password, datetime.now(timezone.utc).isoformat())
        )
        db.commit()
        user_id = cursor.lastrowid
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        return dict(cursor.fetchone())
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")

@router.post("/login", response_model=UserResponse)
def login_user(payload: UserLoginRequest, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ?", (payload.email, payload.password))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return dict(user)

@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(user)

from pydantic import BaseModel
class AdminRatingUpdate(BaseModel):
    rating: float

@router.put("/{user_id}/rating")
def update_user_rating(user_id: int, payload: AdminRatingUpdate, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("UPDATE users SET manual_rating = ? WHERE id = ?", (payload.rating, user_id))
    db.commit()
    return {"status": "ok"}


from app.schemas import ForgotPasswordRequest, ResetPasswordRequest
import logging

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (payload.email,))
    user = cursor.fetchone()
    
    if user:
        # Generate secure random token
        raw_token = secrets.token_urlsafe(32)
        # Hash token for DB storage
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        
        created_at = datetime.now(timezone.utc)
        expires_at = datetime.now(timezone.utc)
        # expires in 30 minutes
        expires_at = datetime.fromtimestamp(created_at.timestamp() + 1800, tz=timezone.utc)
        
        cursor.execute(
            "INSERT INTO password_resets (user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (user["id"], token_hash, created_at.isoformat(), expires_at.isoformat())
        )
        db.commit()
        
        reset_link = f"/#reset-password?token={raw_token}"
        # DEV MODE LOG
        logging.warning(f"=== DEV MODE FORGOT PASSWORD ===")
        logging.warning(f"Reset Link for {payload.email}: {reset_link}")
        logging.warning(f"=================================")

    return {"detail": "If an account exists with that email, a password reset link has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: sqlite3.Connection = Depends(get_db)):
    cursor = db.cursor()
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    
    cursor.execute(
        "SELECT * FROM password_resets WHERE token_hash = ? ORDER BY id DESC LIMIT 1",
        (token_hash,)
    )
    reset_record = cursor.fetchone()
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid password reset link.")
        
    if reset_record["used_at"]:
        raise HTTPException(status_code=400, detail="This reset link is no longer valid.")
        
    expires_at = datetime.fromisoformat(reset_record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
        
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        
    # Valid! Update user password using the same system as signup
    user_id = reset_record["user_id"]
    cursor.execute(
        "UPDATE users SET password = ? WHERE id = ?",
        (payload.new_password, user_id)
    )
    
    # Invalidate token
    cursor.execute(
        "UPDATE password_resets SET used_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), reset_record["id"])
    )
    db.commit()
    
    return {"detail": "Password successfully changed."}
