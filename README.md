# Product Service

Product catalog API for the AI Product course project (module 02 Product Service).
FastAPI + PostgreSQL, deployed as a Docker image on AWS ECS Fargate behind an ALB,
with product images stored in S3 (the database keeps only the image URL).

Step-by-step explanation in Chinese: [PRODUCT_SERVICE_GUIDE.md](PRODUCT_SERVICE_GUIDE.md).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/products` | Create a product (201) |
| GET | `/products` | List ACTIVE products; `?include_inactive=true` for all; `limit` / `offset` |
| GET | `/products/{id}` | Get one product (404 if unknown) |
| PUT | `/products/{id}` | Update any subset of fields; `status: "ACTIVE"` re-lists a product |
| DELETE | `/products/{id}` | Take a product off the shelf (soft delete, status -> INACTIVE, 204) |
| GET | `/health` | Health check used by the load balancer |

Interactive docs: `/docs`.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
docker compose up -d db
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8080
```

`DATABASE_URL` defaults to the compose database (`postgresql+psycopg://postgres:postgres@localhost:5432/products`).
Override it via environment variable to point at RDS.

Run everything in containers instead:

```powershell
docker compose up --build
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests use an in-memory SQLite database, so no PostgreSQL is required.

## Seed data

```powershell
.\.venv\Scripts\python.exe scripts\seed_products.py --base-url http://localhost:8080
```

Reads `seed/products.json`; image URLs there point at the S3 bucket.

## Deploy to AWS

```powershell
powershell -ExecutionPolicy Bypass -File .\aws\up.ps1                  # first build (S3, RDS, ECR, ECS Fargate, ALB, HTTPS)
powershell -ExecutionPolicy Bypass -File .\aws\up.ps1 -SkipImagePush   # rebuild after down.ps1
powershell -ExecutionPolicy Bypass -File .\aws\down.ps1                # idle: stop RDS, remove service + ALB
```

`aws/up.ps1` is idempotent: each step checks whether the resource exists. Resource IDs and the
generated database password are kept in `aws/state.local.json` (gitignored).
`DATABASE_URL` is injected through the task definition; never commit real credentials.
Deployed at `https://api.shupu.me` when the stack is up; see the guide, section 6, for the record.

## Layout

```
app/main.py            FastAPI app, /health, table creation on startup
app/db.py              engine / session from DATABASE_URL
app/models.py          products table
app/schemas.py         request / response validation
app/routers/products.py  the five product endpoints
scripts/seed_products.py seed via the API
tests/                 CRUD tests
aws/                   task definition / IAM / S3 policy templates
```
