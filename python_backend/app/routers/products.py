from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from sqlalchemy import func
import math

from ..database import get_db, Base, engine
from ..models import Product, Company
from ..schemas import ProductCreate, ProductOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/", response_model=str)
def index():
    return "Products API"


def _to_out(prod: Product, company_map: dict[int, str]) -> ProductOut:
    discount_val = float(getattr(prod, "discount_pct", 0.0) or 0.0)
    trade_val = float(getattr(prod, "trade_price", 0.0) or 0.0)
    return ProductOut(
        id=prod.id,
        expirationDate=prod.expirationDate or "",
        price=prod.price or 0.0,
        company_id=int(prod.company_id or 0),
        company_name=company_map.get(int(prod.company_id or 0), ""),
        quantity=int(prod.quantity or 0),
        name=prod.name,
        minStock=0,
        img=prod.img or "",
        discount_pct=discount_val,
        trade_price=trade_val,
        purchase_discount=discount_val,
        sale_discount=0.0,
        is_active=bool(getattr(prod, "is_active", True)),
    )


@router.get("/all", response_model=List[ProductOut])
def list_products(
    company_id: int = 0,
    q: str = "",
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    companies = db.query(Company).all()
    company_map = {int(c.id): c.name for c in companies}
    query = db.query(Product)
    if not include_inactive:
        query = query.filter(Product.is_active == True)  # noqa: E712
    if company_id:
        query = query.filter(Product.company_id == int(company_id))
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(Product.name).like(needle))
    items = query.all()
    return [_to_out(p, company_map) for p in items]


@router.get("/page", response_model=Dict[str, Any])
def list_products_page(
    company_id: int = 0,
    q: str = "",
    include_inactive: bool = False,
    page: int = 1,
    page_size: int = 25,
    db: Session = Depends(get_db),
):
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 25), 200))
    companies = db.query(Company).all()
    company_map = {int(c.id): c.name for c in companies}
    query = db.query(Product)
    if not include_inactive:
        query = query.filter(Product.is_active == True)  # noqa: E712
    if company_id:
        query = query.filter(Product.company_id == int(company_id))
    if q:
        needle = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(Product.name).like(needle))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_to_out(p, company_map) for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": int(math.ceil(total / float(page_size))) if page_size else 1,
    }


@router.get("/product/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    companies = db.query(Company).all()
    company_map = {int(c.id): c.name for c in companies}
    return _to_out(prod, company_map)


@router.post("/product", response_model=ProductOut)
def upsert_product(payload: ProductCreate, db: Session = Depends(get_db)):
    if payload.id is not None:
        prod = db.query(Product).filter(Product.id == int(payload.id)).first()
        if not prod:
            prod = Product(id=int(payload.id), is_active=True)
            db.add(prod)
        elif prod.is_active is None or not bool(prod.is_active):
            prod.is_active = True
    else:
        prod = Product(is_active=True)
        db.add(prod)

    company_id = int(payload.company_id or 0)
    if company_id:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise HTTPException(status_code=400, detail="Company not found")

    prod.expirationDate = payload.expirationDate or ""
    prod.price = payload.price or 0.0
    prod.company_id = company_id
    prod.company_id = company_id
    if payload.quantity is not None:
        prod.quantity = payload.quantity
    elif prod.quantity is None:
        prod.quantity = 0
    prod.name = payload.name
    prod.img = payload.img or ""
    # Map legacy fields to new ones if present
    try:
        discount_val = (
            payload.discount_pct
            if payload.discount_pct is not None
            else payload.purchase_discount
        )
        if discount_val is not None:
            prod.discount_pct = float(discount_val or 0.0)
    except Exception:
        pass
    try:
        trade_val = payload.trade_price
        if trade_val is not None:
            prod.trade_price = float(trade_val or 0.0)
    except Exception:
        pass
    # sale_discount removed (ignored)

    db.commit()
    db.refresh(prod)
    companies = db.query(Company).all()
    company_map = {int(c.id): c.name for c in companies}
    return _to_out(prod, company_map)


@router.delete("/product/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    prod.is_active = False
    db.add(prod)
    db.commit()
    return {"ok": True, "inactive": True}
