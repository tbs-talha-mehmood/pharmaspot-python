from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db, Base, engine
from ..models import User
from ..schemas import UserCreate, UserOut, LoginRequest, LoginResponse
from ..security import hash_password, verify_password


# Ensure tables
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/", response_model=str)
def index():
    return "Users API"


@router.get("/all", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(User).all()


@router.get("/user/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/logout/{user_id}")
def logout(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = f"Logged Out_{__import__('datetime').datetime.now()}"
    db.add(user)
    db.commit()
    return {"ok": True}


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        return LoginResponse(auth=False)
    if not verify_password(req.password, user.password_hash):
        return LoginResponse(auth=False)
    user.status = f"Logged In_{__import__('datetime').datetime.now()}"
    db.add(user)
    db.commit()
    return LoginResponse(
        auth=True,
        id=user.id,
        username=user.username,
        fullname=user.fullname or "",
        status=user.status or "",
        perm_products=bool(user.perm_products),
        perm_transactions=bool(user.perm_transactions),
        perm_users=bool(user.perm_users),
        perm_settings=bool(user.perm_settings),
    )


@router.post("/post", response_model=UserOut)
def create_or_update(user_in: UserCreate, db: Session = Depends(get_db)):
    # If username exists, update; else create new with next id
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        user.fullname = user_in.fullname or ""
        user.perm_products = bool(user_in.perm_products)
        user.perm_transactions = bool(user_in.perm_transactions)
        user.perm_users = bool(user_in.perm_users)
        user.perm_settings = bool(user_in.perm_settings)
        if user_in.password:
            user.password_hash = hash_password(user_in.password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    else:
        new_user = User(
            username=user_in.username,
            fullname=user_in.fullname or "",
            password_hash=hash_password(user_in.password),
            perm_products=bool(user_in.perm_products),
            perm_transactions=bool(user_in.perm_transactions),
            perm_users=bool(user_in.perm_users),
            perm_settings=bool(user_in.perm_settings),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user


@router.get("/check")
def ensure_admin(db: Session = Depends(get_db)):
    # Create default admin if missing (id=1)
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        admin = User(
            id=1,
            username="admin",
            fullname="Administrator",
            password_hash=hash_password("admin"),
            perm_products=True,
            perm_transactions=True,
            perm_users=True,
            perm_settings=True,
        )
        db.add(admin)
        db.commit()
    return {"ok": True}
