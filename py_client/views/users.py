from PyQt5 import QtWidgets


class UsersView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Users")
        title.setObjectName("title")
        header.addWidget(title)
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_add = QtWidgets.QPushButton("Add User")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_add)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Username", "Fullname"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_add.clicked.connect(self.add_user_dialog)

    def refresh(self):
        try:
            users = self.api.users_all()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return

        self.table.setRowCount(0)
        for u in users:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(u.get("id"))))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(u.get("username", "")))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem(u.get("fullname", "")))

    def add_user_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add User")
        form = QtWidgets.QFormLayout(d)
        username = QtWidgets.QLineEdit()
        fullname = QtWidgets.QLineEdit()
        password = QtWidgets.QLineEdit(); password.setEchoMode(QtWidgets.QLineEdit.Password)
        p_products = QtWidgets.QCheckBox()
        p_transactions = QtWidgets.QCheckBox()
        p_users = QtWidgets.QCheckBox()
        p_settings = QtWidgets.QCheckBox()
        form.addRow("Username", username)
        form.addRow("Fullname", fullname)
        form.addRow("Password", password)
        form.addRow("Products", p_products)
        form.addRow("Transactions", p_transactions)
        form.addRow("Users", p_users)
        form.addRow("Settings", p_settings)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "username": username.text().strip(),
                "fullname": fullname.text().strip(),
                "password": password.text(),
                "perm_products": p_products.isChecked(),
                "perm_transactions": p_transactions.isChecked(),
                "perm_users": p_users.isChecked(),
                "perm_settings": p_settings.isChecked(),
            }
            try:
                self.api.user_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
