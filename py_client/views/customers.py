from PyQt5 import QtWidgets, QtCore, QtGui
from datetime import datetime
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


class CustomersView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user_id = 0
        self._is_admin = False
        self._can_delete_payment = False
        self._build()
        self.refresh()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        apply_page_layout(layout)
        header = QtWidgets.QHBoxLayout()
        apply_header_layout(header)
        self.chk_inactive = QtWidgets.QCheckBox("Show inactive")
        self.btn_add = QtWidgets.QPushButton("Add Customer")
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
        self.search.setPlaceholderText("Search name, phone, email, address")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(360)
        self.search.installEventFilter(self)
        header.addWidget(self.search)
        layout.addLayout(header)

        # Main customers table now shows amount summary columns similar to suppliers.
        self.table = QtWidgets.QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Phone", "Email", "Address", "Invoices", "Total", "Paid", "Due"]
        )
        configure_table(self.table, stretch_last=False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeToContents)
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
        self.table.itemDoubleClicked.connect(lambda _item: self.open_profile_selected())
        self.btn_prev.clicked.connect(self._prev_page)
        self.btn_next.clicked.connect(self._next_page)
        self.chk_inactive.stateChanged.connect(self._on_filter_changed)
        self._search_timer = QtCore.QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(self._on_search_changed)
        self._page = 1
        self._pages = 1
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
        existing = self._selected_customer()
        has_sel = existing is not None
        is_active = bool((existing or {}).get("is_active", True))
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

    def set_user(self, user: dict):
        try:
            self.user_id = int((user or {}).get("id", 0) or 0)
        except Exception:
            self.user_id = 0
        uname = str((user or {}).get("username", "") or "").strip().lower()
        self._is_admin = bool(self.user_id == 1 or uname == "admin")
        self._can_delete_payment = bool(user.get("perm_delete_payment", False) or self._is_admin)

    def refresh(self):
        try:
            data = self.api.customers_page(
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
        for p in items:
            r = self.table.rowCount()
            self.table.insertRow(r)
            cid = int((p or {}).get("id", 0) or 0)
            name = str(p.get("name", "") or "")
            is_active = bool(p.get("is_active", True))
            inv_count = int((p or {}).get("invoice_count", 0) or 0)
            total_sales = float((p or {}).get("total_sales", 0.0) or 0.0)
            total_paid = float((p or {}).get("total_paid", 0.0) or 0.0)
            total_due = max(0.0, float((p or {}).get("total_due", 0.0) or 0.0))

            id_item = QtWidgets.QTableWidgetItem(str(cid))
            name_item = QtWidgets.QTableWidgetItem(name if is_active else f"{name} (Inactive)")
            phone_item = QtWidgets.QTableWidgetItem(p.get("phone", ""))
            email_item = QtWidgets.QTableWidgetItem(p.get("email", ""))
            addr_item = QtWidgets.QTableWidgetItem(p.get("address", ""))

            inv_item = QtWidgets.QTableWidgetItem(str(inv_count))
            total_item = QtWidgets.QTableWidgetItem(f"{total_sales:.2f}")
            paid_item = QtWidgets.QTableWidgetItem(f"{total_paid:.2f}")
            due_item = QtWidgets.QTableWidgetItem(f"{total_due:.2f}")

            inv_item.setTextAlignment(QtCore.Qt.AlignCenter)
            total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            paid_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            due_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
            if total_due > 1e-9:
                due_item.setForeground(QtGui.QBrush(QtGui.QColor("#F87171")))

            if not is_active:
                fade = QtGui.QBrush(QtGui.QColor("#7C8DA6"))
                for itm in (id_item, name_item, phone_item, email_item, addr_item, inv_item, total_item, paid_item):
                    itm.setForeground(fade)

            self.table.setItem(r, 0, id_item)
            self.table.setItem(r, 1, name_item)
            self.table.setItem(r, 2, phone_item)
            self.table.setItem(r, 3, email_item)
            self.table.setItem(r, 4, addr_item)
            self.table.setItem(r, 5, inv_item)
            self.table.setItem(r, 6, total_item)
            self.table.setItem(r, 7, paid_item)
            self.table.setItem(r, 8, due_item)
        self.page_label.setText(f"Page {self._page} / {self._pages}")
        self.btn_prev.setEnabled(self._page > 1)
        self.btn_next.setEnabled(self._page < self._pages)
        self._sync_action_state()

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

    def add_dialog(self):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle("Add Customer")
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        name.setPlaceholderText("Customer name")
        phone = QtWidgets.QLineEdit()
        phone.setPlaceholderText("Phone number")
        email = QtWidgets.QLineEdit()
        email.setPlaceholderText("Email")
        address = QtWidgets.QLineEdit()
        address.setPlaceholderText("Address")
        form.addRow("Name", name)
        form.addRow("Phone", phone)
        form.addRow("Email", email)
        form.addRow("Address", address)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=460, fixed=True)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "name": name.text().strip(),
                "phone": phone.text().strip(),
                "email": email.text().strip(),
                "address": address.text().strip(),
            }
            try:
                if not payload["name"]:
                    raise ValueError("Name is required")
                self.api.customer_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _selected_customer(self):
        r = self.table.currentRow()
        if r < 0:
            return None
        cid_item = self.table.item(r, 0)
        if not cid_item:
            return None
        try:
            cid = int(cid_item.text())
        except Exception:
            return None
        try:
            return self.api.customer_get(cid)
        except Exception:
            return None

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

    def _customer_transactions(self, customer_id: int):
        docs = self.api.transactions_by_customer(int(customer_id))
        if isinstance(docs, dict):
            detail = str(docs.get("detail", "") or "").strip()
            if detail:
                raise ValueError(detail)
            return []
        return list(docs or [])

    def open_profile_selected(self):
        customer = self._selected_customer()
        if not customer:
            QtWidgets.QMessageBox.information(self, "Select", "Select a customer row first")
            return
        try:
            cid = int(customer.get("id", 0) or 0)
        except Exception:
            cid = 0
        if cid <= 0:
            QtWidgets.QMessageBox.information(self, "Select", "Invalid customer")
            return
        cname = str(customer.get("name", "") or "Customer")
        max_dlg_w, max_dlg_h = dialog_screen_limits(
            width_ratio=0.92,
            height_ratio=0.90,
            fallback_width=1120,
            fallback_height=760,
        )
        row_h = 32
        chrome_h = 224
        col_widths = {
            0: 96,   # Invoice #
            1: 116,  # Date
            2: 92,   # Time
            3: 108,  # Total
            4: 108,  # Paid
            5: 108,  # Due
            6: 102,  # Discount
        }
        pay_col_widths = {
            0: 116,  # Date
            1: 92,   # Time
            2: 96,   # Invoice #
            3: 110,  # Amount
            4: 110,  # Paid Total
            5: 206,  # User (wider to align tables)
            6: 0,    # Payment ID (hidden, zero-width)
        }

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Customer Profile - {cname}")
        v = QtWidgets.QVBoxLayout(dlg)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(8)
        title = QtWidgets.QLabel(f"{cname} (ID: {cid})")
        title.setObjectName("moneyStrong")
        v.addWidget(title)

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
        table = QtWidgets.QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(["Invoice #", "Date", "Time", "Total", "Paid", "Due", "Discount"])
        configure_table(table, stretch_last=False)
        table.verticalHeader().setDefaultSectionSize(row_h)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        hdr = table.horizontalHeader()
        for col in range(7):
            hdr.setSectionResizeMode(col, QtWidgets.QHeaderView.Fixed)
            table.setColumnWidth(col, col_widths[col])
        v.addWidget(table)

        info_lbl = QtWidgets.QLabel("Merged payments are auto-allocated to oldest due invoices.")
        info_lbl.setObjectName("mutedLabel")
        v.addWidget(info_lbl)

        # Payments table (mirrors supplier profile)
        payments_title = QtWidgets.QLabel("Payment History (Installments)")
        payments_title.setObjectName("mutedLabel")
        v.addWidget(payments_title)

        payments_table = QtWidgets.QTableWidget(0, 7)
        payments_table.setHorizontalHeaderLabels(
            ["Date", "Time", "Invoice #", "Amount", "Paid Total", "User", "Payment ID"]
        )
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

        state = {"due_total": 0.0, "total_rows": 0, "user_map": {}}

        def _to_float(value, default=0.0):
            try:
                return float(value if value is not None else default)
            except Exception:
                return float(default)

        def _fit_tables():
            # Keep invoice and payment tables aligned and scrollable even with many rows.
            max_visible_rows = 12
            base_w = max(
                sum(col_widths.values()),
                sum(pay_col_widths[c] for c in range(7) if c != 6),
            )

            inv_frame = table.frameWidth() * 2 + 2
            inv_table_w = base_w + inv_frame
            inv_rows = min(table.rowCount(), max_visible_rows)
            inv_table_h = (
                table.frameWidth() * 2 + table.horizontalHeader().height() + (inv_rows * row_h) + 2
            )
            table.setFixedSize(inv_table_w, inv_table_h)

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
                inv_rows = self._customer_transactions(cid)
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Error", str(e))
                return False
            try:
                all_pay_rows = self.api.transaction_payments_list() or []
            except Exception:
                all_pay_rows = []

            if isinstance(all_pay_rows, dict) and str(all_pay_rows.get("detail", "")).strip():
                QtWidgets.QMessageBox.information(dlg, "Payments", str(all_pay_rows.get("detail", "")).strip())
                all_pay_rows = []

            inv_rows = list(inv_rows or [])
            inv_rows.sort(key=lambda row: str(row.get("date", "") or ""), reverse=True)

            invoice_ids: set[int] = set()
            for row in inv_rows:
                try:
                    tx_id = int((row or {}).get("id", 0) or 0)
                except Exception:
                    tx_id = 0
                if tx_id > 0:
                    invoice_ids.add(tx_id)

            pay_rows: list[dict] = []
            for row in list(all_pay_rows or []):
                try:
                    tx_id = int((row or {}).get("transaction_id", 0) or 0)
                except Exception:
                    tx_id = 0
                if tx_id in invoice_ids:
                    pay_rows.append(row)

            pay_rows.sort(key=lambda row: int((row or {}).get("id", 0) or 0), reverse=True)

            table.setRowCount(0)
            payments_table.setRowCount(0)

            state["total_rows"] = len(inv_rows)

            total_sum = 0.0
            paid_sum = 0.0
            due_sum = 0.0
            for t in inv_rows:
                total = max(0.0, _to_float(t.get("total", 0.0), 0.0))
                paid = max(0.0, _to_float(t.get("paid", 0.0), 0.0))
                due = max(0.0, total - paid)
                total_sum += total
                paid_sum += paid
                due_sum += due

            inv_lbl.setText(f"Invoices: {len(inv_rows)}")
            total_lbl.setText(f"Total: {total_sum:.2f}")
            paid_lbl.setText(f"Paid: {paid_sum:.2f}")
            due_lbl.setText(f"Merged Due: {due_sum:.2f}")
            state["due_total"] = float(due_sum)
            receive_btn.setEnabled(due_sum > 1e-9)

            if not inv_rows and not pay_rows:
                inv_overflow_lbl.setVisible(False)
                pay_overflow_lbl.setVisible(False)
                _fit_tables()
                self.refresh()
                return True

            # Show all rows; dialog height is capped by _fit_tables and tables become scrollable.
            inv_rows_budget = len(inv_rows)
            pay_rows_budget = len(pay_rows)

            # Fill invoices
            visible_inv_rows = inv_rows[:inv_rows_budget]
            hidden_inv = max(0, len(inv_rows) - len(visible_inv_rows))
            for t in visible_inv_rows:
                rr = table.rowCount()
                table.insertRow(rr)
                total = max(0.0, _to_float(t.get("total", 0.0), 0.0))
                paid = max(0.0, _to_float(t.get("paid", 0.0), 0.0))
                due = max(0.0, total - paid)
                date_txt, time_txt = self._split_datetime(t.get("date", ""))
                inv_id = int(t.get("id", 0) or 0)
                disc_val = _to_float(t.get("discount", 0.0), 0.0)

                inv_item = QtWidgets.QTableWidgetItem(str(inv_id))
                date_item = QtWidgets.QTableWidgetItem(date_txt)
                time_item = QtWidgets.QTableWidgetItem(time_txt)
                total_item = QtWidgets.QTableWidgetItem(f"{total:.2f}")
                paid_item = QtWidgets.QTableWidgetItem(f"{paid:.2f}")
                due_item = QtWidgets.QTableWidgetItem(f"{due:.2f}")
                disc_item = QtWidgets.QTableWidgetItem(f"{disc_val:.2f}")

                inv_item.setTextAlignment(QtCore.Qt.AlignCenter)
                date_item.setTextAlignment(QtCore.Qt.AlignCenter)
                time_item.setTextAlignment(QtCore.Qt.AlignCenter)
                total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                paid_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                due_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                disc_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                if due > 1e-9:
                    due_item.setForeground(QtGui.QBrush(QtGui.QColor("#F87171")))

                table.setItem(rr, 0, inv_item)
                table.setItem(rr, 1, date_item)
                table.setItem(rr, 2, time_item)
                table.setItem(rr, 3, total_item)
                table.setItem(rr, 4, paid_item)
                table.setItem(rr, 5, due_item)
                table.setItem(rr, 6, disc_item)

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
                inv_id = int((row or {}).get("transaction_id", 0) or 0)
                amount = _to_float(row.get("amount", 0.0), 0.0)
                paid_total = _to_float(row.get("paid_total", 0.0), 0.0)
                uid = int((row or {}).get("user_id", 0) or 0)
                pid = int((row or {}).get("id", 0) or 0)

                date_item = QtWidgets.QTableWidgetItem(date_txt)
                time_item = QtWidgets.QTableWidgetItem(time_txt)
                inv_item = QtWidgets.QTableWidgetItem(str(inv_id))
                amount_item = QtWidgets.QTableWidgetItem(f"{amount:.2f}")
                paid_total_item = QtWidgets.QTableWidgetItem(f"{paid_total:.2f}")
                user_item = QtWidgets.QTableWidgetItem(_user_name(uid))
                id_item = QtWidgets.QTableWidgetItem(str(pid))

                date_item.setTextAlignment(QtCore.Qt.AlignCenter)
                time_item.setTextAlignment(QtCore.Qt.AlignCenter)
                inv_item.setTextAlignment(QtCore.Qt.AlignCenter)
                amount_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
                paid_total_item.setTextAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)

                payments_table.setItem(rr, 0, date_item)
                payments_table.setItem(rr, 1, time_item)
                payments_table.setItem(rr, 2, inv_item)
                payments_table.setItem(rr, 3, amount_item)
                payments_table.setItem(rr, 4, paid_total_item)
                payments_table.setItem(rr, 5, user_item)
                payments_table.setItem(rr, 6, id_item)

            if hidden_pay > 0:
                pay_overflow_lbl.setText(
                    f"Showing latest {len(visible_pay_rows)} of {len(pay_rows)} payments to fit screen without scrolling."
                )
                pay_overflow_lbl.setVisible(True)
            else:
                pay_overflow_lbl.setVisible(False)

            _fit_tables()
            self.refresh()
            return True

        def _edit_selected_payment():
            rr = payments_table.currentRow()
            if rr < 0:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Select a payment row first.")
                return
            if not self._can_delete_payment:
                QtWidgets.QMessageBox.information(
                    dlg,
                    "Permission",
                    "You do not have permission to modify payments.",
                )
                return
            id_item = payments_table.item(rr, 6)
            inv_item = payments_table.item(rr, 2)
            amt_item = payments_table.item(rr, 3)
            if not id_item or not inv_item or not amt_item:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Invalid payment row.")
                return
            try:
                payment_id = int(id_item.text() or 0)
            except Exception:
                payment_id = 0
            try:
                transaction_id = int(inv_item.text() or 0)
            except Exception:
                transaction_id = 0
            if payment_id <= 0 or transaction_id <= 0:
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
                resp = self.api.transaction_payment_update(
                    transaction_id,
                    payment_id,
                    float(new_amount),
                    user_id=int(self.user_id or 0),
                )
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
            if not self._can_delete_payment:
                QtWidgets.QMessageBox.information(
                    dlg,
                    "Permission",
                    "You do not have permission to delete payments.",
                )
                return
            id_item = payments_table.item(rr, 6)
            inv_item = payments_table.item(rr, 2)
            if not id_item or not inv_item:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Invalid payment row.")
                return
            try:
                payment_id = int(id_item.text() or 0)
            except Exception:
                payment_id = 0
            try:
                transaction_id = int(inv_item.text() or 0)
            except Exception:
                transaction_id = 0
            if payment_id <= 0 or transaction_id <= 0:
                QtWidgets.QMessageBox.information(dlg, "Payments", "Invalid payment selection.")
                return
            if QtWidgets.QMessageBox.question(dlg, "Confirm", "Delete this payment entry?") != QtWidgets.QMessageBox.Yes:
                return
            try:
                resp = self.api.transaction_payment_delete(
                    transaction_id,
                    payment_id,
                    user_id=int(self.user_id or 0),
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                QtWidgets.QMessageBox.information(dlg, "Payments", str(resp.get("detail")))
                return
            _refresh_profile()

        def _receive_payment():
            merged_due = float(state.get("due_total", 0.0) or 0.0)
            if merged_due <= 1e-9:
                QtWidgets.QMessageBox.information(dlg, "Payment", "No due invoices for this customer.")
                return
            amount, ok = QtWidgets.QInputDialog.getDouble(
                dlg,
                "Receive Payment",
                "Enter merged payment amount:",
                value=merged_due,
                min=0.01,
                max=merged_due,
                decimals=2,
            )
            if not ok:
                return
            try:
                resp = self.api.customer_payment_apply(
                    cid,
                    float(amount),
                    user_id=int(self.user_id or 0),
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(dlg, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("customer_id"):
                QtWidgets.QMessageBox.information(dlg, "Payment", str(resp.get("detail")))
                return
            try:
                applied = float((resp or {}).get("total_applied", 0.0) or 0.0)
                remaining = float((resp or {}).get("total_due_after", 0.0) or 0.0)
                alloc_count = len((resp or {}).get("allocations", []) or [])
            except Exception:
                applied = float(amount)
                remaining = max(0.0, merged_due - float(amount))
                alloc_count = 0
            QtWidgets.QMessageBox.information(
                dlg,
                "Payment Applied",
                f"Applied {applied:.2f} across {alloc_count} invoice(s).\nRemaining merged due: {remaining:.2f}",
            )
            _refresh_profile()

        btn_row = QtWidgets.QHBoxLayout()
        apply_header_layout(btn_row)
        receive_btn = QtWidgets.QPushButton("Receive Payment")
        edit_btn = QtWidgets.QPushButton("Edit Selected")
        delete_btn = QtWidgets.QPushButton("Delete Selected")
        close_btn = QtWidgets.QPushButton("Close")
        set_accent(receive_btn)
        set_secondary(edit_btn, delete_btn, close_btn)
        receive_btn.clicked.connect(_receive_payment)
        edit_btn.clicked.connect(_edit_selected_payment)
        delete_btn.clicked.connect(_delete_selected_payment)
        if not self._can_delete_payment:
            edit_btn.setEnabled(False)
            delete_btn.setEnabled(False)
            edit_btn.setToolTip("You do not have permission to modify payments.")
            delete_btn.setToolTip("You do not have permission to delete payments.")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(receive_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)
        polish_controls(dlg)
        if _refresh_profile():
            dlg.exec_()

    def _customer_dialog(self, title: str, existing: dict | None = None):
        d = QtWidgets.QDialog(self)
        d.setWindowTitle(title)
        form = QtWidgets.QFormLayout(d)
        apply_form_layout(form)
        name = QtWidgets.QLineEdit()
        phone = QtWidgets.QLineEdit()
        email = QtWidgets.QLineEdit()
        address = QtWidgets.QLineEdit()
        if existing:
            name.setText(existing.get("name", ""))
            phone.setText(existing.get("phone", ""))
            email.setText(existing.get("email", ""))
            address.setText(existing.get("address", ""))
        form.addRow("Name", name)
        form.addRow("Phone", phone)
        form.addRow("Email", email)
        form.addRow("Address", address)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        form.addRow(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)
        polish_controls(d)
        fit_dialog_to_contents(d, min_width=460, fixed=True)
        return d, name, phone, email, address

    def edit_selected(self):
        existing = self._selected_customer()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a customer row first")
            return
        d, name, phone, email, address = self._customer_dialog("Edit Customer", existing)
        if d.exec_() == QtWidgets.QDialog.Accepted:
            payload = {
                "id": int(existing.get("id")),
                "name": name.text().strip(),
                "phone": phone.text().strip(),
                "email": email.text().strip(),
                "address": address.text().strip(),
            }
            try:
                if not payload["name"]:
                    raise ValueError("Name is required")
                self.api.customer_upsert(payload)
                self.refresh()
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def delete_selected(self):
        existing = self._selected_customer()
        if not existing:
            QtWidgets.QMessageBox.information(self, "Select", "Select a customer row first")
            return
        is_active = bool(existing.get("is_active", True))
        try:
            if is_active:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Deactivate this customer?") != QtWidgets.QMessageBox.Yes:
                    return
                self.api.customer_delete(int(existing.get("id")))
                QtWidgets.QMessageBox.information(self, "Deactivated", "Customer has been deactivated.")
            else:
                if QtWidgets.QMessageBox.question(self, "Confirm", "Reactivate this customer?") != QtWidgets.QMessageBox.Yes:
                    return
                payload = {
                    "id": int(existing.get("id")),
                    "name": str(existing.get("name", "") or ""),
                    "phone": str(existing.get("phone", "") or ""),
                    "email": str(existing.get("email", "") or ""),
                    "address": str(existing.get("address", "") or ""),
                }
                resp = self.api.customer_upsert(payload)
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    QtWidgets.QMessageBox.warning(self, "Error", str(resp.get("detail")))
                    return
                QtWidgets.QMessageBox.information(self, "Reactivated", "Customer has been reactivated.")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))








