"""Pydantic schemas: what the API accepts and returns.

Validation happens here, before anything touches the database.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProductStatus = Literal["ACTIVE", "INACTIVE"]

# products.price_cents is a PostgreSQL INTEGER (32-bit). Reject larger values
# with 422 instead of letting the database raise and the API return 500.
MAX_PRICE_CENTS = 2_147_483_647

_NAME = Field(min_length=1, max_length=120, examples=["Wooden Desk Lamp"])
_DESCRIPTION = Field(default=None, max_length=2000)
_PRICE = Field(ge=0, le=MAX_PRICE_CENTS, description="Price in integer cents", examples=[4999])
_CURRENCY = Field(default="USD", pattern=r"^[A-Z]{3}$")
_IMAGE_URL = Field(
    default=None,
    max_length=2048,
    pattern=r"^https?://",
    examples=["https://example-bucket.s3.amazonaws.com/products/lamp.jpg"],
)


class ProductCreate(BaseModel):
    name: str = _NAME
    description: str | None = _DESCRIPTION
    price_cents: int = _PRICE
    currency: str = _CURRENCY
    image_url: str | None = _IMAGE_URL


class ProductUpdate(BaseModel):
    """All fields optional: send only what you want to change."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = _DESCRIPTION
    price_cents: int | None = Field(default=None, ge=0, le=MAX_PRICE_CENTS)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    image_url: str | None = _IMAGE_URL
    status: ProductStatus | None = None

    @model_validator(mode="after")
    def _no_null_for_required_columns(self) -> "ProductUpdate":
        # Omitting a field means "leave it alone"; sending null for a NOT NULL
        # column would otherwise fail inside the database with a 500.
        for field in ("name", "price_cents", "currency", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    price_cents: int
    currency: str
    image_url: str | None
    status: ProductStatus
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]
    total: int
    limit: int
    offset: int
