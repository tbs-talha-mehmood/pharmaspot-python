from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..services.cogs import (
    build_profit_reconciliation,
    build_company_inventory_snapshot,
    estimate_product_fifo_cost,
    build_product_purchase_lots,
)


Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/profit_reconciliation")
def profit_reconciliation(
    start_date: str = "",
    end_date: str = "",
    user_id: int = 0,
    db: Session = Depends(get_db),
):
    return build_profit_reconciliation(
        db,
        start_date=str(start_date or ""),
        end_date=str(end_date or ""),
        user_id=int(user_id or 0),
    )


@router.get("/company_inventory")
def company_inventory(
    include_inactive: bool = False,
    q: str = "",
    db: Session = Depends(get_db),
):
    return build_company_inventory_snapshot(
        db,
        include_inactive=bool(include_inactive),
        q=str(q or ""),
    )


@router.get("/product_margin_preview")
def product_margin_preview(
    product_id: int,
    quantity: float = 1.0,
    db: Session = Depends(get_db),
):
    return estimate_product_fifo_cost(
        db,
        product_id=int(product_id or 0),
        quantity=float(quantity or 0.0),
    )


@router.get("/product_purchase_lots")
def product_purchase_lots(
    product_id: int,
    db: Session = Depends(get_db),
):
    return build_product_purchase_lots(
        db,
        product_id=int(product_id or 0),
    )
