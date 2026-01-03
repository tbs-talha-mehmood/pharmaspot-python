from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db, Base, engine
from ..models import Product
from ..schemas import ProductCreate, ProductOut


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/", response_model=str)
def index():
    return "Products API"


@router.get("/all", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


@router.get("/product/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return prod


@router.post("/product", response_model=ProductOut)
def upsert_product(payload: ProductCreate, db: Session = Depends(get_db)):
    if payload.id is not None:
        prod = db.query(Product).filter(Product.id == int(payload.id)).first()
        if not prod:
            prod = Product(id=int(payload.id))
            db.add(prod)
    else:
        prod = Product()
        db.add(prod)

    prod.barcode = payload.barcode
    prod.expirationDate = payload.expirationDate or ""
    prod.price = payload.price or 0.0
    prod.category = payload.category or ""
    prod.quantity = payload.quantity or 0
    prod.name = payload.name
    prod.stock = payload.stock or 1
    prod.minStock = payload.minStock or 0
    prod.img = payload.img or ""
    prod.purchase_discount = payload.purchase_discount or 0.0
    prod.sale_discount = payload.sale_discount or 0.0

    db.commit()
    db.refresh(prod)
    return prod


@router.delete("/product/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(prod)
    db.commit()
    return {"ok": True}

