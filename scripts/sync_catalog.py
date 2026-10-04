"""Bring a Product Service catalog in line with seed/catalog_customizable.json.

Dry-run by default: prints exactly which products would be created and which
old products would be taken off the shelf, and changes nothing.

    python scripts/sync_catalog.py --base-url http://localhost:8080 --image-base http://localhost:8090/
    python scripts/sync_catalog.py --base-url ... --image-base ... --apply
    python scripts/sync_catalog.py --base-url ... --image-base ... --apply --retire-id <uuid> --retire-id <uuid>

Rules
- Creates a catalog product only if no product (ACTIVE or INACTIVE) with the
  exact same name exists, so re-running never creates duplicates.
- For products whose name exactly equals a catalog name, updates only
  description / image_url when they differ (never price, status or others).
- Never deletes rows. Old products are soft-deleted (DELETE -> status
  INACTIVE), which keeps them for history and can be undone with
  PUT {"status": "ACTIVE"}.
- Retiring is opt-in per ID: only products whose ID is given with --retire-id
  AND whose name is on the retire list are touched. Unrelated products with a
  similar name are never affected. Without --retire-id, retiring is only
  reported.
- Uses only the standard library and the public API (no DB credentials).
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[1] / "seed" / "catalog_customizable.json"


def call(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, (json.loads(raw) if raw else {})


def load_all(base: str) -> list[dict]:
    items, offset = [], 0
    while True:
        status, page = call("GET", f"{base}/products?include_inactive=true&limit=200&offset={offset}")
        if status != 200:
            raise SystemExit(f"Cannot list products: HTTP {status} {page}")
        items += page["items"]
        offset += page["limit"]
        if offset >= page["total"]:
            return items


def plan(existing: list[dict], catalog: dict, image_base: str, retire_ids: set[str]) -> dict:
    by_name: dict[str, list[dict]] = {}
    for p in existing:
        by_name.setdefault(p["name"], []).append(p)
    create, update = [], []
    for item in catalog["products"]:
        wanted = {
            "name": item["name"],
            "description": item["description"],
            "price_cents": item["price_cents"],
            "currency": item["currency"],
            "image_url": image_base.rstrip("/") + "/" + item["image"],
        }
        matches = by_name.get(item["name"], [])
        if not matches:
            create.append(wanted)
            continue
        # Exact-name catalog rows only (never fuzzy): refresh image / copy if they drifted.
        for p in matches:
            changes = {k: wanted[k] for k in ("description", "image_url") if p.get(k) != wanted[k]}
            if changes:
                update.append({"id": p["id"], "name": p["name"], "changes": changes})
    names = set(by_name)
    retire_names = set(catalog["retire_names"])
    candidates = [p for p in existing if p["name"] in retire_names and p["status"] == "ACTIVE"]
    retire = [p for p in candidates if p["id"] in retire_ids]
    unknown = sorted(retire_ids - {p["id"] for p in candidates})
    return {"create": create, "update": update, "retire_candidates": candidates, "retire": retire, "unknown_ids": unknown}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--image-base", required=True, help="URL prefix that serves the SVG files")
    ap.add_argument("--apply", action="store_true", help="actually change data (default: dry run)")
    ap.add_argument("--retire-id", action="append", default=[], help="ID of an old product to take off the shelf")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    p = plan(load_all(base), catalog, args.image_base, set(args.retire_id))

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[{mode}] {base}")
    print(f"create {len(p['create'])}:")
    for c in p["create"]:
        print(f"  + {c['name']}  {c['price_cents']} {c['currency']}  {c['image_url']}")
    print(f"update {len(p['update'])} (exact-name catalog products, description / image only):")
    for u in p["update"]:
        print(f"  ~ {u['id']}  {u['name']}  fields: {', '.join(u['changes'])}")
    print(f"old products on the retire list still ACTIVE: {len(p['retire_candidates'])}")
    for c in p["retire_candidates"]:
        flag = "will take off shelf" if c in p["retire"] else "kept (pass --retire-id to retire)"
        print(f"  - {c['id']}  {c['name']}  -> {flag}")
    if p["unknown_ids"]:
        print(f"ERROR: --retire-id not found among active retire candidates: {p['unknown_ids']}")
        return 2
    if not args.apply:
        print("Nothing changed. Re-run with --apply to perform the plan above.")
        return 0

    failed = 0
    for c in p["create"]:
        status, body = call("POST", f"{base}/products", c)
        ok = status == 201
        failed += not ok
        print(f"  {'created' if ok else 'FAILED '} {body.get('id', '')} {c['name']}" + ("" if ok else f" HTTP {status} {body}"))
    for u in p["update"]:
        status, body = call("PUT", f"{base}/products/{u['id']}", u["changes"])
        ok = status == 200
        failed += not ok
        print(f"  {'updated' if ok else 'FAILED '} {u['id']} {u['name']}" + ("" if ok else f" HTTP {status} {body}"))
    for c in p["retire"]:
        status, body = call("DELETE", f"{base}/products/{c['id']}")
        ok = status == 204
        failed += not ok
        print(f"  {'retired' if ok else 'FAILED '} {c['id']} {c['name']}" + ("" if ok else f" HTTP {status} {body}"))
    print(f"done, failures={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
