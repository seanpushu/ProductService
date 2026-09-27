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
| GET | `/health` | Health check used by the load balancer (process only, no DB check) |
| GET | `/version` | Running version and git commit SHA |

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

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (secret; on AWS injected from Secrets Manager) |
| `CORS_ALLOW_ORIGINS` | Comma-separated browser origins, default `http://localhost:5173,http://127.0.0.1:5173` |
| `GIT_SHA` | Commit SHA shown by `GET /version`, set at image build time. The version number is `APP_VERSION` in `app/config.py` |

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q        # SQLite unit tests only
docker compose up -d db
docker compose exec db createdb -U postgres products_test
$env:TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/products_test"
.\.venv\Scripts\python.exe -m pytest -v        # + PostgreSQL integration tests
```

`tests/test_postgres_integration.py` starts the real app (lifespan `create_all`) against PostgreSQL and
checks CRUD, pagination, 404 and 422. `tests/conftest.py` refuses a database whose name does not end in
`_test` or that is on RDS; the tests only delete rows they created.

## Security limitation

The write endpoints (`POST`, `PUT`, `DELETE`) have **no authentication**. Anyone who can reach the API can
change the catalog. CORS only restricts which web pages may read responses in a browser; it is not access
control. The public frontend only uses `GET /products`. This is a course project, not production-hardened.

## Seed data

```powershell
.\.venv\Scripts\python.exe scripts\seed_products.py --base-url http://localhost:8080
```

Reads `seed/products.json`; image URLs there point at the S3 bucket.

## Deploy to AWS (CI/CD)

- Pull request to `main`: `.github/workflows/ci.yml` (tests, Docker smoke test, cfn-lint). No AWS access.
- Push to `main`: `.github/workflows/deploy.yml` runs CI, then builds `productservice:<commit-sha>`, pushes to
  ECR, updates CloudFormation stack `productservice-app` and verifies `https://api.shupu.me`.

Details, resource ownership, IAM roles and pause/resume: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

`aws/up.ps1` / `aws/down.ps1` are the older manual scripts from Session 5. Their resource names are
out of date; do not run them.

## Layout

```
app/main.py            FastAPI app, CORS, /health, /version, table creation on startup
app/config.py          non-secret settings (CORS origins, version)
infra/                 CloudFormation: app stack + one-time GitHub OIDC bootstrap
.github/workflows/     ci.yml (PR checks), deploy.yml (main -> AWS)
app/db.py              engine / session from DATABASE_URL
app/models.py          products table
app/schemas.py         request / response validation
app/routers/products.py  the five product endpoints
scripts/seed_products.py seed via the API
tests/                 SQLite CRUD tests + PostgreSQL integration tests
aws/                   old Session 5 manual scripts (outdated names, do not run)
```
