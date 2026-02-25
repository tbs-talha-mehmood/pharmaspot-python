# PharmaSpot Python

Desktop pharmacy POS built with a FastAPI backend and a PyQt5 client.

## Project Structure

- `python_backend/` - FastAPI API, models, and routers
- `py_client/` - PyQt5 desktop app (POS, products, purchases, transactions, reports)

## Requirements

- Python 3.11+ (3.12 also works)
- Windows PowerShell commands are shown below

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r python_backend/requirements.txt
pip install -r py_client/requirements.txt
```

## Run

1. Start backend API:

```powershell
.venv\Scripts\Activate.ps1
python -m python_backend.run_api
```

2. Start desktop client (new terminal):

```powershell
.venv\Scripts\Activate.ps1
$env:API_URL = "http://127.0.0.1:8000"
python py_client/main.py
```

## Default Login

- The app calls `/api/users/check` on login.
- If no admin exists, it auto-creates:
  - Username: `admin`
  - Password: `admin`

## Database Configuration

By default, backend uses local SQLite:

- DB file: `%APPDATA%\pharmaspot\server\databases\app.db`
- Uploads: `%APPDATA%\pharmaspot\uploads`

To use MySQL, set environment variables before starting backend:

```powershell
$env:DB_ENGINE = "mysql"
$env:DB_HOST = "<host>"
$env:DB_PORT = "3306"
$env:DB_NAME = "<database>"
$env:DB_USER = "<user>"
$env:DB_PASSWORD = "<password>"
```

Optional override:

```powershell
$env:DATABASE_URL = "mysql+pymysql://user:pass@host:3306/dbname?charset=utf8mb4"
```

## POS Notes

- Reopen invoice: type invoice number and press `Enter`.
- Partial payments are supported across multiple attempts.
- Payments button appears after invoice reopen (edit mode).
- Payment history allows editing payment entries.
- Overpayment is blocked (paid amount cannot exceed invoice total).

Keyboard shortcuts:

- `F2` focus product search
- `F8` open purchase history for selected product
- `Shift+Enter` flow: cart -> discount -> paid -> checkout

## Useful Checks

```powershell
.venv\Scripts\python.exe -m py_compile py_client/views/pos.py
.venv\Scripts\python.exe -m py_compile py_client/views/transactions.py
.venv\Scripts\python.exe -m py_compile python_backend/app/routers/transactions.py
```
