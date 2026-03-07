from PyQt5 import QtWidgets, QtCore
from .ui_common import (
    apply_form_layout,
    apply_header_layout,
    apply_page_layout,
    configure_table,
    fit_dialog_to_contents,
    polish_controls,
    set_accent,
    set_danger,
    set_secondary,
)


class CompaniesView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._page = 1
        self._pages = 1
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)
        header = QtWidgets.QHBoxLayout()
        apply_header_layout(header)
        self.chk_inactive = QtWidgets.QCheckBox("Show inactive")
        self.btn_add = QtWidgets.QPushButton("Add Company")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        set_secondary(self.btn_edit)
        set_accent(self.btn_add)
        set_danger(self.btn_delete)
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        header.addWidget(self.chk_inactive)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search by name")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(320)
        self.search.installEventFilter(self)
        header.addWidget(self.search)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["ID", "Name"])
        configure_table(self.table)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self.table)

        pager = QtWidgets.QHBoxLayout()
        self.btn_prev = QtWidgets.QPushButton("Prev")
        self.btn_next = QtWidgets.QPushButton("Next")
        set_secondary(self.btn_prev, self.btn_next)
        self.page_label = QtWidgets.QLabel("Page 1 / 1")
        self.page_label.setObjectName("mutedLabel")
        pager.addWidget(self.btn_prev)
        pager.addWidget(self.btn_next)
        pager.addWidget(self.page_label)
        pager.addStretch(1)
        layout.addLayout(pager)

        self.btn_add.clicked.connect(self.add_dialog)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.chk_inactive.stateChanged.connect(self._on_filter_changed)
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self._on_search_changed)
        polish_controls(self)

    def focus_search(self):
        self.search.setFocus(QtCore.Qt.OtherFocusReason)
        self.search.selectAll()

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QtCore.QEvent.FocusIn:
            QtCore.QTimer.singleShot(0, self.search.selectAll)
        return super().eventFilter(obj, event)

    def _on_search_changed(self):
        self._search_timer.stop()
        if len(self.search.text().strip()) >= 3:
            self._search_timer.start()
        else:
            self._page = 1
            self.refresh()

    def _on_filter_changed(self):
        self._page = 1
        self.refresh()

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self.refresh()

    def _next_page(self):
        if self._page < self._pages:
            self._page += 1
            self.refresh()

    def refresh(self):
        try:
            data = self.api.companies_page(
                include_inactive=self.chk_inactive.isChecked(),
                q=self.search.text().strip(),
                page=self._page,
                page_size=25,
            )
            items = data.get("items", [])
            self._pages = int(data.get("pages", 1) or 1)
            self._page = max(1, min(int(data.get("page", self._page) or self._page), self._pages))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.table.setRowCount(0)
        for c in items or []:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(c.get("id"))))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(c.get("name", "")))
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)

    def add_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add Company")
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        name.setPlaceholderText("Company name")
        form.addRow("Name", name)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=420, fixed=True)
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
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        name.setText(selected.get("name", ""))
        form.addRow("Name", name)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=420, fixed=True)
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
