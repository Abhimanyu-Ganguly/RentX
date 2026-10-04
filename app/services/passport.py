"""
Item Passport service.
Implements cryptographically verifiable item identity and an append-only SHA-256 hash chain.
No blockchain node is required: verification is pure mathematical recomputation of hash links.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional


GENESIS_PREV_HASH: str = "0" * 64


def hash_bytes(data: bytes) -> str:
    """
    Computes a SHA-256 hex digest for arbitrary byte content (such as an uploaded image).
    """
    return hashlib.sha256(data).hexdigest()


def compute_item_hash(photo_hash: str, serial: str, title: str) -> str:
    """
    Computes a composite SHA-256 hash identifying the specific physical asset.
    Combines the visual fingerprint (photo_hash), hardware identity (serial), and asset title.
    """
    combined = f"{photo_hash}{serial}{title}".encode("utf-8")
    return hashlib.sha256(combined).hexdigest()


def compute_event_hash(
    prev_hash: str,
    item_id: int,
    seq: int,
    event_type: str,
    actor_id: int,
    details: dict[str, Any],
    timestamp: str,
) -> str:
    """
    Computes SHA-256 hash over a canonical JSON array representing the event payload:
    [prev_hash, item_id, seq, event_type, actor_id, details, timestamp]
    Canonical JSON formatting (sorted keys, no extra whitespace) ensures determinism.
    """
    payload = [
        prev_hash,
        item_id,
        seq,
        event_type,
        actor_id,
        details,
        timestamp,
    ]
    # sort_keys=True and separators=(',', ':') ensure identical JSON string across platforms
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def append_event(
    conn: sqlite3.Connection,
    item_id: int,
    event_type: str,
    actor_id: int,
    details: dict[str, Any],
    timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """
    Appends a new verified event block to an item's passport chain.
    Runs inside the caller's transaction so sequence numbers and hash links never fork.
    """
    if timestamp is None:
        # datetime.now(timezone.utc) replaces deprecated datetime.utcnow()
        timestamp = datetime.now(timezone.utc).isoformat()

    # Find the current highest sequence number and latest hash for this specific item
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT seq, event_hash
        FROM passport_events
        WHERE item_id = ?
        ORDER BY seq DESC
        LIMIT 1
        """,
        (item_id,),
    )
    latest_event = cursor.fetchone()

    if latest_event is None:
        # This is the genesis event (seq 1) for a newly registered asset
        seq = 1
        prev_hash = GENESIS_PREV_HASH
    else:
        seq = latest_event["seq"] + 1
        prev_hash = latest_event["event_hash"]

    # Calculate the cryptographic digest for this event
    event_hash = compute_event_hash(
        prev_hash=prev_hash,
        item_id=item_id,
        seq=seq,
        event_type=event_type,
        actor_id=actor_id,
        details=details,
        timestamp=timestamp,
    )

    details_json = json.dumps(details, sort_keys=True)

    cursor.execute(
        """
        INSERT INTO passport_events (
            item_id, seq, prev_hash, event_type, actor_id, details, timestamp, event_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (item_id, seq, prev_hash, event_type, actor_id, details_json, timestamp, event_hash),
    )

    return {
        "id": cursor.lastrowid,
        "item_id": item_id,
        "seq": seq,
        "prev_hash": prev_hash,
        "event_type": event_type,
        "actor_id": actor_id,
        "details": details,
        "timestamp": timestamp,
        "event_hash": event_hash,
    }


def verify_chain(conn: sqlite3.Connection, item_id: int) -> tuple[bool, Optional[int], list[dict[str, Any]]]:
    """
    Recomputes and verifies the complete cryptographic hash chain for an item.
    Returns:
      (is_valid: bool, broken_at_seq: int | None, events_list: list[dict])
    If any event content, prev_hash link, or sequence order has been tampered with,
    verification fails and immediately reports the exact sequence number where the chain broke.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pe.id, pe.item_id, pe.seq, pe.prev_hash, pe.event_type, pe.actor_id,
               pe.details, pe.timestamp, pe.event_hash, u.name as actor_name
        FROM passport_events pe
        LEFT JOIN users u ON pe.actor_id = u.id
        WHERE pe.item_id = ?
        ORDER BY pe.seq ASC
        """,
        (item_id,),
    )
    rows = cursor.fetchall()

    if not rows:
        return True, None, []

    events: list[dict[str, Any]] = []
    expected_prev_hash = GENESIS_PREV_HASH

    for expected_seq, row in enumerate(rows, start=1):
        raw_details = row["details"]
        try:
            details_dict = json.loads(raw_details) if isinstance(raw_details, str) else raw_details
        except Exception:
            details_dict = {"raw": raw_details}

        event_data = {
            "id": row["id"],
            "item_id": row["item_id"],
            "seq": row["seq"],
            "prev_hash": row["prev_hash"],
            "event_type": row["event_type"],
            "actor_id": row["actor_id"],
            "actor_name": row["actor_name"] or f"User #{row['actor_id']}",
            "details": details_dict,
            "timestamp": row["timestamp"],
            "event_hash": row["event_hash"],
        }
        events.append(event_data)

        # 1. Check sequence monotonicity
        if row["seq"] != expected_seq:
            return False, row["seq"], events

        # 2. Check parent hash linkage
        if row["prev_hash"] != expected_prev_hash:
            return False, row["seq"], events

        # 3. Recompute SHA-256 over exact canonical event payload
        recomputed_hash = compute_event_hash(
            prev_hash=row["prev_hash"],
            item_id=row["item_id"],
            seq=row["seq"],
            event_type=row["event_type"],
            actor_id=row["actor_id"],
            details=details_dict,
            timestamp=row["timestamp"],
        )

        if recomputed_hash != row["event_hash"]:
            return False, row["seq"], events

        # Next block must point to this block's hash
        expected_prev_hash = row["event_hash"]

    return True, None, events
