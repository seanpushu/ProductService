"""Seed products through the public API.

Usage:
    python scripts/seed_products.py --base-url http://localhost:8080
    python scripts/seed_products.py --base-url http://<alb-dns>

Reads seed/products.json and POSTs each item. Skips items whose name already
exists (so re-running is safe). Uses only the standard library.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SEED_FILE = Path(__file__).resolve().parents[1] / "seed" / "products.json"


def request(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="e.g. http://localhost:8080")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    status, existing = request("GET", f"{base}/products?include_inactive=true&limit=200")
    if status != 200:
        print(f"Cannot reach {base}/products: HTTP {status} {existing}")
        return 1
    existing_names = {p["name"] for p in existing.get("items", [])}

    items = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    created = skipped = failed = 0
    for item in items:
        if item["name"] in existing_names:
            skipped += 1
            continue
        status, body = request("POST", f"{base}/products", item)
        if status == 201:
            created += 1
            print(f"created  {body['id']}  {item['name']}")
        else:
            failed += 1
            print(f"FAILED   {item['name']}: HTTP {status} {body}")

    print(f"done: created={created} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
