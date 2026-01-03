import os
from pathlib import Path

# Make imports work when run as a module or a script
try:
    from app.database import engine, SessionLocal  # type: ignore
except ModuleNotFoundError:
    try:
        from python_backend.app.database import engine, SessionLocal  # type: ignore
    except ModuleNotFoundError:
        import sys
        sys.path.append(str(Path(__file__).resolve().parents[1]))
        from app.database import engine, SessionLocal  # type: ignore

from sqlalchemy import text


def main() -> None:
    try:
        # Render URL without exposing the password
        try:
            url_display = engine.url.render_as_string(hide_password=True)  # type: ignore[attr-defined]
        except Exception:
            url_display = str(engine.url)
        print(f"Using DB URL: {url_display}")

        # Simple connectivity check
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("OK: Connected and executed SELECT 1")

        # Optional: open/close a session
        s = SessionLocal()
        s.close()
        print("OK: Session lifecycle healthy")
    except Exception as e:
        print("ERROR: Database connection test failed:", repr(e))
        raise SystemExit(1)


if __name__ == "__main__":
    main()

