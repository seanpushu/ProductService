"""Pydantic schemas: what the API accepts and returns.

Validation happens here, before anything touches the database.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProductStatus = Literal["ACTIVE", "INACTIVE"]

_NAME = Field(min_length=1, max_length=120, examples=["Wooden Desk Lamp"])
_DESCRIPTION = Field(default=None, max_length=2000)
_PRICE = Field(ge=0, description="Price in integer cents", examples=[4999])
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
    price_cents: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    image_url: str | None = _IMAGE_URL
    status: ProductStatus | None = None


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
