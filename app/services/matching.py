"""
Need-Based Equipment Bundling Service.

Matches natural student intentions (e.g. "going camping this weekend", "putting up shelves in my room")
to pre-configured equipment requirement bundles, and dynamically resolves inventory availability.
"""

import json
import re
import sqlite3
from typing import Any, Optional
from app.config import NEED_DICTIONARY


# =========================================================================================
# NLP & INTENT EXTRACTION EXTENSION POINT
# -----------------------------------------------------------------------------------------
# In a full-scale deployment, this function can be replaced by:
# 1. Semantic Embedding Search (e.g. text-embedding-004) measuring cosine similarity to need vectors.
# 2. LLM Function Calling (e.g. Gemini Flash) parsing arbitrary requests into required tooling JSON.
# 3. Graph-based dependency resolver (equipment needed for specific projects).
#
# For lightweight, zero-latency campus deployment, we use deterministic keyword/stem matching.
# =========================================================================================


def normalize_text(text: str) -> list[str]:
    """
    Cleans raw user input by lowercasing, stripping punctuation, and splitting into word tokens.
    """
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t.strip() for t in cleaned.split() if t.strip()]
    return tokens


def find_matching_need(query: str) -> Optional[tuple[str, dict[str, Any]]]:
    """
    Scores query tokens against need keywords and returns the highest scoring need key.
    Returns (need_key, need_config) or None if no relevant match is found.
    """
    tokens = set(normalize_text(query))
    if not tokens:
        return None

    best_match_key = None
    best_score = 0

    for need_key, config in NEED_DICTIONARY.items():
        keywords = set(config.get("keywords", []))
        # Exact word intersection score
        overlap = len(tokens.intersection(keywords))

        # Check if the need_key itself or any multi-word keyword is contained as substring
        normalized_query = " ".join(tokens)
        for kw in keywords:
            if kw in normalized_query:
                overlap += 1

        if overlap > best_score:
            best_score = overlap
            best_match_key = need_key

    if best_score > 0 and best_match_key is not None:
        return best_match_key, NEED_DICTIONARY[best_match_key]

    return None


def match_item_for_tag(conn: sqlite3.Connection, tag: str) -> Optional[dict[str, Any]]:
    """
    Searches available inventory for an item whose title, category, or tags match the requested tag.
    Picks the lowest price available item first (student-friendly budget sorting).
    """
    tag_clean = tag.strip().lower()
    search_pattern = f"%{tag_clean}%"

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT i.*, u.name as owner_name
        FROM items i
        LEFT JOIN users u ON i.owner_id = u.id
        WHERE i.available = 1
          AND (
            LOWER(i.tags) LIKE ?
            OR LOWER(i.title) LIKE ?
            OR LOWER(i.category) LIKE ?
          )
        ORDER BY i.price_per_day ASC, i.id ASC
        LIMIT 1
        """,
        (search_pattern, search_pattern, search_pattern),
    )
    row = cursor.fetchone()
    if not row:
        return None

    try:
        checklist = json.loads(row["condition_checklist"]) if isinstance(row["condition_checklist"], str) else row["condition_checklist"]
    except Exception:
        checklist = {}

    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "owner_name": row["owner_name"],
        "title": row["title"],
        "category": row["category"],
        "description": row["description"],
        "value": row["value"],
        "price_per_day": row["price_per_day"],
        "deposit_amount": row["deposit_amount"],
        "serial": row["serial"],
        "photo_path": row["photo_path"],
        "photo_hash": row["photo_hash"],
        "item_hash": row["item_hash"],
        "condition_checklist": checklist,
        "tags": row["tags"],
        "mode": row["mode"],
        "available": bool(row["available"]),
        "created_at": row["created_at"],
    }


def resolve_need_bundle(conn: sqlite3.Connection, query: str) -> dict[str, Any]:
    """
    Takes a natural query, identifies the need bundle, matches each required tag against
    available inventory, and computes bundle pricing and missing items.
    """
    matched = find_matching_need(query)

    if not matched:
        return {
            "query": query,
            "matched_need_key": None,
            "need_title": None,
            "required_tags": [],
            "bundle": [],
            "missing_tags": [],
            "total_bundle_price_per_day": 0.0,
            "total_bundle_deposit": 0.0,
        }

    need_key, need_config = matched
    required_tags: list[str] = need_config.get("required_tags", [])

    bundle_items: list[dict[str, Any]] = []
    missing_tags: list[str] = []
    total_price = 0.0
    total_deposit = 0.0

    for tag in required_tags:
        matched_item = match_item_for_tag(conn, tag)
        if matched_item:
            bundle_items.append({
                "tag": tag,
                "matched": True,
                "item": matched_item,
            })
            total_price += matched_item["price_per_day"]
            total_deposit += matched_item["deposit_amount"]
        else:
            bundle_items.append({
                "tag": tag,
                "matched": False,
                "item": None,
            })
            missing_tags.append(tag)

    return {
        "query": query,
        "matched_need_key": need_key,
        "need_title": need_config.get("title", need_key.title()),
        "required_tags": required_tags,
        "bundle": bundle_items,
        "missing_tags": missing_tags,
        "total_bundle_price_per_day": round(total_price, 2),
        "total_bundle_deposit": round(total_deposit, 2),
    }
