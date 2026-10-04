"""
End-to-End API Integration Flow Test.
Exercises the entire lifecycle via FastAPI TestClient:
User creation -> Item listing & passport genesis -> Rental request -> Owner acceptance (escrow hold)
-> Renter return -> Owner inspection & rating (escrow release) -> Reputation verification -> Passport audit.
"""

import json
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db

def test_full_marketplace_lifecycle_flow(db_conn):
    """
    Simulates a complete real-world user journey through the API endpoints.
    """
    app.dependency_overrides[get_db] = lambda: db_conn
    try:
        with TestClient(app) as client:
            # 1. Create two test users (Alice and Bob)
            res_alice = client.post(
                "/api/users",
                json={"name": "Alice Wang", "email": "alice.wang.test@campus.edu", "dorm": "Palo Verde", "avatar_url": ""},
            )
            assert res_alice.status_code == 201
            alice = res_alice.json()
            alice_id = alice["id"]

            res_bob = client.post(
                "/api/users",
                json={"name": "Bob Miller", "email": "bob.miller.test@campus.edu", "dorm": "Rains Houses", "avatar_url": ""},
            )
            assert res_bob.status_code == 201
            bob = res_bob.json()
            bob_id = bob["id"]

            # 2. Alice lists a high-end projector (creates genesis passport block #1)
            checklist = {"lamp": "good", "remote": "good", "cables": "good", "lens": "good"}
            item_payload = {
                "title": "Epson 4K Laser Cinema Projector",
                "category": "projector",
                "description": "Ultra bright, 3000 lumens, perfect for movie nights",
                "value": "650.0",
                "price_per_day": "30.0",
                "deposit_amount": "100.0",
                "serial": "EPS-4K-7788",
                "tags": "projector,movie,cinema,4k",
                "mode": "commercial",
                "condition_checklist": json.dumps(checklist),
            }

            res_item = client.post(
                "/api/items",
                data=item_payload,
                headers={"X-User-Id": str(alice_id)},
            )
            assert res_item.status_code == 201
            item = res_item.json()
            item_id = item["id"]
            assert item["available"] is True
            assert len(item["photo_hash"]) == 64
            assert len(item["item_hash"]) == 64

            # Verify initial passport has 1 event (registered) and is valid
            res_passport1 = client.get(f"/api/items/{item_id}/passport")
            assert res_passport1.status_code == 200
            p1 = res_passport1.json()
            assert p1["is_valid"] is True
            assert p1["total_events"] == 1
            assert p1["events"][0]["event_type"] == "registered"

            # 3. Bob requests to rent the projector for 3 days
            res_req = client.post(
                "/api/rentals",
                json={"item_id": item_id, "days": 3},
                headers={"X-User-Id": str(bob_id)},
            )
            assert res_req.status_code == 201
            rental = res_req.json()
            rental_id = rental["id"]
            assert rental["booking_status"] == "requested"
            assert rental["deposit_status"] == "pending"
            assert rental["total_price"] == 90.0
            assert rental["deposit_amount"] == 100.0

            # 4. Alice accepts the booking (deposit state transitions: pending -> held, passport event #2)
            res_accept = client.post(
                f"/api/rentals/{rental_id}/accept",
                headers={"X-User-Id": str(alice_id)},
            )
            assert res_accept.status_code == 200
            accepted_rental = res_accept.json()
            assert accepted_rental["booking_status"] == "accepted"
            assert accepted_rental["deposit_status"] == "held"

            # Item should now be unavailable for others
            res_item_check = client.get(f"/api/items/{item_id}")
            assert res_item_check.json()["available"] is False

            # 5. Bob finishes his movie night and initiates return
            res_return = client.post(
                f"/api/rentals/{rental_id}/return",
                json={"condition_after": checklist, "return_on_time": True},
                headers={"X-User-Id": str(bob_id)},
            )
            assert res_return.status_code == 200
            assert res_return.json()["return_on_time"] is True

            # 6. Alice confirms return, rates Bob 5 stars (deposit state: held -> released, passport event #3)
            res_confirm = client.post(
                f"/api/rentals/{rental_id}/confirm",
                json={"condition_rating": 5, "condition_notes": "Returned in immaculate condition with all cables!"},
                headers={"X-User-Id": str(alice_id)},
            )
            assert res_confirm.status_code == 200
            completed_rental = res_confirm.json()
            assert completed_rental["booking_status"] == "completed"
            assert completed_rental["deposit_status"] == "released"
            assert completed_rental["condition_rating"] == 5

            # Item is available again
            assert client.get(f"/api/items/{item_id}").json()["available"] is True

            # 7. Check Reputation updates
            # Bob (Renter): 100% punctuality, 100% care, 0 disputes
            res_bob_rep = client.get(f"/api/users/{bob_id}/reputation")
            assert res_bob_rep.status_code == 200
            bob_rep = res_bob_rep.json()["renter"]
            assert bob_rep["has_history"] is True
            assert bob_rep["return_punctuality_pct"] == 100.0
            assert bob_rep["item_care_pct"] == 100.0
            assert bob_rep["dispute_count"] == 0
            assert bob_rep["successful_rentals"] == 1

            # Alice (Owner): 100% reliability, 1 completed booking
            res_alice_rep = client.get(f"/api/users/{alice_id}/reputation")
            assert res_alice_rep.status_code == 200
            alice_rep = res_alice_rep.json()["owner"]
            assert alice_rep["has_history"] is True
            assert alice_rep["reliability_pct"] == 100.0

            # 8. Check Passport Hash Chain: 3 events (registered, rented, returned), chain valid
            res_passport2 = client.get(f"/api/items/{item_id}/passport")
            assert res_passport2.status_code == 200
            p2 = res_passport2.json()
            assert p2["is_valid"] is True
            assert p2["total_events"] >= 3
            assert p2["events"][0]["event_type"] == "registered"

            # 9. Test Demo Tampering: Tamper with event #2 and verify passport catches it
            event_2_id = p2["events"][1]["id"]
            res_tamper = client.post(f"/api/demo/tamper/{event_2_id}")
            assert res_tamper.status_code == 200

            # Re-verify passport: must now be INVALID and report broken at seq 2
            res_passport3 = client.get(f"/api/items/{item_id}/passport")
            assert res_passport3.status_code == 200
            p3 = res_passport3.json()
            assert p3["is_valid"] is False
            assert p3["broken_at_seq"] == 2
    finally:
        app.dependency_overrides.clear()
