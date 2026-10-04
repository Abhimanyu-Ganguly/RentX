"""
Tests for Google OAuth simulation and Phone SMS OTP sign-in flows.
"""

from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db

def test_google_sign_in_flow(db_conn):
    """Verify Google OAuth sign-in / automatic account creation."""
    app.dependency_overrides[get_db] = lambda: db_conn
    try:
        with TestClient(app) as client:
            # 1. Sign in with a new Google Account
            res = client.post(
                "/api/users/auth/google",
                json={
                    "email": "sarah.connor@stanford.edu",
                    "name": "Sarah Connor",
                    "avatar_url": "https://example.com/avatar.jpg",
                    "dorm": "Roble Hall",
                    "token": "google_token_123",
                },
            )
            assert res.status_code == 200, res.text
            user = res.json()
            assert user["email"] == "sarah.connor@stanford.edu"
            assert user["name"] == "Sarah Connor"
            assert user["auth_provider"] == "google"
            user_id = user["id"]

            # 2. Re-authenticating with same Google email updates/returns existing user
            res2 = client.post(
                "/api/users/auth/google",
                json={
                    "email": "sarah.connor@stanford.edu",
                    "name": "Sarah Connor (Updated)",
                    "avatar_url": "https://example.com/avatar2.jpg",
                },
            )
            assert res2.status_code == 200
            user2 = res2.json()
            assert user2["id"] == user_id
            assert user2["name"] == "Sarah Connor (Updated)"
    finally:
        app.dependency_overrides.clear()

def test_phone_otp_sign_in_flow(db_conn):
    """Verify Phone number OTP dispatch and verification flow."""
    app.dependency_overrides[get_db] = lambda: db_conn
    try:
        with TestClient(app) as client:
            test_phone = "+15559876543"

            # 1. Request SMS OTP
            res_otp = client.post(
                "/api/users/auth/phone/send-otp",
                json={"phone": test_phone},
            )
            assert res_otp.status_code == 200
            data_otp = res_otp.json()
            assert data_otp["success"] is True
            assert data_otp["demo_otp"] == "123456"

            # 2. Fail verification with wrong OTP code
            res_fail = client.post(
                "/api/users/auth/phone/verify-otp",
                json={"phone": test_phone, "otp": "999999"},
            )
            assert res_fail.status_code == 400

            # 3. Succeed verification with correct OTP code (123456)
            res_verify = client.post(
                "/api/users/auth/phone/verify-otp",
                json={
                    "phone": test_phone,
                    "otp": "123456",
                    "name": "David Miller",
                    "dorm": "Larkin Hall",
                },
            )
            assert res_verify.status_code == 200, res_verify.text
            phone_user = res_verify.json()
            assert phone_user["phone"] == test_phone
            assert phone_user["name"] == "David Miller"
            assert phone_user["auth_provider"] == "phone"
            phone_user_id = phone_user["id"]

            # 4. Subsequent sign-in with same phone number retrieves existing user
            res_subsequent = client.post(
                "/api/users/auth/phone/verify-otp",
                json={"phone": test_phone, "otp": "123456"},
            )
            assert res_subsequent.status_code == 200
            assert res_subsequent.json()["id"] == phone_user_id
    finally:
        app.dependency_overrides.clear()
