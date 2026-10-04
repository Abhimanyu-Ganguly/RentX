"""
Tests for Need-based Equipment Bundling and inventory match resolution.
"""

from app.services.matching import resolve_need_bundle, normalize_text, find_matching_need


def _seed_inventory(conn):
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name, email, created_at) VALUES ('Alice', 'alice@campus.edu', '2026-10-01T00:00:00Z')")
    user_id = cur.lastrowid

    # Seed 2 of the 4 camping items
    cur.execute(
        """
        INSERT INTO items (owner_id, title, category, value, price_per_day, deposit_amount, serial,
                           photo_path, photo_hash, item_hash, condition_checklist, tags, available, created_at)
        VALUES (?, 'Coleman 4-Person Dome Tent', 'camping', 150, 15, 50, 'TNT-001', 'p.jpg', 'ph', 'ih', '{}', 'tent,camping,shelter', 1, '2026-10-01T00:00:00Z')
        """,
        (user_id,),
    )

    cur.execute(
        """
        INSERT INTO items (owner_id, title, category, value, price_per_day, deposit_amount, serial,
                           photo_path, photo_hash, item_hash, condition_checklist, tags, available, created_at)
        VALUES (?, 'Camp Chef Propane Stove', 'camping', 80, 8, 30, 'STV-001', 'p.jpg', 'ph', 'ih', '{}', 'stove,cooking,gas', 1, '2026-10-01T00:00:00Z')
        """,
        (user_id,),
    )


def test_text_normalization():
    """Verify input text is cleaned and tokenized correctly."""
    tokens = normalize_text("I'm going CAMPING with friends!! Can we find gear?")
    assert "camping" in tokens
    assert "friends" in tokens


def test_find_matching_need():
    """Verify keyword match returns correct need structure."""
    res = find_matching_need("we are planning to go camping in Yosemite")
    assert res is not None
    key, config = res
    assert key == "camping"
    assert "tent" in config["required_tags"]


def test_resolve_need_bundle_with_partial_inventory(db_conn):
    """
    Verify need bundle matching with partial inventory:
    Camping needs: tent, stove, lantern, sleeping bag.
    We seeded tent & stove -> lantern and sleeping bag should be identified in missing_tags.
    """
    _seed_inventory(db_conn)

    bundle_res = resolve_need_bundle(db_conn, "We want to go camping this weekend")
    assert bundle_res["matched_need_key"] == "camping"
    assert len(bundle_res["required_tags"]) == 4
    assert len(bundle_res["bundle"]) == 4

    matched_tags = [b["tag"] for b in bundle_res["bundle"] if b["matched"]]
    assert "tent" in matched_tags
    assert "stove" in matched_tags

    missing_tags = bundle_res["missing_tags"]
    assert "lantern" in missing_tags
    assert "sleeping bag" in missing_tags

    # Total bundle daily cost = $15 (tent) + $8 (stove) = $23
    assert bundle_res["total_bundle_price_per_day"] == 23.0
    # Total deposit = $50 + $30 = $80
    assert bundle_res["total_bundle_deposit"] == 80.0


def test_unknown_query_returns_empty_result(db_conn):
    """Verify that completely unmatched queries return safe empty structures without crashing."""
    bundle_res = resolve_need_bundle(db_conn, "learn quantum computing on a supercomputer")
    assert bundle_res["matched_need_key"] is None
    assert bundle_res["bundle"] == []
    assert bundle_res["missing_tags"] == []
    assert bundle_res["total_bundle_price_per_day"] == 0.0
