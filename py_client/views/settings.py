from PyQt5 import QtWidgets
from pathlib import Path
import sys


class SettingsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Settings")
        title.setObjectName("title")
        layout.addWidget(title)

        form = QtWidgets.QFormLayout()
        self.business_name = QtWidgets.QLineEdit()
        self.receipt_footer = QtWidgets.QLineEdit()
        self.vat_percent = QtWidgets.QDoubleSpinBox(); self.vat_percent.setRange(0, 100); self.vat_percent.setDecimals(2)
        form.addRow("Business Name", self.business_name)
        form.addRow("Receipt Footer", self.receipt_footer)
        form.addRow("VAT %", self.vat_percent)
        layout.addLayout(form)

        db_group = QtWidgets.QGroupBox("Database (MySQL)")
        db_form = QtWidgets.QFormLayout(db_group)
        self.db_engine = QtWidgets.QComboBox(); self.db_engine.addItems(["mysql"])
        self.db_host = QtWidgets.QLineEdit(); self.db_host.setPlaceholderText("e.g. localhost")
        self.db_port = QtWidgets.QSpinBox(); self.db_port.setRange(1, 65535); self.db_port.setValue(3306)
        self.db_name = QtWidgets.QLineEdit()
        self.db_user = QtWidgets.QLineEdit()
        self.db_password = QtWidgets.QLineEdit(); self.db_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.db_url = QtWidgets.QLineEdit(); self.db_url.setPlaceholderText("Optional: full SQLAlchemy URL (overrides above)")
        db_form.addRow("Engine", self.db_engine)
        db_form.addRow("Host", self.db_host)
        db_form.addRow("Port", self.db_port)
        db_form.addRow("Database", self.db_name)
        db_form.addRow("User", self.db_user)
        db_form.addRow("Password", self.db_password)
        db_form.addRow("DATABASE_URL", self.db_url)
        layout.addWidget(db_group)

        btns = QtWidgets.QHBoxLayout()
        save = QtWidgets.QPushButton("Save")
        refresh = QtWidgets.QPushButton("Refresh")
        save_db = QtWidgets.QPushButton("Save DB Settings (restart app after)")
        btns.addWidget(save)
        btns.addWidget(refresh)
        btns.addWidget(save_db)
        btns.addStretch(1)
        layout.addLayout(btns)

        save.clicked.connect(self.save)
        refresh.clicked.connect(self.refresh)
        save_db.clicked.connect(self.save_db)

        layout.addStretch(1)

    def refresh(self):
        try:
            data = self.api.settings_map() or {}
            settings = data.get("settings", {}) if isinstance(data, dict) else {}
        except Exception:
            settings = {}
        self.business_name.setText(settings.get("business_name", ""))
        self.receipt_footer.setText(settings.get("receipt_footer", ""))
        try:
            self.vat_percent.setValue(float(settings.get("vat_percent", 0)))
        except Exception:
            self.vat_percent.setValue(0.0)
        self._load_db_env()

    def save(self):
        try:
            self.api.setting_set("business_name", self.business_name.text().strip())
            self.api.setting_set("receipt_footer", self.receipt_footer.text().strip())
            self.api.setting_set("vat_percent", str(self.vat_percent.value()))
            QtWidgets.QMessageBox.information(self, "Saved", "Settings saved")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    # ----- DB env helpers -----
    @property
    def _env_path(self) -> Path:
        # In a bundled exe, write .env next to the executable under python_backend/
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).resolve().parent / "python_backend"
        else:
            base = Path(__file__).resolve().parents[2] / "python_backend"
        base.mkdir(parents=True, exist_ok=True)
        return base / ".env"

    def _load_db_env(self):
        data = {}
        path = self._env_path
        if path.exists():
            try:
                for line in path.read_text().splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    data[key.strip()] = val.strip()
            except Exception:
                data = {}
        self.db_engine.setCurrentText((data.get("DB_ENGINE") or "mysql").lower())
        self.db_host.setText(data.get("DB_HOST", ""))
        try:
            self.db_port.setValue(int(data.get("DB_PORT", "3306") or 3306))
        except Exception:
            self.db_port.setValue(3306)
        self.db_name.setText(data.get("DB_NAME", ""))
        self.db_user.setText(data.get("DB_USER", ""))
        self.db_password.setText(data.get("DB_PASSWORD", ""))
        self.db_url.setText(data.get("DATABASE_URL", ""))

    def save_db(self):
        engine = self.db_engine.currentText().strip() or "mysql"
        host = self.db_host.text().strip()
        name = self.db_name.text().strip()
        user = self.db_user.text().strip()
        pwd = self.db_password.text()
        port = str(self.db_port.value())
        url = self.db_url.text().strip()
        lines = [
            "# Auto-generated DB settings (restart app to apply)",
            f"DB_ENGINE={engine}",
            f"DB_HOST={host}",
            f"DB_PORT={port}",
            f"DB_NAME={name}",
            f"DB_USER={user}",
            f"DB_PASSWORD={pwd}",
        ]
        if url:
            lines.append(f"DATABASE_URL={url}")
        path = self._env_path
        try:
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            QtWidgets.QMessageBox.information(
                self,
                "Saved",
                f"DB settings saved to {path}.\nPlease restart the app to reconnect with the new database.",
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Could not write DB settings: {e}")
