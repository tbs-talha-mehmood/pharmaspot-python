import os
import sys
from pathlib import Path
import threading
import socket
import time
import traceback
from contextlib import closing

from PyQt5 import QtWidgets, QtCore, QtGui
import requests
from api import ApiClient
from app import PharmaApp
from theme import apply_theme, prepare_theme

_BACKEND_START_ERROR = None


def find_open_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def start_api_server(port: int):
    global _BACKEND_START_ERROR
    os.environ.setdefault("APPNAME", "pharmaspot")
    # Start uvicorn in-process
    # Ensure repo root is on sys.path so 'python_backend' is importable
    if getattr(sys, "frozen", False):
        repo_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    try:
        import uvicorn
        # Use package-qualified path so imports resolve regardless of CWD
        uvicorn.run(
            "python_backend.app.main:app",
            host="127.0.0.1",
            port=port,
            reload=False,
            log_config=None,
            access_log=False,
        )
    except Exception:
        _BACKEND_START_ERROR = traceback.format_exc()
        try:
            if getattr(sys, "frozen", False):
                log_path = Path(sys.executable).resolve().parent / "backend_startup.log"
            else:
                log_path = Path(__file__).resolve().parents[1] / "backend_startup.log"
            log_path.write_text(_BACKEND_START_ERROR, encoding="utf-8")
        except Exception:
            pass


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, api_url: str):
        super().__init__()
        self.api_url = api_url
        self.setWindowTitle("PharmaSpot (PyQt)")
        self.resize(1200, 800)

        self.status = self.statusBar()
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        header = QtWidgets.QLabel("PharmaSpot")
        header.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(header)

        self.info = QtWidgets.QTextEdit()
        self.info.setReadOnly(True)
        layout.addWidget(self.info)

        refresh_btn = QtWidgets.QPushButton("Ping API and List Products")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        self.setCentralWidget(central)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh_silent)
        self.timer.start(5000)

        self.refresh()

    def refresh(self):
        try:
            r = requests.get(self.api_url + "/")
            products = requests.get(self.api_url + "/api/products/all").json()
            self.info.setPlainText(f"API OK: {r.json()}\nProducts: {len(products)}")
            self.status.showMessage("Connected to API", 2000)
        except Exception as e:
            self.info.setPlainText(f"API error: {e}")
            self.status.showMessage("API error", 2000)

    def refresh_silent(self):
        try:
            requests.get(self.api_url + "/", timeout=1.0)
        except Exception:
            pass


def main():
    global _BACKEND_START_ERROR
    # If API_URL is provided, use an existing backend; otherwise start one in-process
    api_url = (os.environ.get("API_URL") or "").strip()
    if api_url:
        api_url = api_url.rstrip("/")
    else:
        # Launch API server on a dynamic port
        port = find_open_port()
        os.environ["PORT"] = str(port)
        api_url = f"http://127.0.0.1:{port}"

        t = threading.Thread(target=start_api_server, args=(port,), daemon=True)
        t.start()

        # Wait for server
        server_ready = False
        for _ in range(40):
            try:
                requests.get(api_url + "/", timeout=0.5)
                server_ready = True
                break
            except Exception:
                if _BACKEND_START_ERROR:
                    break
                time.sleep(0.1)
        if not server_ready and _BACKEND_START_ERROR:
            prepare_theme()
            app = QtWidgets.QApplication(sys.argv)
            apply_theme(app)
            QtWidgets.QMessageBox.critical(
                None,
                "Backend Startup Error",
                (
                    "PharmaSpot could not start its local API server.\n\n"
                    "A detailed log has been written to backend_startup.log "
                    "next to the executable."
                ),
            )
            return

    prepare_theme()
    app = QtWidgets.QApplication(sys.argv)
    apply_theme(app)
    icon_path = Path(__file__).resolve().parent / "assets" / "pharmaspot-icon-96.png"
    if icon_path.is_file():
        app.setWindowIcon(QtGui.QIcon(str(icon_path)))
    client = ApiClient(api_url)
    shell = PharmaApp(client)
    w = QtWidgets.QMainWindow()
    w.setWindowTitle("PharmaSpot")
    if icon_path.is_file():
        w.setWindowIcon(QtGui.QIcon(str(icon_path)))
    w.setCentralWidget(shell)
    w.resize(1280, 800)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
