from PyQt5 import QtWidgets, QtCore
from pathlib import Path
import sys
from .ui_common import apply_form_layout, apply_page_layout, polish_controls, set_accent, set_secondary
from .users import UsersView


class SettingsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._allow_settings = True
        self._allow_users = True
        self._users_loaded = False
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs, 1)

        # Business Setting
        business_tab = QtWidgets.QWidget()
        business_layout = QtWidgets.QVBoxLayout(business_tab)
        apply_page_layout(business_layout)
        form = QtWidgets.QFormLayout()
        apply_form_layout(form)
        self.business_name = QtWidgets.QLineEdit()
        self.business_name.setPlaceholderText("Business name")
        self.receipt_footer = QtWidgets.QLineEdit()
        self.receipt_footer.setPlaceholderText("Receipt footer note")
        self.vat_percent = QtWidgets.QDoubleSpinBox()
        self.vat_percent.setRange(0, 100)
        self.vat_percent.setDecimals(2)
        self.period_lock_enabled = QtWidgets.QCheckBox("Enable")
        self.period_lock_date = QtWidgets.QDateEdit()
        self.period_lock_date.setCalendarPopup(True)
        self.period_lock_date.setDisplayFormat("dd-MM-yyyy")
        self.period_lock_date.setDate(QtCore.QDate.currentDate())
        self.period_lock_date.setEnabled(False)
        self.period_lock_enabled.toggled.connect(self.period_lock_date.setEnabled)
        lock_wrap = QtWidgets.QWidget()
        lock_row = QtWidgets.QHBoxLayout(lock_wrap)
        lock_row.setContentsMargins(0, 0, 0, 0)
        lock_row.setSpacing(8)
        lock_row.addWidget(self.period_lock_enabled)
        lock_row.addWidget(self.period_lock_date)
        lock_row.addStretch(1)
        form.addRow("Business Name", self.business_name)
        form.addRow("Receipt Footer", self.receipt_footer)
        form.addRow("VAT %", self.vat_percent)
        form.addRow("Period Lock", lock_wrap)
        business_layout.addLayout(form)
        business_btns = QtWidgets.QHBoxLayout()
        self.btn_save_business = QtWidgets.QPushButton("Save")
        set_accent(self.btn_save_business)
        business_btns.addWidget(self.btn_save_business)
        business_btns.addStretch(1)
        business_layout.addLayout(business_btns)
        business_layout.addStretch(1)

        # Database Setting
        database_tab = QtWidgets.QWidget()
        database_layout = QtWidgets.QVBoxLayout(database_tab)
        apply_page_layout(database_layout)
        db_group = QtWidgets.QGroupBox("Database (MySQL)")
        db_form = QtWidgets.QFormLayout(db_group)
        apply_form_layout(db_form)
        self.db_engine = QtWidgets.QComboBox()
        self.db_engine.addItems(["mysql"])
        self.db_host = QtWidgets.QLineEdit()
        self.db_host.setPlaceholderText("e.g. localhost")
        self.db_port = QtWidgets.QSpinBox()
        self.db_port.setRange(1, 65535)
        self.db_port.setValue(3306)
        self.db_name = QtWidgets.QLineEdit()
        self.db_name.setPlaceholderText("Database name")
        self.db_user = QtWidgets.QLineEdit()
        self.db_user.setPlaceholderText("Database user")
        self.db_password = QtWidgets.QLineEdit()
        self.db_password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.db_password.setPlaceholderText("Database password")
        self.db_url = QtWidgets.QLineEdit()
        self.db_url.setPlaceholderText("Optional full SQLAlchemy URL (overrides above)")
        db_form.addRow("Engine", self.db_engine)
        db_form.addRow("Host", self.db_host)
        db_form.addRow("Port", self.db_port)
        db_form.addRow("Database", self.db_name)
        db_form.addRow("User", self.db_user)
        db_form.addRow("Password", self.db_password)
        db_form.addRow("DATABASE_URL", self.db_url)
        database_layout.addWidget(db_group)
        db_btns = QtWidgets.QHBoxLayout()
        self.btn_reload_db = QtWidgets.QPushButton("Reload")
        self.btn_save_db = QtWidgets.QPushButton("Save DB Settings (restart app after)")
        set_secondary(self.btn_reload_db)
        set_accent(self.btn_save_db)
        db_btns.addWidget(self.btn_reload_db)
        db_btns.addWidget(self.btn_save_db)
        db_btns.addStretch(1)
        database_layout.addLayout(db_btns)
        database_layout.addStretch(1)

        # User Setting
        self.user_tab = UsersView(self.api, auto_refresh=False)

        self._business_tab_index = self.tabs.addTab(business_tab, "Business Settings")
        self._database_tab_index = self.tabs.addTab(database_tab, "Database Setting")
        self._user_tab_index = self.tabs.addTab(self.user_tab, "User Setting")

        self.btn_save_business.clicked.connect(self.save)
        self.btn_reload_db.clicked.connect(self._load_db_env)
        self.btn_save_db.clicked.connect(self.save_db)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        polish_controls(self)

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
        try:
            lock_info = self.api.period_lock_get() or {}
        except Exception:
            lock_info = {}
        lock_until = str((lock_info or {}).get("lock_until", "") or "").strip()
        if bool((lock_info or {}).get("locked", False)) and lock_until:
            qd = QtCore.QDate.fromString(lock_until, "yyyy-MM-dd")
            if not qd.isValid():
                qd = QtCore.QDate.currentDate()
            self.period_lock_enabled.setChecked(True)
            self.period_lock_date.setDate(qd)
        else:
            self.period_lock_enabled.setChecked(False)
        self._load_db_env()
        if self._allow_users and self.tabs.currentIndex() == self._user_tab_index:
            self._refresh_users_tab()

    def set_user(self, user: dict):
        self._allow_settings = bool(user.get("perm_settings", False))
        self._allow_users = bool(user.get("perm_users", False))
        self._apply_tab_visibility()

    def _set_tab_visible(self, index: int, visible: bool):
        try:
            self.tabs.setTabVisible(index, visible)
        except Exception:
            try:
                self.tabs.tabBar().setTabVisible(index, visible)
            except Exception:
                self.tabs.setTabEnabled(index, visible)

    def _apply_tab_visibility(self):
        self._set_tab_visible(self._business_tab_index, self._allow_settings)
        self._set_tab_visible(self._database_tab_index, self._allow_settings)
        self._set_tab_visible(self._user_tab_index, self._allow_users)
        if self.tabs.currentIndex() == self._user_tab_index and not self._allow_users:
            if self._allow_settings:
                self.tabs.setCurrentIndex(self._business_tab_index)
            elif self._allow_users:
                self.tabs.setCurrentIndex(self._user_tab_index)
        if self.tabs.currentIndex() in (self._business_tab_index, self._database_tab_index) and not self._allow_settings:
            if self._allow_users:
                self.tabs.setCurrentIndex(self._user_tab_index)

    def _on_tab_changed(self, index: int):
        if index == self._user_tab_index and self._allow_users:
            self._refresh_users_tab()

    def _refresh_users_tab(self):
        try:
            self.user_tab.refresh()
            self._users_loaded = True
        except Exception:
            if self._users_loaded:
                raise

    def save(self):
        try:
            self.api.setting_set("business_name", self.business_name.text().strip())
            self.api.setting_set("receipt_footer", self.receipt_footer.text().strip())
            self.api.setting_set("vat_percent", str(self.vat_percent.value()))
            lock_until = self.period_lock_date.date().toString("yyyy-MM-dd") if self.period_lock_enabled.isChecked() else None
            self.api.period_lock_set(lock_until)
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
