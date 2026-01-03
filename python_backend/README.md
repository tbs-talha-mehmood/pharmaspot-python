Python conversion (FastAPI + PyQt5)

Folders:
- python_backend: FastAPI backend service
- py_client: PyQt5 desktop shell that launches the API in-process

Quick start:
1) Create venv and install backend deps
   - python -m venv .venv
   - .venv\\Scripts\\activate
   - pip install -r python_backend/requirements.txt

2) Option A: Run API alone
   - python -m python_backend.run_api

3) Option B: Run PyQt5 desktop which embeds the API
   - pip install -r py_client/requirements.txt
   - python py_client/main.py

Notes:
- Database configuration:
  - Default: SQLite at %APPDATA%/pharmaspot/server/databases/app.db
  - To use MySQL, set environment variables before launching:
    - Windows PowerShell example:
      - $env:DB_ENGINE = "mysql"
      - $env:DB_HOST = "<host>"
      - $env:DB_PORT = "3306"  # optional
      - $env:DB_NAME = "<database>"
      - $env:DB_USER = "<user>"
      - $env:DB_PASSWORD = "<password>"
      - Optional: $env:DATABASE_URL overrides all (SQLAlchemy URL)
    - Driver: pymysql (installed), charset utf8mb4
  - Example for your remote DB:
    - $env:DB_ENGINE = "mysql"
    - $env:DB_HOST = "<your-mysql-host>"
    - $env:DB_NAME = "u930334298_Pharma"
    - $env:DB_USER = "u930334298_Pharma"
    - $env:DB_PASSWORD = "42Igr#WiTy|T"
- Uploads stored in %APPDATA%/pharmaspot/uploads.
- Users endpoint will auto-create admin/admin on first call to /api/users/check.
