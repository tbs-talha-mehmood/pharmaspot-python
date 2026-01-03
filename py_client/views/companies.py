from PyQt5 import QtWidgets


class CompaniesView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        header = QtWidgets.QHBoxLayout()
        self.chk_inactive = QtWidgets.QCheckBox("Show inactive")
        header.addWidget(QtWidgets.QLabel("Companies"))
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_add = QtWidgets.QPushButton("Add Company")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        header.addWidget(self.chk_inactive)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["ID", "Name"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_add.clicked.connect(self.add_dialog)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.chk_inactive.stateChanged.connect(self.refresh)

    def refresh(self):
        try:
            items = self.api.companies(include_inactive=self.chk_inactive.isChecked())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.table.setRowCount(0)
        for c in items or []:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(c.get("id"))))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(c.get("name", "")))

    def add_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add Company")
        form = QtWidgets.QFormLayout(d)
        name = QtWidgets.QLineEdit()
        form.addRow("Name", name)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {"name": name.text().strip()}
            try:
                resp = self.api.company_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _selected_company(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        cid_item = self.table.item(r, 0)
        name_item = self.table.item(r, 1)
        if not cid_item or not name_item:
            return None
        try:
            cid = int(cid_item.text())
        except Exception:
            return None
        return {"id": cid, "name": name_item.text()}

    def edit_selected(self):
        selected = self._selected_company()
        if not selected:
            QtWidgets.QMessageBox.information(self, "Select", "Select a company row first")
            return
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Edit Company")
        form = QtWidgets.QFormLayout(d)
        name = QtWidgets.QLineEdit()
        name.setText(selected.get("name", ""))
        form.addRow("Name", name)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {"id": selected["id"], "name": name.text().strip()}
            try:
                resp = self.api.company_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def delete_selected(self):
        selected = self._selected_company()
        if not selected:
            QtWidgets.QMessageBox.information(self, "Select", "Select a company row first")
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this company?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            self.api.company_delete(int(selected["id"]))
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
