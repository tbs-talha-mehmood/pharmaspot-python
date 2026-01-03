from PyQt5 import QtWidgets


class SettingsView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Settings")
        title.setStyleSheet("font-size:16px;font-weight:bold")
        layout.addWidget(title)

        form = QtWidgets.QFormLayout()
        self.business_name = QtWidgets.QLineEdit()
        self.receipt_footer = QtWidgets.QLineEdit()
        self.vat_percent = QtWidgets.QDoubleSpinBox(); self.vat_percent.setRange(0, 100); self.vat_percent.setDecimals(2)
        form.addRow("Business Name", self.business_name)
        form.addRow("Receipt Footer", self.receipt_footer)
        form.addRow("VAT %", self.vat_percent)
        layout.addLayout(form)

        btns = QtWidgets.QHBoxLayout()
        save = QtWidgets.QPushButton("Save")
        refresh = QtWidgets.QPushButton("Refresh")
        btns.addWidget(save)
        btns.addWidget(refresh)
        btns.addStretch(1)
        layout.addLayout(btns)

        save.clicked.connect(self.save)
        refresh.clicked.connect(self.refresh)

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

    def save(self):
        try:
            self.api.setting_set("business_name", self.business_name.text().strip())
            self.api.setting_set("receipt_footer", self.receipt_footer.text().strip())
            self.api.setting_set("vat_percent", str(self.vat_percent.value()))
            QtWidgets.QMessageBox.information(self, "Saved", "Settings saved")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

