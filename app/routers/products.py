"""Product Service endpoints.

POST   /products        create
GET    /products        list (ACTIVE only by default)
GET    /products/{id}   read one
PUT    /products/{id}   update fields / re-list
DELETE /products/{id}   take off the shelf (soft delete -> status INACTIVE)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product
from app.schemas import ProductCreate, ProductList, ProductOut, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


def _get_or_404(db: Session, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> Product:
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=ProductList)
def list_products(
    include_inactive: bool = Query(False, description="Also return INACTIVE products"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ProductList:
    stmt = select(Product)
    if not include_inactive:
        stmt = stmt.where(Product.status == "ACTIVE")

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.order_by(Product.created_at.desc(), Product.id).limit(limit).offset(offset)
    ).all()
    return ProductList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> Product:
    return _get_or_404(db, product_id)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID, payload: ProductUpdate, db: Session = Depends(get_db)
) -> Product:
    product = _get_or_404(db, product_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")
    for field, value in changes.items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Take a product off the shelf. The row is kept so order history stays valid."""
    product = _get_or_404(db, product_id)
    if product.status != "INACTIVE":
        product.status = "INACTIVE"
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
