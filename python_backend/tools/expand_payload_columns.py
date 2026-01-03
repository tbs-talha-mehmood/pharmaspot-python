import os
from pathlib import Path


def main():
    # Ensure same APPNAME pathing as the API
    os.environ.setdefault("APPNAME", "pharmaspot")

    # Late imports
    from python_backend.app.database import engine

    dialect = engine.dialect.name.lower()
    print(f"Detected dialect: {dialect}")

    if dialect.startswith("mysql") or dialect == "mysql":
        stmts = [
            "ALTER TABLE purchases MODIFY COLUMN items_json LONGTEXT NOT NULL",
            "ALTER TABLE transactions MODIFY COLUMN items_json LONGTEXT NOT NULL",
        ]
        with engine.begin() as conn:
            for sql in stmts:
                print(f"Executing: {sql}")
                conn.exec_driver_sql(sql)
        print("Columns updated to LONGTEXT on MySQL.")
    else:
        # SQLite and others: TEXT already unbounded enough; no change needed
        print("No migration required for this dialect.")


if __name__ == "__main__":
    main()

