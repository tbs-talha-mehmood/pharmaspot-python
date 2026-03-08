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
        self.btn_delete = QtWidgets.QPushButton("Deactivate")
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

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Inventory (Cost)"])
        configure_table(self.table, stretch_last=False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
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
        self.investment_label = QtWidgets.QLabel("Realtime Inventory Investment: 0.00")
        self.investment_label.setObjectName("moneyStrong")
        pager.addWidget(self.investment_label)
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
        self.table.itemSelectionChanged.connect(self._sync_action_state)
        self._sync_action_state()

    def focus_search(self):
        self.search.setFocus(QtCore.Qt.OtherFocusReason)
        self.search.selectAll()

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QtCore.QEvent.FocusIn:
            QtCore.QTimer.singleShot(0, self.search.selectAll)
        return super().eventFilter(obj, event)

    def _sync_action_state(self):
        selected = self._selected_company()
        has_sel = selected is not None
        is_active = bool((selected or {}).get("is_active", True))
        self.btn_edit.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_delete.setText("Reactivate" if (has_sel and not is_active) else "Deactivate")
        if has_sel and not is_active:
            self.btn_delete.setProperty("danger", False)
            self.btn_delete.setProperty("accent", True)
        else:
            self.btn_delete.setProperty("accent", False)
            self.btn_delete.setProperty("danger", True)
        self.btn_delete.style().unpolish(self.btn_delete)
        self.btn_delete.style().polish(self.btn_delete)
        self.btn_delete.update()
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
            inv_data = self.api.company_inventory(
                include_inactive=self.chk_inactive.isChecked(),
                q=self.search.text().strip(),
            )
            inv_rows = list((inv_data or {}).get("items") or [])
            inv_map = {int(r.get("company_id", 0) or 0): r for r in inv_rows}
            total_val = float(((inv_data or {}).get("summary") or {}).get("total_value", 0.0) or 0.0)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.table.setRowCount(0)
        for c in items or []:
            cid = int(c.get("id", 0) or 0)
            inv = dict(inv_map.get(cid) or {})
            val = float(inv.get("inventory_value", 0.0) or 0.0)
            r = self.table.rowCount()
            self.table.insertRow(r)
            id_item = QtWidgets.QTableWidgetItem(str(cid))
            id_item.setData(QtCore.Qt.UserRole, dict(c) if isinstance(c, dict) else {})
            self.table.setItem(r, 0, id_item)
            name_item = QtWidgets.QTableWidgetItem(c.get("name", ""))
            self.table.setItem(r, 1, name_item)
            val_item = QtWidgets.QTableWidgetItem(f"{val:.2f}")
            val_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            self.table.setItem(r, 2, val_item)
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.investment_label.setText(f"Realtime Inventory Investment: {total_val:.2f}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)
        self._sync_action_state()

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
        meta = cid_item.data(QtCore.Qt.UserRole)
        if isinstance(meta, dict):
            try:
                mid = int(meta.get("id", cid) or cid)
            except Exception:
                mid = cid
            return {"id": mid, "name": str(meta.get("name", name_item.text() or "")), "is_active": bool(meta.get("is_active", True))}
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
        is_active = bool(selected.get("is_active", True))
        try:
            if is_active:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Deactivate this company?") != QtWidgets.QMessageBox.Yes:
                    return
                self.api.company_delete(int(selected["id"]))
                QtWidgets.QMessageBox.information(self, "Deactivated", "Company has been deactivated.")
            else:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Reactivate this company?") != QtWidgets.QMessageBox.Yes:
                    return
                payload = {"id": int(selected["id"]), "name": str(selected.get("name", "") or "")}
                resp = self.api.company_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                QtWidgets.QMessageBox.information(self, "Reactivated", "Company has been reactivated.")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))







