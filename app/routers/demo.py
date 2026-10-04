"""
Demo-Only Inspection and Tampering HTTP router.
Used exclusively during hackathon presentations to demonstrate cryptographic integrity verification.
"""

import json
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status
from app.database import get_db
from app.config import DEMO_MODE
import sys

router = APIRouter(prefix="/api/demo", tags=["Demo Tools (Hackathon Verification Only)"])


@router.post("/tamper/{event_id}")
def tamper_passport_event(
    event_id: int,
    db: sqlite3.Connection = Depends(get_db),
):
    """
    [DEMO ONLY - FOR LIVE PRESENTATIONS]
    Simulates malicious database alteration by editing an event's recorded condition/details
    without recomputing the cryptographic hash.
    When /items/{id}/passport is called after this, the mathematical verification detects
    the broken hash link and pinpoints the exact sequence number.
    """
    if not DEMO_MODE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode is disabled.")
    
    cursor = db.cursor()
    cursor.execute("SELECT * FROM passport_events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Passport event with ID {event_id} not found.",
        )

    # Inject tampered payload into database
    tampered_details = json.dumps({
        "TAMPERED_FLAG": True,
        "tamper_note": "Simulated unauthorized direct SQL alteration during live demo",
        "original_action": event["event_type"],
    })

    cursor.execute(
        "UPDATE passport_events SET details = ? WHERE id = ?",
        (tampered_details, event_id),
    )

    return {
        "status": "tampered",
        "event_id": event_id,
        "item_id": event["item_id"],
        "seq": event["seq"],
        "message": (
            f"[DEMO SIMULATION] Event #{event['seq']} (ID {event_id}) details were directly modified in SQLite. "
            f"Now re-verify the Item Passport for Item #{event['item_id']} to see the cryptographic alert!"
        ),
    }

@router.post("/reset")
def reset_demo_database(db: sqlite3.Connection = Depends(get_db)):
    """Resets the database to fresh seeded state. Demo only."""
    if not DEMO_MODE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode is disabled.")
    import subprocess
    subprocess.run([sys.executable, "seed.py"], check=True)
    return {"message": "Database reset to demo state.", "success": True}
