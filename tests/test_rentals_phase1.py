'''Phase 1 Rental tests: creation, owner accept, owner reject, validation edge cases.'''
import json
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db

def test_rental_reject_flow(db_conn):
    """Create a rental request and have the owner reject it.
    Verify status transition, item availability, and passport event.
    """
    # Override DB dependency with the provided test connection
    app.dependency_overrides[get_db] = lambda: db_conn
    try:
        with TestClient(app) as client:
            # Create owner and renter users
            owner_res = client.post(
                "/api/users",
                json={"name": "Owner", "email": "owner@test.com", "dorm": "A", "avatar_url": ""},
            )
            assert owner_res.status_code == 201
            owner_id = owner_res.json()["id"]

            renter_res = client.post(
                "/api/users",
                json={"name": "Renter", "email": "renter@test.com", "dorm": "B", "avatar_url": ""},
            )
            assert renter_res.status_code == 201
            renter_id = renter_res.json()["id"]

            # Owner lists an item (available = true)
            checklist = {"clean": "yes", "power": "ok"}
            item_payload = {
                "title": "Test Camera",
                "category": "camera gear",
                "description": "A test camera",
                "value": "200.0",
                "price_per_day": "10.0",
                "deposit_amount": "50.0",
                "serial": "CAM-001",
                "tags": "test,camera",
                "mode": "personal",
                "condition_checklist": json.dumps(checklist),
            }
            item_res = client.post(
                "/api/items",
                data=item_payload,
                headers={"X-User-Id": str(owner_id)},
            )
            assert item_res.status_code == 201
            item = item_res.json()
            item_id = item["id"]
            assert item["available"] is True

            # Renter creates a rental request for 2 days
            rent_res = client.post(
                "/api/rentals",
                json={"item_id": item_id, "start_date": "2030-10-01", "end_date": "2030-10-02", "days": 2},
                headers={"X-User-Id": str(renter_id)},
            )
            assert rent_res.status_code == 201
            rental = rent_res.json()
            rental_id = rental["id"]
            assert rental["booking_status"] == "pending"

            # Owner rejects the request
            reject_res = client.post(
                f"/api/rentals/{rental_id}/reject",
                headers={"X-User-Id": str(owner_id)},
            )
            assert reject_res.status_code == 200
            rejected = reject_res.json()
            assert rejected["booking_status"] == "rejected"

            # Item should remain available
            item_check = client.get(f"/api/items/{item_id}")
            assert item_check.status_code == 200
            assert item_check.json()["available"] is True

            # Passport should contain a "booking_rejected" event
            passport_res = client.get(f"/api/items/{item_id}/passport")
            assert passport_res.status_code == 200
            passport = passport_res.json()
            event_types = [e["event_type"] for e in passport["events"]]
            assert "booking_rejected" in event_types
    finally:
        app.dependency_overrides.clear()

def test_rental_reject_invalid_owner(db_conn):
    """Attempt to reject a rental as a non‑owner; expect HTTP 403 error."""
    app.dependency_overrides[get_db] = lambda: db_conn
    try:
        with TestClient(app) as client:
            # Create two users
            u1 = client.post("/api/users", json={"name": "User1", "email": "u1@test.com", "dorm": "A", "avatar_url": ""}).json()
            u2 = client.post("/api/users", json={"name": "User2", "email": "u2@test.com", "dorm": "B", "avatar_url": ""}).json()
            # Owner (u1) lists item
            checklist = {"c": "ok"}
            item_res = client.post(
                "/api/items",
                data={
                    "title": "Item", "category": "other", "description": "desc", "value": "10", "price_per_day": "1", "deposit_amount": "5", "serial": "S1", "tags": "t", "mode": "personal", "condition_checklist": json.dumps(checklist),
                },
                headers={"X-User-Id": str(u1["id"])},
            )
            item_id = item_res.json()["id"]
            # Renter (u2) requests rental
            rent_res = client.post(
                "/api/rentals",
                json={"item_id": item_id, "start_date": "2030-10-01", "end_date": "2030-10-01", "days": 1},
                headers={"X-User-Id": str(u2["id"])},
            )
            rental_id = rent_res.json()["id"]
            # Attempt reject by u2 (not the owner)
            bad_reject = client.post(
                f"/api/rentals/{rental_id}/reject",
                headers={"X-User-Id": str(u2["id"])},
            )
            assert bad_reject.status_code == 403
    finally:
        app.dependency_overrides.clear()

def test_rental_accept_conflict(db_conn):
    """Owner accepts a rental, then another overlapping request cannot be accepted."""
    app.dependency_overrides[get_db] = lambda: db_conn
    try:
        with TestClient(app) as client:
            # Users
            owner = client.post("/api/users", json={"name": "Owner", "email": "o@test.com", "dorm": "A", "avatar_url": ""}).json()
            renter1 = client.post("/api/users", json={"name": "Renter1", "email": "r1@test.com", "dorm": "B", "avatar_url": ""}).json()
            renter2 = client.post("/api/users", json={"name": "Renter2", "email": "r2@test.com", "dorm": "C", "avatar_url": ""}).json()
            # Item
            checklist = {"ok": "yes"}
            item_res = client.post(
                "/api/items",
                data={
                    "title": "Bike", "category": "sports", "description": "bike", "value": "100", "price_per_day": "5", "deposit_amount": "20", "serial": "B1", "tags": "bike", "mode": "personal", "condition_checklist": json.dumps(checklist),
                },
                headers={"X-User-Id": str(owner["id"])},
            )
            item_id = item_res.json()["id"]
            # Renter1 request
            r1 = client.post(
                "/api/rentals",
                json={"item_id": item_id, "start_date": "2030-10-01", "end_date": "2030-10-03", "days": 3},
                headers={"X-User-Id": str(renter1["id"])},
            ).json()
            # Renter2 makes overlapping request (same item, same period) BEFORE owner accepts R1
            r2 = client.post(
                "/api/rentals",
                json={"item_id": item_id, "start_date": "2030-10-01", "end_date": "2030-10-03", "days": 3},
                headers={"X-User-Id": str(renter2["id"])},
            ).json()
            # Owner accepts Renter1
            accept1 = client.post(f"/api/rentals/{r1['id']}/accept", headers={"X-User-Id": str(owner["id"])})
            assert accept1.status_code == 200
            # Owner attempts to accept overlapping request -> should fail with 409
            accept2 = client.post(f"/api/rentals/{r2['id']}/accept", headers={"X-User-Id": str(owner["id"])})
            assert accept2.status_code == 409
    finally:
        app.dependency_overrides.clear()
