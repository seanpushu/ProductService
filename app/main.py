"""Product Service - FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401  (registers the Product model on Base)
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
    version="0.1.0",
    description="Product catalog API for the AI Product project (02 Product Service).",
    lifespan=lifespan,
)

app.include_router(products.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"service": "product-service", "docs": "/docs"}


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Used by the ALB target group health check."""
    return {"status": "ok"}
