"""Product Service - FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (registers the Product model on Base)
from app.config import APP_VERSION, CORS_ALLOW_ORIGINS, GIT_SHA
from app.db import Base, engine
from app.routers import products


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Create tables that do not exist yet. Good enough for this assignment;
    # a production service would use Alembic migrations instead.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Product Service",
    version=APP_VERSION,
    description="Product catalog API for the AI Product project (02 Product Service).",
    lifespan=lifespan,
)

# The public catalog only needs credential-free GET requests from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
    max_age=600,
)

app.include_router(products.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"service": "product-service", "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Used by the ALB target group health check. Process liveness only."""
    return {"status": "ok"}


@app.get("/version", tags=["meta"])
def version() -> dict[str, str]:
    """Which build is running. Used to confirm an automatic deploy landed."""
    return {"service": "product-service", "version": APP_VERSION, "git_sha": GIT_SHA}
