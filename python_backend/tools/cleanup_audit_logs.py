from sqlalchemy import inspect, text

from python_backend.app.database import (engine)


def main() -> None:
    """Delete all rows from the audit_logs table, if it exists."""
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
    except Exception as exc:  # pragma: no cover - maintenance helper
        print(f"Could not inspect database: {exc}")
        return

    if "audit_logs" not in tables:
        print("audit_logs table not found; nothing to clean up.")
        return

    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM audit_logs"))
        print("All rows deleted from audit_logs table.")
    except Exception as exc:  # pragma: no cover - maintenance helper
        print(f"Failed to delete audit logs: {exc}")


if __name__ == "__main__":
    main()

