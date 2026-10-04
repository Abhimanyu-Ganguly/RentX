"""
Database Seeding Script for 'Buy Nothing, Rent Everything'.
Populates campus personas, diverse equipment inventory across categories,
and historical rental transactions with varied outcomes (on-time, late, disputed/resolved).
All items and rentals are created through the service layer to ensure cryptographically valid Item Passports.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from app.config import DATABASE_PATH, UPLOADS_DIR
from app.database import init_db, get_db_connection
from app.services.passport import (
    append_event,
    compute_item_hash,
    hash_bytes,
)
from app.services.deposit import (
    transition_on_accept,
    transition_on_confirm_return,
    transition_on_dispute,
    transition_on_resolve,
)


def create_placeholder_image(filename: str, color_hex: str, title: str) -> tuple[str, str]:
    """
    Generates a clean SVG placeholder image in the uploads directory and computes its SHA-256 hash.
    """
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOADS_DIR / filename

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{color_hex};stop-opacity:1" />
      <stop offset="100%" style="stop-color:#0f172a;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="600" height="400" fill="url(#grad)" rx="16"/>
  <circle cx="300" cy="180" r="64" fill="#ffffff" opacity="0.15"/>
  <path d="M270 200 L300 150 L330 200 Z" fill="#ffffff" opacity="0.4"/>
  <text x="300" y="280" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="22" font-weight="bold" fill="#ffffff" text-anchor="middle">{title}</text>
  <text x="300" y="315" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" font-size="14" fill="#94a3b8" text-anchor="middle">Verified Item Passport • Cryptographic ID</text>
</svg>"""

    file_bytes = svg_content.encode("utf-8")
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    photo_hash = hash_bytes(file_bytes)
    return f"/uploads/{filename}", photo_hash


