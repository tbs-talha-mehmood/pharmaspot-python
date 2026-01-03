import os
from pathlib import Path
from typing import Optional, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from urllib.parse import quote_plus
try:
    # Load environment variables from a .env file if present
    from dotenv import load_dotenv  # type: ignore

    try:
        # Prefer python_backend/.env relative to this file
        _ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
        if _ENV_PATH.exists():
            load_dotenv(dotenv_path=_ENV_PATH)
        else:
            # Fallback to default search (current working directory)
            load_dotenv()
    except Exception:
        pass
except Exception:
    # dotenv is optional; ignore if not installed
    pass
try:
    # SQLAlchemy 1.4+
    from sqlalchemy.engine.url import URL
except Exception:
    URL = None  # type: ignore


def _appdata_dir() -> Path:
    # Prefer Windows APPDATA. Fallback to user home.
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    appname = os.environ.get("APPNAME") or "pharmaspot"
    return Path(base) / appname / "server" / "databases"


DB_DIR = _appdata_dir()
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "app.db"


def _build_mysql_url() -> Optional[str]:
    host = os.environ.get("DB_HOST")
    name = os.environ.get("DB_NAME")
    user = os.environ.get("DB_USER")
    pwd = os.environ.get("DB_PASSWORD")
    port = os.environ.get("DB_PORT") or "3306"
    driver = os.environ.get("DB_DRIVER") or "pymysql"
    if not (host and name and user and pwd):
        return None

    # Prefer SQLAlchemy URL helper when available to avoid quoting issues
    if URL is not None:
        try:
            url = URL.create(
                drivername=f"mysql+{driver}",
                username=user,
                password=pwd,
                host=host,
                port=int(port) if str(port).isdigit() else None,
                database=name,
                query={"charset": "utf8mb4"},
            )
            return str(url)
        except Exception:
            pass

    # Fallback to manual construction with safe quoting
    user_q = quote_plus(user)
    pwd_q = quote_plus(pwd)
    host_part = f"{host}:{port}" if port else host
    return f"mysql+{driver}://{user_q}:{pwd_q}@{host_part}/{name}?charset=utf8mb4"


def _compute_db_url() -> Dict[str, Any]:
    # Highest priority: explicit DATABASE_URL
    url = os.environ.get("DATABASE_URL")
    if url:
        return {"url": url, "connect_args": {}}

    # Next: MySQL via env vars
    engine_env = (os.environ.get("DB_ENGINE") or os.environ.get("DB_TYPE") or "").lower()
    if engine_env == "mysql" or os.environ.get("DB_HOST"):
        mysql_url = _build_mysql_url()
        if mysql_url:
            return {"url": mysql_url, "connect_args": {}}

    # Fallback: local SQLite
    return {
        "url": f"sqlite:///{DB_PATH}",
        "connect_args": {"check_same_thread": False},
    }


cfg = _compute_db_url()
engine = create_engine(cfg["url"], connect_args=cfg.get("connect_args", {}), pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
