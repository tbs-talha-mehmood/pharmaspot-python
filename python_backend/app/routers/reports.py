from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import Base, engine, get_db
from ..services.cogs import build_profit_reconciliation, build_company_inventory_snapshot


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