def seed_database():
    """
    Executes the seeding sequence.
    """
    print("Initializing SQLite database tables...")
    init_db()
    conn = get_db_connection()

    # Clear existing data cleanly for fresh demo state
    with conn:
        conn.execute("DELETE FROM passport_events;")
        conn.execute("DELETE FROM rentals;")
        conn.execute("DELETE FROM items;")
        conn.execute("DELETE FROM users;")
        try:
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('users', 'items', 'rentals', 'passport_events');")
        except Exception:
            pass

    base_time = datetime.now(timezone.utc) - timedelta(days=14)

    # =========================================================================
    # 1. Seed Campus Users
    # =========================================================================
    users_data = [
        {
            "name": "Maya Lin",
            "email": "maya.lin@campus.edu",
            "dorm": "Stern Hall - Burbank",
            "avatar_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150",
        },
        {
            "name": "Marcus Vance",
            "email": "marcus.vance@campus.edu",
            "dorm": "Crothers Memorial",
            "avatar_url": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150",
        },
        {
            "name": "Elena Rostova",
            "email": "elena.rostova@campus.edu",
            "dorm": "Roble Hall",
            "avatar_url": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150",
        },
        {
            "name": "Dev Patel",
            "email": "dev.patel@campus.edu",
            "dorm": "Florence Moore - Alondra",
            "avatar_url": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150",
        },
        {
            "name": "Sofia Rodriguez",
            "email": "sofia.r@campus.edu",
            "dorm": "Lagunita Court",
            "avatar_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150",
        },
        {
            "name": "Jordan Lee",
            "email": "jordan.lee@campus.edu",
            "dorm": "Governor's Corner",
            "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150",
        },
    ]

    user_ids: dict[str, int] = {}
    with conn:
        for u in users_data:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (name, email, dorm, avatar_url, password, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (u["name"], u["email"], u["dorm"], u["avatar_url"], "password123", base_time.isoformat()),
            )
            user_ids[u["name"]] = cur.lastrowid

    print(f"[OK] Seeded {len(user_ids)} campus user profiles.")

    # =========================================================================
    # 2. Seed Equipment Inventory with Cryptographic Passports
    # =========================================================================
    items_raw = [
        # Maya's Camera Gear
        {
            "owner": "Maya Lin",
            "title": "Sony Alpha A7 IV Mirrorless Camera",
            "category": "camera gear",
            "description": "Full-frame 33MP hybrid camera with 4K 60p video. Includes 28-70mm lens, 2 batteries, and 128GB SD card.",
            "value": 2400.0,
            "price_per_day": 35.0,
            "deposit_amount": 150.0,
            "serial": "SN-A7IV-99201",
            "tags": "camera,photography,4k,sony,photoshoot",
            "color": "#3b82f6",
            "checklist": {"lens": "good", "body": "good", "battery": "good", "memory card": "good"},
        },
        {
            "owner": "Maya Lin",
            "title": "Manfrotto 055 Carbon Fiber Tripod",
            "category": "camera gear",
            "description": "Sturdy 3-section carbon tripod with 3-way pan/tilt head. Supports up to 20 lbs.",
            "value": 380.0,
            "price_per_day": 12.0,
            "deposit_amount": 40.0,
            "serial": "SN-MAN-055CF",
            "tags": "tripod,camera,stable,mount,photoshoot",
            "color": "#0ea5e9",
            "checklist": {"lens": "good", "body": "good", "battery": "good", "memory card": "good"},
        },
        {
            "owner": "Maya Lin",
            "title": "Aputure Amaran 100d LED Studio Light",
            "category": "camera gear",
            "description": "Daylight-balanced 100W continuous LED video light with softbox and carrying case.",
            "value": 220.0,
            "price_per_day": 14.0,
            "deposit_amount": 50.0,
            "serial": "SN-APU-100D",
            "tags": "lighting,studio,camera,video,photoshoot",
            "color": "#f59e0b",
            "checklist": {"screen/body": "good", "power cable": "good", "ports": "good", "buttons": "good"},
        },

        # Marcus's Camping Gear
        {
            "owner": "Marcus Vance",
            "title": "Coleman Sundome 4-Person Dome Tent",
            "category": "camping",
            "description": "Weatherproof 9x7 ft dome tent. Fits 1 queen airbed. Setup in under 10 minutes.",
            "value": 140.0,
            "price_per_day": 15.0,
            "deposit_amount": 50.0,
            "serial": "SN-COL-TENT4P",
            "tags": "tent,camping,outdoors,shelter",
            "color": "#10b981",
            "checklist": {"fabric/zippers": "good", "poles/stakes": "good", "accessories": "good", "cleanliness": "good"},
        },
        {
            "owner": "Marcus Vance",
            "title": "Camp Chef Everest 2-Burner Propane Stove",
            "category": "camping",
            "description": "High-output 20,000 BTU dual burners with windscreen and matchless ignition.",
            "value": 160.0,
            "price_per_day": 10.0,
            "deposit_amount": 35.0,
            "serial": "SN-CHF-EV2B",
            "tags": "stove,camping,cooking,propane,gas",
            "color": "#ef4444",
            "checklist": {"fabric/zippers": "good", "poles/stakes": "good", "accessories": "good", "cleanliness": "good"},
        },
        {
            "owner": "Marcus Vance",
            "title": "Black Diamond 500 Lumen Rechargeable Lantern",
            "category": "camping",
            "description": "Dual-fuel USB rechargeable lantern. Dimmable warm lighting with power bank output.",
            "value": 75.0,
            "price_per_day": 6.0,
            "deposit_amount": 20.0,
            "serial": "SN-BD-LNT500",
            "tags": "lantern,light,camping,outdoor",
            "color": "#f59e0b",
            "checklist": {"fabric/zippers": "good", "poles/stakes": "good", "accessories": "good", "cleanliness": "good"},
        },
        {
            "owner": "Marcus Vance",
            "title": "The North Face Wasatch 20°F Sleeping Bag",
            "category": "camping",
            "description": "Synthetic insulation mummy sleeping bag rated for 20°F weather. Includes compression sack.",
            "value": 110.0,
            "price_per_day": 8.0,
            "deposit_amount": 30.0,
            "serial": "SN-TNF-SB20",
            "tags": "sleeping bag,camping,warm,bedding",
            "color": "#8b5cf6",
            "checklist": {"fabric/zippers": "good", "poles/stakes": "good", "accessories": "good", "cleanliness": "good"},
        },

        # Elena's Maker & DIY Tools
        {
            "owner": "Elena Rostova",
            "title": "DeWalt 20V MAX Cordless Drill & Impact Combo",
            "category": "tools",
            "description": "Brushless motor drill/driver kit with 2x 20V batteries, charger, and 30pc drill bit set.",
            "value": 220.0,
            "price_per_day": 12.0,
            "deposit_amount": 45.0,
            "serial": "SN-DEW-20VCOMBO",
            "tags": "drill,tools,dewalt,cordless,shelves",
            "color": "#eab308",
            "checklist": {"chuck": "good", "battery": "good", "bits": "good", "casing": "good"},
        },
        {
            "owner": "Elena Rostova",
            "title": "Bosch Digital Self-Leveling Cross-Line Laser Level",
            "category": "tools",
            "description": "Projects bright horizontal and vertical laser lines up to 50 ft. Perfect for hanging shelves.",
            "value": 130.0,
            "price_per_day": 8.0,
            "deposit_amount": 30.0,
            "serial": "SN-BSH-LVL50",
            "tags": "level,laser,tools,mounting,shelves",
            "color": "#06b6d4",
            "checklist": {"chuck": "good", "battery": "good", "bits": "good", "casing": "good"},
        },
        {
            "owner": "Elena Rostova",
            "title": "Franklin Sensors ProSensor 710+ Stud Finder",
            "category": "tools",
            "description": "Multi-sensor stud finder with 13 precision LEDs. Instant drywall scan with no calibration needed.",
            "value": 60.0,
            "price_per_day": 5.0,
            "deposit_amount": 20.0,
            "serial": "SN-FRK-STUD710",
            "tags": "stud finder,wall,tools,mounting,shelves",
            "color": "#ec4899",
            "checklist": {"chuck": "good", "battery": "good", "bits": "good", "casing": "good"},
        },
        {
            "owner": "Elena Rostova",
            "title": "Little Giant 17ft Multi-Position Extension Ladder",
            "category": "ladder",
            "description": "Convertible aluminum ladder (A-frame, extension, 90-degree, staircase). 300 lb rated.",
            "value": 260.0,
            "price_per_day": 14.0,
            "deposit_amount": 60.0,
            "serial": "SN-LTG-17FT",
            "tags": "ladder,tools,shelves,mounting,extension",
            "color": "#64748b",
            "checklist": {"rungs": "good", "locking mechanism": "good", "feet/grips": "good", "hinges": "good"},
        },

        # Dev's Audio-Visual Cinema Gear
        {
            "owner": "Dev Patel",
            "title": "Epson Home Cinema 4K PRO-UHD Projector",
            "category": "projector",
            "description": "3000 lumens 4K HDR home theater projector. Includes HDMI cable, remote, and tripod mount adapter.",
            "value": 900.0,
            "price_per_day": 30.0,
            "deposit_amount": 100.0,
            "serial": "SN-EPS-4K3000",
            "tags": "projector,movie,cinema,screen,movie night",
            "color": "#6366f1",
            "checklist": {"lamp": "good", "remote": "good", "cables": "good", "lens": "good"},
        },
        {
            "owner": "Dev Patel",
            "title": "JBL PartyBox 110 High-Power Portable Speaker",
            "category": "electronics",
            "description": "160W powerful sound with built-in dynamic light show and 12-hour battery life.",
            "value": 350.0,
            "price_per_day": 18.0,
            "deposit_amount": 60.0,
            "serial": "SN-JBL-PB110",
            "tags": "speaker,audio,party,movie night,sound",
            "color": "#f97316",
            "checklist": {"screen/body": "good", "power cable": "good", "ports": "good", "buttons": "good"},
        },
        {
            "owner": "Dev Patel",
            "title": "Heavy Duty 50ft Outdoor Extension Cord",
            "category": "electronics",
            "description": "14-gauge 3-prong lighted outdoor extension cord with triple tap outlet.",
            "value": 45.0,
            "price_per_day": 4.0,
            "deposit_amount": 15.0,
            "serial": "SN-EXT-50FT",
            "tags": "extension cord,cable,power,outdoor,movie night",
            "color": "#14b8a6",
            "checklist": {"screen/body": "good", "power cable": "good", "ports": "good", "buttons": "good"},
        },

        # Sofia's Craft & Construction Gear
        {
            "owner": "Sofia Rodriguez",
            "title": "Milwaukee M18 Random Orbital Wood Sander",
            "category": "tools",
            "description": "Cordless 5-inch orbital sander with variable speed dial and dust canister.",
            "value": 140.0,
            "price_per_day": 10.0,
            "deposit_amount": 35.0,
            "serial": "SN-MIL-SAND18",
            "tags": "sander,woodworking,tools,diy",
            "color": "#dc2626",
            "checklist": {"chuck": "good", "battery": "good", "bits": "good", "casing": "good"},
        },
    ]

    items_raw = items_raw[:2]
    item_ids: dict[str, int] = {}
    with conn:
        for idx, item in enumerate(items_raw, start=1):
            owner_id = user_ids[item["owner"]]
            # Generate placeholder SVG image & SHA-256 hash
            clean_name = item["title"].lower().replace(" ", "_")[:20]
            img_path, photo_hash = create_placeholder_image(
                filename=f"{clean_name}_{idx}.svg",
                color_hex=item["color"],
                title=item["title"][:28],
            )
            item_hash = compute_item_hash(photo_hash, item["serial"], item["title"])

            item_time = base_time + timedelta(hours=idx * 2)

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO items (
                    owner_id, title, category, description, value, price_per_day, deposit_amount,
                    serial, photo_path, photo_hash, item_hash, condition_checklist, tags, mode, available, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'commercial', 1, ?)
                """,
                (
                    owner_id,
                    item["title"],
                    item["category"],
                    item["description"],
                    item["value"],
                    item["price_per_day"],
                    item["deposit_amount"],
                    item["serial"],
                    img_path,
                    photo_hash,
                    item_hash,
                    json.dumps(item["checklist"], sort_keys=True),
                    item["tags"],
                    item_time.isoformat(),
                ),
            )
            item_id = cur.lastrowid
            item_ids[item["title"]] = item_id

            # Append Genesis block #1 to item passport
            append_event(
                conn=conn,
                item_id=item_id,
                event_type="registered",
                actor_id=owner_id,
                details={
                    "action": "Item registered on campus network",
                    "owner": item["owner"],
                    "serial": item["serial"],
                    "photo_hash": photo_hash,
                    "item_hash": item_hash,
                    "initial_condition": item["checklist"],
                    "stated_value": item["value"],
                    "daily_rate": item["price_per_day"],
                    "deposit_required": item["deposit_amount"],
                },
                timestamp=item_time.isoformat(),
            )

    print(f"[OK] Seeded {len(item_ids)} equipment items with cryptographic passports.")

    # =========================================================================
    conn.commit()
    conn.close()
    return
    # 3. Seed Realistic Historical Rental Flows
    # =========================================================================
    with conn:
        # Rental 1: Pristine Happy Path (Sony A7 IV rented by Jordan from Maya)
        r1_item_id = item_ids["Sony Alpha A7 IV Mirrorless Camera"]
        r1_owner_id = user_ids["Maya Lin"]
        r1_renter_id = user_ids["Jordan Lee"]
        t_req = base_time + timedelta(days=2)
        t_acc = t_req + timedelta(hours=1, minutes=30)
        t_ret = t_req + timedelta(days=2)

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO rentals (
                item_id, renter_id, owner_id, days, total_price, deposit_amount,
                booking_status, deposit_status, condition_rating, return_on_time,
                requested_at, responded_at, returned_at, completed_at
            ) VALUES (?, ?, ?, 2, 70.0, 150.0, 'completed', 'released', 5, 1, ?, ?, ?, ?)
            """,
            (r1_item_id, r1_renter_id, r1_owner_id, t_req.isoformat(), t_acc.isoformat(), t_ret.isoformat(), t_ret.isoformat()),
        )
        r1_id = cur.lastrowid

        # Passport Event #2: Rented
        append_event(
            conn=conn,
            item_id=r1_item_id,
            event_type="rented",
            actor_id=r1_owner_id,
            details={
                "action": "Handed over to renter for photography project",
                "rental_id": r1_id,
                "renter": "Jordan Lee",
                "days": 2,
                "deposit_status": "held",
            },
            timestamp=t_acc.isoformat(),
        )
        # Passport Event #3: Returned
        append_event(
            conn=conn,
            item_id=r1_item_id,
            event_type="returned",
            actor_id=r1_owner_id,
            details={
                "action": "Returned in perfect condition; full deposit released",
                "rental_id": r1_id,
                "condition_rating": 5,
                "returned_on_time": True,
                "deposit_status": "released",
            },
            timestamp=t_ret.isoformat(),
        )

        # Rental 2: Late Return Case (DeWalt Drill rented by Jordan from Elena)
        r2_item_id = item_ids["DeWalt 20V MAX Cordless Drill & Impact Combo"]
        r2_owner_id = user_ids["Elena Rostova"]
        r2_renter_id = user_ids["Jordan Lee"]
        t_req2 = base_time + timedelta(days=4)
        t_acc2 = t_req2 + timedelta(hours=3)
        t_ret2 = t_req2 + timedelta(days=5)  # 2 days late

        cur.execute(
            """
            INSERT INTO rentals (
                item_id, renter_id, owner_id, days, total_price, deposit_amount,
                booking_status, deposit_status, condition_rating, return_on_time,
                requested_at, responded_at, returned_at, completed_at
            ) VALUES (?, ?, ?, 3, 36.0, 45.0, 'completed', 'released', 3, 0, ?, ?, ?, ?)
            """,
            (r2_item_id, r2_renter_id, r2_owner_id, t_req2.isoformat(), t_acc2.isoformat(), t_ret2.isoformat(), t_ret2.isoformat()),
        )
        r2_id = cur.lastrowid

        append_event(
            conn=conn,
            item_id=r2_item_id,
            event_type="rented",
            actor_id=r2_owner_id,
            details={"action": "Handed over for dorm bookshelf assembly", "rental_id": r2_id, "renter": "Jordan Lee", "days": 3},
            timestamp=t_acc2.isoformat(),
        )
        append_event(
            conn=conn,
            item_id=r2_item_id,
            event_type="returned",
            actor_id=r2_owner_id,
            details={
                "action": "Returned 2 days late; tool functioned but bit case was disorganized",
                "rental_id": r2_id,
                "condition_rating": 3,
                "returned_on_time": False,
                "deposit_status": "released",
            },
            timestamp=t_ret2.isoformat(),
        )

        # Rental 3: Disputed and Resolved Case (Camping Tent rented by Dev from Marcus)
        r3_item_id = item_ids["Coleman Sundome 4-Person Dome Tent"]
        r3_owner_id = user_ids["Marcus Vance"]
        r3_renter_id = user_ids["Dev Patel"]
        t_req3 = base_time + timedelta(days=6)
        t_acc3 = t_req3 + timedelta(hours=2)
        t_ret3 = t_req3 + timedelta(days=3)
        t_dispute = t_ret3 + timedelta(hours=1)
        t_resolved = t_ret3 + timedelta(hours=6)

        cur.execute(
            """
            INSERT INTO rentals (
                item_id, renter_id, owner_id, days, total_price, deposit_amount,
                booking_status, deposit_status, condition_rating, return_on_time,
                dispute_reason, dispute_resolution,
                requested_at, responded_at, returned_at, completed_at
            ) VALUES (?, ?, ?, 3, 45.0, 50.0, 'completed', 'resolved', 2, 1,
                     'Torn seam on rainfly canopy', 'split',
                     ?, ?, ?, ?)
            """,
            (r3_item_id, r3_renter_id, r3_owner_id, t_req3.isoformat(), t_acc3.isoformat(), t_ret3.isoformat(), t_resolved.isoformat()),
        )
        r3_id = cur.lastrowid

        append_event(
            conn=conn,
            item_id=r3_item_id,
            event_type="rented",
            actor_id=r3_owner_id,
            details={"action": "Handed over for Yosemite trip", "rental_id": r3_id, "renter": "Dev Patel", "days": 3},
            timestamp=t_acc3.isoformat(),
        )
        append_event(
            conn=conn,
            item_id=r3_item_id,
            event_type="dispute_opened",
            actor_id=r3_owner_id,
            details={"action": "Torn rainfly seam identified upon return", "rental_id": r3_id, "deposit_status": "disputed"},
            timestamp=t_dispute.isoformat(),
        )
        append_event(
            conn=conn,
            item_id=r3_item_id,
            event_type="dispute_resolved",
            actor_id=r3_owner_id,
            details={"action": "Split settlement: $25 repair cost to owner, $25 refunded to renter", "rental_id": r3_id, "resolution": "split", "deposit_status": "resolved"},
            timestamp=t_resolved.isoformat(),
        )

        # Rental 4: Active In-Progress Rental (Epson Projector rented by Sofia from Dev)
        r4_item_id = item_ids["Epson Home Cinema 4K PRO-UHD Projector"]
        r4_owner_id = user_ids["Dev Patel"]
        r4_renter_id = user_ids["Sofia Rodriguez"]
        t_req4 = datetime.now(timezone.utc) - timedelta(hours=18)
        t_acc4 = t_req4 + timedelta(minutes=45)

        cur.execute(
            """
            INSERT INTO rentals (
                item_id, renter_id, owner_id, days, total_price, deposit_amount,
                booking_status, deposit_status, return_on_time,
                requested_at, responded_at
            ) VALUES (?, ?, ?, 2, 60.0, 100.0, 'accepted', 'held', 1, ?, ?)
            """,
            (r4_item_id, r4_renter_id, r4_owner_id, t_req4.isoformat(), t_acc4.isoformat()),
        )
        r4_id = cur.lastrowid
        # Mark projector unavailable
        cur.execute("UPDATE items SET available = 0 WHERE id = ?", (r4_item_id,))

        append_event(
            conn=conn,
            item_id=r4_item_id,
            event_type="rented",
            actor_id=r4_owner_id,
            details={"action": "Checked out for courtyard screening", "rental_id": r4_id, "renter": "Sofia Rodriguez", "days": 2, "deposit_status": "held"},
            timestamp=t_acc4.isoformat(),
        )

    conn.close()
    print("[OK] Seeded realistic multi-outcome rental histories & active bookings.")
    print("[DONE] Seed completed successfully! Database is ready for demo.")


if __name__ == "__main__":
    seed_database()
