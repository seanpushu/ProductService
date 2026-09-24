"""Database connection setup.

DATABASE_URL decides which PostgreSQL we talk to:
- local:  postgresql+psycopg://postgres:postgres@localhost:5432/products
- AWS:    postgresql+psycopg://<user>:<password>@<rds-endpoint>:5432/products
The application code is identical in both cases.
"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/products",
)

# pool_pre_ping: check the connection is alive before using it, so a restarted
# database does not surface as a confusing error on the first request.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Parent class for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
