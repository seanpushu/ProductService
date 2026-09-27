"""Shared test setup.

PostgreSQL integration tests run only when TEST_DATABASE_URL is set. It must
point at a throwaway database whose name ends in "_test"; we refuse anything
that looks like the production RDS instance so tests can never touch real data.

The variable is copied into DATABASE_URL *before* app.db is imported, so the
app's own engine (and its startup create_all) talks to the test database.
"""

import os
from urllib.parse import urlparse

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    parsed = urlparse(TEST_DATABASE_URL)
    db_name = parsed.path.lstrip("/")
    if not db_name.endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL database name must end with '_test'")
    if parsed.hostname and parsed.hostname.endswith(".rds.amazonaws.com"):
        raise RuntimeError("TEST_DATABASE_URL must not point at an RDS instance")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
