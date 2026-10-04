"""
Need-based matching and bundle generator HTTP router.
Transforms user intent into structured equipment packages with inventory availability checks.
"""

import sqlite3
from fastapi import APIRouter, Depends
from app.database import get_db
from app.schemas import NeedMatchResponse, NeedQueryRequest
from app.services.matching import resolve_need_bundle


router = APIRouter(prefix="/api/matching", tags=["Matching"])


@router.post("/bundle", response_model=NeedMatchResponse)
def get_equipment_bundle(payload: NeedQueryRequest, db: sqlite3.Connection = Depends(get_db)):
    """
    Analyzes student intention, extracts required tool tags, and generates an equipment bundle
    along with real-time inventory matching and missing item alerts.
    """
    return resolve_need_bundle(db, payload.query)
