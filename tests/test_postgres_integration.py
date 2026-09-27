"""Integration tests against a real PostgreSQL database.

Unlike test_products.py (SQLite, dependency override), these tests use the
application exactly as it runs in production: the real engine from
DATABASE_URL, the real startup hook that creates tables, and the real
PostgreSQL constraints. Run with, for example:

    TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/products_test pytest

Every row created here carries a unique run tag, and only those rows are
removed afterwards; nothing else in the database is read for assertions or
deleted.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)

RUN_TAG = f"pgtest-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def client():
    from app.db import SessionLocal, engine
    from app.main import app
    from app.models import Product

    assert engine.dialect.name == "postgresql"
    # `with` runs the lifespan: create_all against the real database.
    with TestClient(app) as c:
        yield c
    with SessionLocal() as db:
        db.execute(delete(Product).where(Product.name.like(f"{RUN_TAG}%")))
        db.commit()


def _name(suffix: str) -> str:
    return f"{RUN_TAG} {suffix}"


def test_startup_created_table_and_connects(client):
    from app.db import engine

    with engine.connect() as conn:
        assert conn.execute(text("select to_regclass('public.products')")).scalar() == "products"
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/version").status_code == 200


def test_crud_on_postgres(client):
    r = client.post(
        "/products",
        json={
            "name": _name("Mug"),
            "description": "Ceramic",
            "price_cents": 1299,
            "image_url": "https://images.test/mug.jpg",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    pid = body["id"]
    assert body["status"] == "ACTIVE" and body["currency"] == "USD"
    assert body["created_at"] and body["updated_at"]

    listed = client.get("/products", params={"limit": 200}).json()
    assert {"items", "total", "limit", "offset"} <= listed.keys()
    assert pid in {p["id"] for p in listed["items"]}

    page = client.get("/products", params={"limit": 1, "offset": 0}).json()
    assert page["limit"] == 1 and len(page["items"]) == 1

    assert client.get(f"/products/{pid}").json()["name"] == _name("Mug")

    r = client.put(f"/products/{pid}", json={"price_cents": 999})
    assert r.status_code == 200
    assert r.json()["price_cents"] == 999 and r.json()["description"] == "Ceramic"

    assert client.delete(f"/products/{pid}").status_code == 204
    active_ids = {p["id"] for p in client.get("/products", params={"limit": 200}).json()["items"]}
    assert pid not in active_ids
    assert client.get(f"/products/{pid}").json()["status"] == "INACTIVE"


def test_errors_on_postgres(client):
    missing = str(uuid.uuid4())
    assert client.get(f"/products/{missing}").status_code == 404
    assert client.put(f"/products/{missing}", json={"name": "x"}).status_code == 404
    assert client.delete(f"/products/{missing}").status_code == 404
    assert client.get("/products/not-a-uuid").status_code == 422
    assert client.post("/products", json={"name": _name("x"), "price_cents": -1}).status_code == 422
    # Beyond PostgreSQL INTEGER: must be a 422, not a database error / 500.
    r = client.post("/products", json={"name": _name("big"), "price_cents": 2**31})
    assert r.status_code == 422

    pid = client.post("/products", json={"name": _name("Nullable"), "price_cents": 1}).json()["id"]
    assert client.put(f"/products/{pid}", json={"name": None}).status_code == 422
    assert client.put(f"/products/{pid}", json={}).status_code == 422
    assert client.put(f"/products/{pid}", json={"description": None}).status_code == 200
