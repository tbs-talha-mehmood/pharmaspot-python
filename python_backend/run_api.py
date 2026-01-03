import os
import uvicorn


def main():
    os.environ.setdefault("APPNAME", "pharmaspot")
    # Import via package path so it works when launched with -m python_backend.run_api
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
