"""Runtime settings read from environment variables.

Nothing here is secret. DATABASE_URL (which contains the password) is read in
app/db.py and, on AWS, is injected from Secrets Manager by ECS.
"""

import os


def _split_csv(raw: str) -> list[str]:
    return [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]


# Browser origins allowed to call this API, comma separated, for example
#   CORS_ALLOW_ORIGINS=http://localhost:5173,https://d1234.cloudfront.net
# CORS only tells browsers which pages may read responses. It is NOT access
# control: curl or any server can still call every endpoint.
CORS_ALLOW_ORIGINS: list[str] = _split_csv(
    os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
)

# Release version: this line is the single source of truth. GIT_SHA is set by
# the Docker build from the commit being deployed.
APP_VERSION: str = "0.2.1"
GIT_SHA: str = os.getenv("GIT_SHA", "local")
