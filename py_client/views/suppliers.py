from datetime import datetime

from PyQt5 import QtWidgets, QtCore, QtGui

from .ui_common import (
    apply_form_layout,
    apply_header_layout,
    apply_page_layout,
    configure_table,
    dialog_screen_limits,
    fit_dialog_to_contents,
    polish_controls,
    set_accent,
    set_danger,
    set_secondary,
)


class SuppliersView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user_id = 0
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
        self.btn_add = QtWidgets.QPushButton("Add Supplier")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_profile = QtWidgets.QPushButton("Profile")
        self.btn_delete = QtWidgets.QPushButton("Deactivate")
        set_secondary(self.btn_edit, self.btn_profile)
        set_accent(self.btn_add)
        set_danger(self.btn_delete)
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_profile)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        header.addWidget(self.chk_inactive)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search supplier by name")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(320)
        self.search.installEventFilter(self)
        header.addWidget(self.search)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Invoices", "Purchased", "Paid", "Due"])
        configure_table(self.table, stretch_last=False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
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
        self.btn_profile.clicked.connect(self.open_profile_selected)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.table.itemDoubleClicked.connect(lambda _item: self.open_profile_selected())
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.chk_inactive.stateChanged.connect(self._on_filter_changed)
        self.table.itemSelectionChanged.connect(self._sync_action_state)
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self._on_search_changed)
        polish_controls(self)
        self._sync_action_state()

    def set_user(self, user: dict):
        try:
            self.user_id = int((user or {}).get("id", 0) or 0)
        except Exception:
            self.user_id = 0

    def focus_search(self):
        self.search.setFocus(QtCore.Qt.OtherFocusReason)
        self.search.selectAll()

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QtCore.QEvent.FocusIn:
            QtCore.QTimer.singleShot(0, self.search.selectAll)
        return super().eventFilter(obj, event)

    def _to_float(self, value, default: float = 0.0) -> float:
        try:
            return float(value if value is not None else default)
        except Exception:
            return float(default)

    def _to_int(self, value, default: int = 0) -> int:
        try:
            return int(value if value is not None else default)
        except Exception:
            return int(default)

    def _split_datetime(self, raw_value):
        dt = str(raw_value or "").strip()
        if not dt:
            return "", ""
        try:
            parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            return parsed.strftime("%d-%m-%Y"), parsed.strftime("%H:%M:%S")
        except Exception:
            normalized = dt.replace("T", " ")
            parts = normalized.split()
            date_txt = parts[0] if parts else normalized
            try:
                date_txt = datetime.strptime(date_txt, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                pass
            time_txt = ""
            if len(parts) > 1:
                time_txt = parts[1]
                if "." in time_txt:
                    time_txt = time_txt.split(".", 1)[0]
                if len(time_txt) > 8 and time_txt[8] in ("+", "-"):
                    time_txt = time_txt[:8]
            return date_txt, time_txt

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

    def _sync_action_state(self):
        selected = self._selected_supplier()
        has_sel = selected is not None
        is_active = bool((selected or {}).get("is_active", True))
        self.btn_edit.setEnabled(has_sel)
        self.btn_profile.setEnabled(has_sel)
        self.btn_delete.setEnabled(has_sel)
        self.btn_edit.setText("Edit")
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

    def refresh(self):
        try:
            data = self.api.suppliers_page(
                include_inactive=self.chk_inactive.isChecked(),
                q=self.search.text().strip(),
                page=self._page,
                page_size=25,
            )
            items = list(data.get("items", []) or [])
            self._pages = int(data.get("pages", 1) or 1)
            self._page = max(1, min(int(data.get("page", self._page) or self._page), self._pages))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return

        self.table.setRowCount(0)
        for s in items:
            sid = self._to_int(s.get("id", 0), 0)
            name = str(s.get("name", "") or "")
            is_active = bool(s.get("is_active", True))
            inv_count = self._to_int(s.get("invoice_count", 0), 0)
            total_purchased = max(0.0, self._to_float(s.get("total_purchased", 0.0), 0.0))
            total_paid = max(0.0, self._to_float(s.get("total_paid", 0.0), 0.0))
            total_due = max(0.0, self._to_float(s.get("total_due", 0.0), 0.0))

            r = self.table.rowCount()
            self.table.insertRow(r)
            id_item = QtWidgets.QTableWidgetItem(str(sid))
            name_item = QtWidgets.QTableWidgetItem(name if is_active else f"{name} (Inactive)")
            id_item.setData(QtCore.Qt.UserRole, dict(s))
            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, name_item)
            inv_item = QtWidgets.QTableWidgetItem(str(inv_count))
            inv_item.setTextAlignment(QtCore.Qt.AlignCenter)
            purch_item = QtWidgets.QTableWidgetItem(f"{total_purchased:.2f}")
            paid_item = QtWidgets.QTableWidgetItem(f"{total_paid:.2f}")
            due_item = QtWidgets.QTableWidgetItem(f"{total_due:.2f}")
            for itm in (purch_item, paid_item, due_item):
                itm.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            if total_due > 0.0:
                due_item.setForeground(QtGui.QBrush(QtGui.QColor("#F87171")))
            if not is_active:
                fade = QtGui.QBrush(QtGui.QColor("#7C8DA6"))
                for itm in (id_item, name_item, inv_item, purch_item, paid_item):
                    itm.setForeground(fade)
            self.table.setItem(r, 2, inv_item)
            self.table.setItem(r, 3, purch_item)
            self.table.setItem(r, 4, paid_item)
            self.table.setItem(r, 5, due_item)

        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)
        self._sync_action_state()

    def _selected_supplier(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        sid_item = self.table.item(r, 0)
        name_item = self.table.item(r, 1)
        if not sid_item or not name_item:
            return None
        meta = sid_item.data(QtCore.Qt.UserRole)
        if isinstance(meta, dict):
            sid = self._to_int(meta.get("id", 0), 0)
            if sid <= 0:
                return None
            return {
                "id": sid,
                "name": str(meta.get("name", "") or ""),
                "is_active": bool(meta.get("is_active", True)),
            }
        try:
            sid = int(sid_item.text())
        except Exception:
            return None
        nm = str(name_item.text() or "")
        if nm.endswith(" (Inactive)"):
            nm = nm[: -len(" (Inactive)")].strip()
        return {"id": sid, "name": nm, "is_active": True}

    def add_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add Supplier")
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        name.setPlaceholderText("Supplier name")
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
                resp = self.api.supplier_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def edit_selected(self):
        selected = self._selected_supplier()
        if not selected:
            QtWidgets.QMessageBox.information(self, "Select", "Select a supplier row first")
            return
        was_inactive = not bool(selected.get("is_active", True))
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Edit Supplier")
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
                resp = self.api.supplier_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
    def delete_selected(self):
        selected = self._selected_supplier()
        if not selected:
            QtWidgets.QMessageBox.information(self, "Select", "Select a supplier row first")
            return
        is_active = bool(selected.get("is_active", True))
        try:
            if is_active:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Deactivate this supplier?") != QtWidgets.QMessageBox.Yes:
                    return
                resp = self.api.supplier_delete(int(selected["id"]))
                if isinstance(resp, dict) and str(resp.get("detail", "")).strip():
                    QtWidgets.QMessageBox.information(self, "Deactivate blocked", str(resp.get("detail", "")).strip())
                    return
                QtWidgets.QMessageBox.information(self, "Deactivated", "Supplier has been deactivated.")
            else:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Reactivate this supplier?") != QtWidgets.QMessageBox.Yes:
                    return
                payload = {"id": int(selected["id"]), "name": str(selected.get("name", "") or "")}
                resp = self.api.supplier_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                QtWidgets.QMessageBox.information(self, "Reactivated", "Supplier has been reactivated.")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def open_profile_selected(self):
        supplier = self._selected_supplier()
        if not supplier:
            QtWidgets.QMessageBox.information(self, "Select", "Select a supplier row first")
            return
        sid = int(supplier.get("id", 0) or 0)
        sname = str(supplier.get("name", "") or "Supplier")
        if sid <= 0:
            QtWidgets.QMessageBox.information(self, "Select", "Invalid supplier")
            return

        max_dlg_w, max_dlg_h = dialog_screen_limits(
            width_ratio=0.92,
            height_ratio=0.90,
            fallback_width=1120,
            fallback_height=760,
        )
        row_h = 32
        chrome_h = 280
        inv_col_widths = {
            0: 116,   # PO #
            1: 92,  # Date
            2: 96,   # Time
            3: 110,  # Total
            4: 110,  # Paid
            5: 160,  # Due
        }
        pay_col_widths = {
            0: 116,  # Date
            1: 92,   # Time
            2: 96,   # PO #
            3: 110,  # Amount
            4: 110,  # Paid Total
            5: 160,  # User
            6: 0,    # Payment ID (hidden, zero-width)
        }

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Supplier Profile - {sname}")
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        title = QtWidgets.QLabel(f"{sname} (ID: {sid})")
        title.setObjectName("moneyStrong")
        v.addWidget(title)

        # Summary
        summary_row = QtWidgets.QHBoxLayout()
        apply_header_layout(summary_row)
        summary_row.setSpacing(24)
        inv_lbl = QtWidgets.QLabel("Invoices: 0")
        total_lbl = QtWidgets.QLabel("Total: 0.00")
        paid_lbl = QtWidgets.QLabel("Paid: 0.00")
        due_lbl = QtWidgets.QLabel("Merged Due: 0.00")
        due_lbl.setObjectName("moneyStrong")
        summary_row.addWidget(inv_lbl)
        summary_row.addWidget(total_lbl)
        summary_row.addWidget(paid_lbl)
        summary_row.addWidget(due_lbl)
        summary_row.addStretch(1)
        v.addLayout(summary_row)

        # Invoices table
        invoices_table = QtWidgets.QTableWidget(0, 6)
        invoices_table.setHorizontalHeaderLabels(["PO #", "Date", "Time", "Total", "Paid", "Due"])
        configure_table(invoices_table, stretch_last=False)
        invoices_table.verticalHeader().setDefaultSectionSize(row_h)
        invoices_table.setWordWrap(False)
        invoices_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        invoices_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        ih = invoices_table.horizontalHeader()
        for col in range(6):
            ih.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
            invoices_table.setColumnWidth(col, inv_col_widths[col])
        v.addWidget(invoices_table)

        info_lbl = QtWidgets.QLabel("Merged payments are auto-allocated to oldest due purchase invoices.")
        info_lbl.setObjectName("mutedLabel")
        v.addWidget(info_lbl)

        # Payments table
        payments_title = QtWidgets.QLabel("Payment History (Installments)")
        payments_title.setObjectName("mutedLabel")
        v.addWidget(payments_title)

        payments_table = QtWidgets.QTableWidget(0, 7)
        payments_table.setHorizontalHeaderLabels(["Date", "Time", "PO #", "Amount", "Paid Total", "User", "Payment ID"])
        payments_table.setColumnHidden(6, True)
        configure_table(payments_table, stretch_last=False)
        payments_table.verticalHeader().setDefaultSectionSize(row_h)
        payments_table.setWordWrap(False)
        payments_table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        payments_table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        ph = payments_table.horizontalHeader()
        for col in range(7):
            ph.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
            payments_table.setColumnWidth(col, pay_col_widths[col])
        v.addWidget(payments_table)

        inv_overflow_lbl = QtWidgets.QLabel("")
        inv_overflow_lbl.setObjectName("mutedLabel")
        inv_overflow_lbl.setVisible(False)
        v.addWidget(inv_overflow_lbl)

        pay_overflow_lbl = QtWidgets.QLabel("")
        pay_overflow_lbl.setObjectName("mutedLabel")
        pay_overflow_lbl.setVisible(False)
        v.addWidget(pay_overflow_lbl)

        state = {"due_total": 0.0, "user_map": {}}

        def _fit_tables():
            # Keep invoice and payment tables aligned and scrollable even with many rows.
            max_visible_rows = 12
            base_w = max(
                sum(inv_col_widths.values()),
                sum(pay_col_widths[c] for c in range(7) if c != 6),
            )

            inv_frame = invoices_table.frameWidth() * 2 + 2
            inv_table_w = base_w + inv_frame
            inv_rows = min(invoices_table.rowCount(), max_visible_rows)
            inv_table_h = (
                invoices_table.frameWidth() * 2
                + invoices_table.horizontalHeader().height()
                + (inv_rows * row_h)
                + 2
            )
            invoices_table.setFixedSize(inv_table_w, inv_table_h)

            pay_frame = payments_table.frameWidth() * 2 + 2
            pay_table_w = base_w + pay_frame
            pay_rows = min(payments_table.rowCount(), max_visible_rows)
            pay_table_h = (
                payments_table.frameWidth() * 2
                + payments_table.horizontalHeader().height()
                + (pay_rows * row_h)
                + 2
            )
            payments_table.setFixedSize(pay_table_w, pay_table_h)

            dlg.adjustSize()
            target_w = min(max_dlg_w, dlg.sizeHint().width())
            target_h = min(max_dlg_h, dlg.sizeHint().height())
            dlg.setFixedSize(target_w, target_h)

        def _load_user_map():
            m = {}
            try:
                for u in self.api.users_all() or []:
                    uid = int((u or {}).get("id", 0) or 0)
                    if uid > 0:
                        name = str(u.get("fullname", "") or u.get("username", "") or f"User {uid}")
                        m[uid] = name
            except Exception:
                pass
            state["user_map"] = m

        def _user_name(uid: int) -> str:
            try:
                return str(state.get("user_map", {}).get(int(uid or 0), f"User {int(uid or 0)}"))
            except Exception:
                return ""

        def _refresh_profile():
            try:
                inv_rows = self.api.supplier_purchases(sid) or []
                pay_rows = self.api.supplier_payments(sid) or []
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Error", str(e))
                return False
            if isinstance(inv_rows, dict) and str(inv_rows.get("detail", "")).strip():
                QtWidgets.QMessageBox.information(dlg, "Supplier", str(inv_rows.get("detail", "")).strip())
                inv_rows = []
            if isinstance(pay_rows, dict) and str(pay_rows.get("detail", "")).strip():
                QtWidgets.QMessageBox.information(dlg, "Payments", str(pay_rows.get("detail", "")).strip())
                pay_rows = []

            inv_rows = list(inv_rows or [])
            pay_rows = list(pay_rows or [])
            inv_rows.sort(key=lambda row: str(row.get("date", "") or ""), reverse=True)
            pay_rows.sort(key=lambda row: int((row or {}).get("id", 0) or 0), reverse=True)

            invoices_table.setRowCount(0)
            payments_table.setRowCount(0)

            total_invoice = 0.0
            total_paid = 0.0
            total_due = 0.0
            for row in inv_rows:
                total_amt = max(0.0, self._to_float(row.get("total", 0.0), 0.0))
                paid_amt = max(0.0, self._to_float(row.get("paid", 0.0), 0.0))
                due_amt = max(0.0, total_amt - paid_amt)
                total_invoice += total_amt
                total_paid += paid_amt
                total_due += due_amt
            inv_lbl.setText(f"Invoices: {len(inv_rows)}")
            total_lbl.setText(f"Total: {total_invoice:.2f}")
            paid_lbl.setText(f"Paid: {total_paid:.2f}")
            due_lbl.setText(f"Merged Due: {total_due:.2f}")
            state["due_total"] = float(total_due)

            # Show all rows; dialog height is capped by _fit_tables and tables become scrollable.
            inv_rows_budget = len(inv_rows)
            pay_rows_budget = len(pay_rows)

            # Fill invoices
            visible_inv_rows = inv_rows[:inv_rows_budget]
            hidden_inv = max(0, len(inv_rows) - len(visible_inv_rows))
            for row in visible_inv_rows:
                po_id = int((row or {}).get("id", 0) or 0)
                total_amt = max(0.0, self._to_float(row.get("total", 0.0), 0.0))
                paid_amt = max(0.0, self._to_float(row.get("paid", 0.0), 0.0))
                due_amt = max(0.0, total_amt - paid_amt)
                date_txt, time_txt = self._split_datetime(row.get("date", ""))

                rr = invoices_table.rowCount()
                invoices_table.insertRow(rr)
                po_item = QtWidgets.QTableWidgetItem(str(po_id))
                date_item = QtWidgets.QTableWidgetItem(date_txt)
                time_item = QtWidgets.QTableWidgetItem(time_txt)
                t_item = QtWidgets.QTableWidgetItem(f"{total_amt:.2f}")
                p_item = QtWidgets.QTableWidgetItem(f"{paid_amt:.2f}")
                d_item = QtWidgets.QTableWidgetItem(f"{due_amt:.2f}")
                po_item.setTextAlignment(QtCore.Qt.AlignCenter)
                date_item.setTextAlignment(QtCore.Qt.AlignCenter)
                time_item.setTextAlignment(QtCore.Qt.AlignCenter)
                t_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                p_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                d_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                if due_amt > 1e-9:
                    d_item.setForeground(QtGui.QBrush(QtGui.QColor("#F87171")))
                invoices_table.setItem(rr, 0, po_item)
                invoices_table.setItem(rr, 1, date_item)
                invoices_table.setItem(rr, 2, time_item)
                invoices_table.setItem(rr, 3, t_item)
                invoices_table.setItem(rr, 4, p_item)
                invoices_table.setItem(rr, 5, d_item)
            if hidden_inv > 0:
                inv_overflow_lbl.setText(
                    f"Showing latest {len(visible_inv_rows)} of {len(inv_rows)} invoices to fit screen without scrolling."
                )
                inv_overflow_lbl.setVisible(True)
            else:
                inv_overflow_lbl.setVisible(False)

            # Fill payments
            _load_user_map()
            visible_pay_rows = pay_rows[:pay_rows_budget]
            hidden_pay = max(0, len(pay_rows) - len(visible_pay_rows))
            for row in visible_pay_rows:
                rr = payments_table.rowCount()
                payments_table.insertRow(rr)
                date_txt, time_txt = self._split_datetime(row.get("date", ""))
                po_id = int((row or {}).get("purchase_id", 0) or 0)
                amount = self._to_float(row.get("amount", 0.0), 0.0)
                paid_total = self._to_float(row.get("paid_total", 0.0), 0.0)
                uid = int((row or {}).get("user_id", 0) or 0)
                pid = int((row or {}).get("id", 0) or 0)
                date_item = QtWidgets.QTableWidgetItem(date_txt)
                time_item = QtWidgets.QTableWidgetItem(time_txt)
                po_item = QtWidgets.QTableWidgetItem(str(po_id))
                amount_item = QtWidgets.QTableWidgetItem(f"{amount:.2f}")
                paid_total_item = QtWidgets.QTableWidgetItem(f"{paid_total:.2f}")
                user_item = QtWidgets.QTableWidgetItem(_user_name(uid))
                id_item = QtWidgets.QTableWidgetItem(str(pid))
                date_item.setTextAlignment(QtCore.Qt.AlignCenter)
                time_item.setTextAlignment(QtCore.Qt.AlignCenter)
                po_item.setTextAlignment(QtCore.Qt.AlignCenter)
                amount_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                paid_total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                payments_table.setItem(rr, 0, date_item)
                payments_table.setItem(rr, 1, time_item)
                payments_table.setItem(rr, 2, po_item)
                payments_table.setItem(rr, 3, amount_item)
                payments_table.setItem(rr, 4, paid_total_item)
                payments_table.setItem(rr, 5, user_item)
                payments_table.setItem(rr, 6, id_item)
            if hidden_pay > 0:
                pay_overflow_lbl.setText(
                    f"Showing latest {len(visible_pay_rows)} of {len(pay_rows)} installments to fit screen without scrolling."
                )
                pay_overflow_lbl.setVisible(True)
            else:
                pay_overflow_lbl.setVisible(False)

            _fit_tables()
            self.refresh()
            return True

        def _pay_supplier():
            due_total = float(state.get("due_total", 0.0) or 0.0)
            if due_total <= 1e-9:
                QtWidgets.QMessageBox.information(dlg, "Payment", "No due purchase invoices for this supplier.")
                return
            amount, ok = QtWidgets.QInputDialog.getDouble(
                dlg,
                "Pay Supplier",
                "Enter payment amount:",
                value=due_total,
                min=0.01,
                max=due_total,
                decimals=2,
            )
            if not ok:
                return
            try:
                resp = self.api.supplier_payment_apply(sid, float(amount), user_id=int(self.user_id or 0))
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("supplier_id"):
                QtWidgets.QMessageBox.information(dlg, "Payment", str(resp.get("detail")))
                return
            applied = self._to_float((resp or {}).get("total_applied", 0.0), 0.0)
            remaining = self._to_float((resp or {}).get("total_due_after", 0.0), 0.0)
            alloc_count = len((resp or {}).get("allocations", []) or [])
            QtWidgets.QMessageBox.information(
                dlg,
                "Payment Applied",
                f"Applied {applied:.2f} across {alloc_count} invoice(s).`nRemaining merged due: {remaining:.2f}",
            )
            _refresh_profile()

        def _edit_selected_payment():
            rr = payments_table.currentRow()
            if rr < 0:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Select a payment row first.")
                return
            id_item = payments_table.item(rr, 6)
            po_item = payments_table.item(rr, 2)
            amt_item = payments_table.item(rr, 3)
            if not id_item or not po_item or not amt_item:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Invalid payment row.")
                return
            try:
                payment_id = int(id_item.text() or 0)
            except Exception:
                payment_id = 0
            try:
                purchase_id = int(po_item.text() or 0)
            except Exception:
                purchase_id = 0
            if payment_id <= 0 or purchase_id <= 0:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Invalid payment selection.")
                return
            try:
                current_amount = float((amt_item.text() or "0").replace("+", ""))
            except Exception:
                current_amount = 0.0
            new_amount, ok = QtWidgets.QInputDialog.getDouble(
                dlg,
                "Edit Payment",
                "Payment amount:",
                value=current_amount,
                min=0.0,
                max=10**12,
                decimals=2,
            )
            if not ok:
                return
            try:
                resp = self.api.purchase_payment_update(purchase_id, payment_id, float(new_amount))
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                QtWidgets.QMessageBox.information(dlg, "Payments", str(resp.get("detail")))
                return
            _refresh_profile()

        def _delete_selected_payment():
            rr = payments_table.currentRow()
            if rr < 0:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Select a payment row first.")
                return
            id_item = payments_table.item(rr, 6)
            po_item = payments_table.item(rr, 2)
            if not id_item or not po_item:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Invalid payment row.")
                return
            try:
                payment_id = int(id_item.text() or 0)
                purchase_id = int(po_item.text() or 0)
            except Exception:
                payment_id = 0
                purchase_id = 0
            if payment_id <= 0 or purchase_id <= 0:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Invalid payment selection.")
                return
            if QtWidgets.QMessageBox.question(dlg, "Confirm", "Delete this payment entry?") != QtWidgets.QMessageBox.Yes:
                return
            try:
                resp = self.api.purchase_payment_delete(purchase_id, payment_id)
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                QtWidgets.QMessageBox.information(dlg, "Payments", str(resp.get("detail")))
                return
            _refresh_profile()

        # Footer buttons
        btn_row = QtWidgets.QHBoxLayout()
        apply_header_layout(btn_row)
        pay_btn = QtWidgets.QPushButton("Pay Supplier")
        edit_btn = QtWidgets.QPushButton("Edit Selected")
        delete_btn = QtWidgets.QPushButton("Delete Selected")
        close_btn = QtWidgets.QPushButton("Close")
        set_accent(pay_btn)
        set_secondary(edit_btn, delete_btn, close_btn)
        pay_btn.clicked.connect(_pay_supplier)
        edit_btn.clicked.connect(_edit_selected_payment)
        delete_btn.clicked.connect(_delete_selected_payment)
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(pay_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)

        polish_controls(dlg)
        if _refresh_profile():
            dlg.exec_()





