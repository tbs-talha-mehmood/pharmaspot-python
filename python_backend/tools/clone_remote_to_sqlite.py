"""
Clone the current remote MySQL database to a local SQLite file.

Usage:
    python python_backend/tools/clone_remote_to_sqlite.py [output_path]

If output_path is omitted, the default is tools/remote_clone.sqlite
relative to the repository root. Environment variables (or python_backend/.env)
must point to the remote MySQL instance (DB_HOST/DB_NAME/DB_USER/DB_PASSWORD
or DATABASE_URL).
"""
import sys
from pathlib import Path
from typing import Type

from sqlalchemy import create_engine, insert, Text
from sqlalchemy.orm import sessionmaker

# Ensure python_backend (and repo root) are on sys.path so "app" resolves
TOOLS_DIR = Path(__file__).resolve().parent
PKG_ROOT = TOOLS_DIR.parent  # python_backend
REPO_ROOT = PKG_ROOT.parent
for p in (str(PKG_ROOT), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.database import _compute_db_url
from app.models import Base, Company, Product, Customer, User, Setting, Purchase, Transaction


def build_remote_engine():
    cfg = _compute_db_url()
    url = cfg["url"]
    connect_args = cfg.get("connect_args", {})
    print(f"[remote] {url}")
    return create_engine(url, connect_args=connect_args, pool_pre_ping=True)


def build_local_engine(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path}"
    print(f"[local] {url}")
    return create_engine(url)


def copy_table(remote_sess, local_conn, model: Type[Base]):
    rows = remote_sess.query(model).all()
    payload = []
    for row in rows:
        payload.append({col.name: getattr(row, col.name) for col in row.__table__.columns})
    if payload:
        local_conn.execute(insert(model.__table__), payload)
    print(f" copied {len(payload):4d} rows -> {model.__tablename__}")


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / "remote_clone.sqlite"
    remote_engine = build_remote_engine()
    local_engine = build_local_engine(out_path)

    # Build schema on local
    # Replace LONGTEXT columns with Text for SQLite compatibility
    for table in Base.metadata.sorted_tables:
        for col in table.c:
            tname = col.type.__class__.__name__.lower()
            if "longtext" in tname:
                col.type = Text()
    Base.metadata.create_all(bind=local_engine)

    RemoteSession = sessionmaker(bind=remote_engine)
    with RemoteSession() as r_sess, local_engine.begin() as l_conn:
        for model in (Company, Product, Customer, User, Setting, Purchase, Transaction):
            copy_table(r_sess, l_conn, model)

    print(f"Done. Local copy at: {out_path}")
    print("Point your app to this file with DATABASE_URL=sqlite:///<path> and restart.")


if __name__ == "__main__":
    main()
