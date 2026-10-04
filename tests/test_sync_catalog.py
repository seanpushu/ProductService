"""Unit tests for scripts/sync_catalog.py planning logic (no network)."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_catalog", ROOT / "scripts" / "sync_catalog.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

CATALOG = json.loads((ROOT / "seed" / "catalog_customizable.json").read_text(encoding="utf-8"))


def row(name, status="ACTIVE", pid=None):
    return {"id": pid or f"id-{name}", "name": name, "status": status}


def test_catalog_file_is_consistent():
    names = [p["name"] for p in CATALOG["products"]]
    assert len(names) == len(set(names))
    for p in CATALOG["products"]:
        assert p["price_cents"] > 0 and p["currency"] == "USD"
        assert (ROOT / "seed" / "images" / "custom" / p["image"]).is_file(), p["image"]
        assert "Customizable" in p["name"]


def test_plan_creates_missing_and_is_idempotent():
    p = sync.plan([], CATALOG, "https://img.test/products/", set())
    assert len(p["create"]) == len(CATALOG["products"])
    assert p["create"][0]["image_url"].startswith("https://img.test/products/")

    # After creation (even if later INACTIVE) nothing is created again.
    existing = [row(c["name"]) for c in p["create"]]
    existing[0]["status"] = "INACTIVE"
    assert sync.plan(existing, CATALOG, "https://img.test", set())["create"] == []


def test_retire_only_by_explicit_id_and_listed_name():
    old = row("Blueberries, 1 Pint", pid="b1")
    unrelated = row("Blueberries Tee", pid="u1")
    p = sync.plan([old, unrelated], CATALOG, "https://img.test", set())
    assert [c["id"] for c in p["retire_candidates"]] == ["b1"]
    assert p["retire"] == []  # report only without --retire-id

    p = sync.plan([old, unrelated], CATALOG, "https://img.test", {"b1"})
    assert [c["id"] for c in p["retire"]] == ["b1"]

    # An ID that is not a listed, active old product is rejected, never retired.
    p = sync.plan([old, unrelated], CATALOG, "https://img.test", {"u1"})
    assert p["retire"] == [] and p["unknown_ids"] == ["u1"]
