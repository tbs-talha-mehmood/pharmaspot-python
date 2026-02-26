from PyQt5 import QtWidgets, QtPrintSupport, QtCore, QtGui
import base64
from pathlib import Path
from datetime import datetime


class POSView(QtWidgets.QWidget):
    """Point of Sale view — redesigned for speed and simplicity.

    Key improvements:
    - Always‑visible search box with instant results (Enter to add)
    - Clean cart table: Item, Qty, Price, Line Total, Remove
    - Big checkout area with Subtotal, Discount %, VAT, Total
    - Clear Cart and keyboard shortcuts (F2 focus search, Del remove)
    """

    def __init__(self, api):
        super().__init__()
        self.api = api
        self.user_id = 0
        self.products_cache = []
        self.held_sales: list[dict] = []
        self.vat_percent = 0.0
        self._edit_transaction_id = None
        self._edit_original_qty_by_product: dict[int, int] = {}
        self._edit_existing_paid = 0.0
        self._build()
        self._load_customers()
        self._load_products_cache()
        self._load_settings()

    # ---------- UI ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Top card: sale controls + quick search
        top_card = QtWidgets.QFrame()
        top_card.setObjectName("posTopCard")
        top_wrap = QtWidgets.QVBoxLayout(top_card)
        top_wrap.setContentsMargins(12, 10, 12, 10)
        top_wrap.setSpacing(8)

        # Customer + invoice row
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(8)
        cust_lbl = QtWidgets.QLabel("Customer:")
        cust_lbl.setObjectName("mutedLabel")
        top.addWidget(cust_lbl)
        self.customer = QtWidgets.QComboBox()
        self.customer.setMinimumWidth(300)
        self.customer.setEditable(True)
        self.customer.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.customer.setMaxVisibleItems(20)
        cust_line = self.customer.lineEdit()
        if cust_line is not None:
            cust_line.setPlaceholderText("Type to search customer...")
            cust_line.returnPressed.connect(self._select_customer_by_typed_text)
        comp = self.customer.completer()
        if comp is not None:
            comp.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
            comp.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
            try:
                comp.setFilterMode(QtCore.Qt.MatchContains)
            except Exception:
                pass
        top.addWidget(self.customer)
        top.addStretch(1)
        inv_lbl = QtWidgets.QLabel("Invoice #:")
        inv_lbl.setObjectName("mutedLabel")
        top.addWidget(inv_lbl)
        self.invoice_no = QtWidgets.QLineEdit()
        self.invoice_no.setObjectName("invoiceInput")
        self.invoice_no.setPlaceholderText("e.g. 1001")
        self.invoice_no.setMinimumWidth(190)
        self.invoice_no.textChanged.connect(lambda _t: self._update_payment_history_visibility())
        self.invoice_no.returnPressed.connect(self._reopen_invoice_by_number)
        top.addWidget(self.invoice_no)
        self.payment_history_btn = QtWidgets.QPushButton("Payments")
        self.payment_history_btn.setProperty("secondary", True)
        self.payment_history_btn.clicked.connect(self._show_invoice_payments)
        self.payment_history_btn.setVisible(False)
        top.addWidget(self.payment_history_btn)
        self.cancel_invoice_edit_btn = QtWidgets.QPushButton("Cancel Edit")
        self.cancel_invoice_edit_btn.setProperty("danger", True)
        self.cancel_invoice_edit_btn.clicked.connect(self._cancel_invoice_edit)
        self.cancel_invoice_edit_btn.setVisible(False)
        top.addWidget(self.cancel_invoice_edit_btn)
        top_wrap.addLayout(top)

        # Search row
        search_row = QtWidgets.QHBoxLayout()
        search_row.setSpacing(8)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Type to search products...")
        self.search.textChanged.connect(self._on_search_changed)
        self.search.returnPressed.connect(self._add_first_search_result)
        self.search.setMinimumHeight(34)
        search_row.addWidget(self.search, 1)
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.setProperty("secondary", True)
        self.refresh_btn.setMinimumWidth(96)
        self.refresh_btn.clicked.connect(self._load_products_cache)
        search_row.addWidget(self.refresh_btn)
        top_wrap.addLayout(search_row)
        root.addWidget(top_card)

        # Search results list (inline, collapsible)
        self.results = QtWidgets.QListWidget()
        self.results.setVisible(False)
        self.results.setMaximumHeight(160)
        self.results.itemActivated.connect(self._on_result_activate)
        root.addWidget(self.results)

        # Cart table (match Purchases columns)
        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Product", "Retail", "% Discount", "Trade", "Addl %", "Qty", "Line Total",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        for col in (1, 2, 3, 4, 5, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        root.addWidget(self.table, 1)

        # Bottom: totals + actions
        bottom = QtWidgets.QHBoxLayout()
        bottom.setSpacing(8)
        self.clear_btn = QtWidgets.QPushButton("Clear Cart")
        self.clear_btn.setProperty("secondary", True)
        self.clear_btn.clicked.connect(self._clear_cart)
        bottom.addWidget(self.clear_btn)
        self.hold_btn = QtWidgets.QPushButton("Hold Sale")
        self.hold_btn.setProperty("secondary", True)
        self.hold_btn.clicked.connect(self._hold_sale)
        bottom.addWidget(self.hold_btn)
        self.resume_btn = QtWidgets.QPushButton("Resume Sale")
        self.resume_btn.setProperty("secondary", True)
        self.resume_btn.clicked.connect(self._resume_sale)
        bottom.addWidget(self.resume_btn)
        bottom.addStretch(1)

        discount_box = QtWidgets.QGroupBox("Sale")
        discount_box.setObjectName("totalsCard")
        discount_box.setMinimumWidth(200)
        discount_layout = QtWidgets.QFormLayout(discount_box)
        self.discount = QtWidgets.QDoubleSpinBox()
        self.discount.setRange(0, 100)
        self.discount.setDecimals(2)
        self.discount.setSingleStep(1.0)
        self.discount.setMinimumWidth(110)
        self.discount.valueChanged.connect(self._recalc_totals)
        self.discount.installEventFilter(self)
        try:
            discount_le = self.discount.lineEdit()
        except Exception:
            discount_le = None
        if discount_le is not None:
            discount_le.installEventFilter(self)
        discount_layout.addRow("Discount %:", self.discount)
        bottom.addWidget(discount_box)

        totals_box = QtWidgets.QGroupBox("Totals")
        totals_box.setObjectName("totalsCard")
        totals_box.setMinimumWidth(260)
        totals_layout = QtWidgets.QFormLayout(totals_box)
        self.subtotal_label = QtWidgets.QLabel("0.00")
        self.vat_label = QtWidgets.QLabel("0.00")
        self.total_label = QtWidgets.QLabel("0.00")
        self.total_label.setObjectName("moneyStrong")
        self.paid_spin = QtWidgets.QDoubleSpinBox()
        self.paid_spin.setRange(0, 10**9)
        self.paid_spin.setDecimals(2)
        self.paid_spin.setValue(0.0)
        self.paid_spin.setSingleStep(10.0)
        self.paid_spin.valueChanged.connect(self._recalc_totals)
        self.paid_spin.installEventFilter(self)
        try:
            paid_le = self.paid_spin.lineEdit()
        except Exception:
            paid_le = None
        if paid_le is not None:
            paid_le.installEventFilter(self)
        self.paid_input_label = QtWidgets.QLabel("Paid:")
        self.paid_prior_key_label = QtWidgets.QLabel("Paid So Far:")
        self.paid_prior_value_label = QtWidgets.QLabel("0.00")
        self.paid_total_key_label = QtWidgets.QLabel("Paid Total:")
        self.paid_total_value_label = QtWidgets.QLabel("0.00")
        self.due_label = QtWidgets.QLabel("0.00")
        font_bold = self.total_label.font()
        font_bold.setPointSize(font_bold.pointSize() + 1)
        font_bold.setBold(True)
        self.total_label.setFont(font_bold)
        totals_layout.addRow("Subtotal:", self.subtotal_label)
        totals_layout.addRow("VAT:", self.vat_label)
        totals_layout.addRow("Total:", self.total_label)
        totals_layout.addRow(self.paid_input_label, self.paid_spin)
        totals_layout.addRow(self.paid_prior_key_label, self.paid_prior_value_label)
        totals_layout.addRow(self.paid_total_key_label, self.paid_total_value_label)
        totals_layout.addRow("Due:", self.due_label)
        self.paid_prior_key_label.setVisible(False)
        self.paid_prior_value_label.setVisible(False)
        self.paid_total_key_label.setVisible(False)
        self.paid_total_value_label.setVisible(False)
        bottom.addWidget(totals_box)

        self.checkout_btn = QtWidgets.QPushButton("Checkout")
        self.checkout_btn.setObjectName("checkoutBtn")
        self.checkout_btn.setStyleSheet("padding: 8px 18px; font-size: 14px; font-weight: 600;")
        self.checkout_btn.clicked.connect(self.checkout)
        bottom.addWidget(self.checkout_btn)
        root.addLayout(bottom)

        # Shortcuts
        QtWidgets.QShortcut(QtGui.QKeySequence("F2"), self, activated=self._focus_search)
        QtWidgets.QShortcut(QtGui.QKeySequence("F8"), self, activated=self._show_purchase_history)
        QtWidgets.QShortcut(QtGui.QKeySequence("F11"), self, activated=self._hold_sale)
        QtWidgets.QShortcut(QtGui.QKeySequence("F12"), self, activated=self._resume_sale)
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self, activated=self._remove_selected_row)
        # Keyboard-only navigation helpers
        self.search.installEventFilter(self)
        self.table.installEventFilter(self)

    # ---------- Data loads ----------
    def _load_products_cache(self):
        try:
            def _fetch():
                return self.api.products() or []
            self.products_cache = self._with_loader("Loading products...", _fetch) or []
        except Exception as e:
            self.products_cache = []
            QtWidgets.QMessageBox.warning(self, "Products", str(e))
        self._on_search_changed(self.search.text())

    def _load_settings(self):
        try:
            s = self.api.settings_map() or {}
            self.vat_percent = float((s.get("settings", {}) or {}).get("vat_percent", 0.0))
        except Exception:
            self.vat_percent = 0.0
        self._recalc_totals()

    def _load_customers(self):
        prev_id = 0
        try:
            prev_id = int(self.customer.currentData() or 0)
        except Exception:
            prev_id = 0
        try:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)
            customers = self.api.customers() or []
            customers = sorted(customers, key=lambda x: str((x or {}).get("name", "")).lower())
            for c in customers:
                self.customer.addItem(c.get("name", "Customer"), int(c.get("id")))
        except Exception:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)
        if prev_id > 0:
            idx = self.customer.findData(prev_id)
            if idx >= 0:
                self.customer.setCurrentIndex(idx)
            else:
                self.customer.setCurrentIndex(0)
        else:
            self.customer.setCurrentIndex(0)

    def _select_customer_by_typed_text(self):
        text = (self.customer.currentText() or "").strip().lower()
        if not text:
            self._focus_search()
            return
        # Prefer exact match first
        for i in range(self.customer.count()):
            if (self.customer.itemText(i) or "").strip().lower() == text:
                self.customer.setCurrentIndex(i)
                self._focus_search()
                return
        # Fallback to first contains match
        for i in range(self.customer.count()):
            if text in (self.customer.itemText(i) or "").strip().lower():
                self.customer.setCurrentIndex(i)
                self._focus_search()
                return
        self._focus_search()

    # ---------- Invoice edit mode ----------
    def _update_payment_history_visibility(self):
        show = self._edit_transaction_id is not None
        self.payment_history_btn.setVisible(show)

    def _set_invoice_edit_mode(self, transaction_id: int, original_qty_map: dict[int, int], existing_paid: float = 0.0):
        self._edit_transaction_id = int(transaction_id)
        self._edit_original_qty_by_product = {
            int(pid): int(qty)
            for pid, qty in (original_qty_map or {}).items()
            if int(pid) > 0 and int(qty) > 0
        }
        try:
            self._edit_existing_paid = max(0.0, float(existing_paid or 0.0))
        except Exception:
            self._edit_existing_paid = 0.0
        self.checkout_btn.setText(f"Update Invoice #{self._edit_transaction_id}")
        self.cancel_invoice_edit_btn.setVisible(True)
        self.paid_input_label.setText("Add Payment:")
        self.paid_prior_key_label.setVisible(True)
        self.paid_prior_value_label.setVisible(True)
        self.paid_total_key_label.setVisible(True)
        self.paid_total_value_label.setVisible(True)
        self.paid_spin.setValue(0.0)
        self._recalc_totals()
        self._update_payment_history_visibility()

    def _exit_invoice_edit_mode(self):
        self._edit_transaction_id = None
        self._edit_original_qty_by_product = {}
        self._edit_existing_paid = 0.0
        self.checkout_btn.setText("Checkout")
        self.cancel_invoice_edit_btn.setVisible(False)
        self.paid_input_label.setText("Paid:")
        self.paid_prior_key_label.setVisible(False)
        self.paid_prior_value_label.setVisible(False)
        self.paid_total_key_label.setVisible(False)
        self.paid_total_value_label.setVisible(False)
        self.invoice_no.clear()
        self._update_payment_history_visibility()

    def _cancel_invoice_edit(self):
        if self._edit_transaction_id is None:
            return
        if QtWidgets.QMessageBox.question(
            self,
            "Cancel Edit",
            "Discard current invoice edits?",
        ) != QtWidgets.QMessageBox.Yes:
            return
        self._exit_invoice_edit_mode()
        self._clear_cart()

    # ---------- Search ----------
    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _focus_discount_input(self):
        self.discount.setFocus()
        try:
            le = self.discount.lineEdit()
        except Exception:
            le = None
        if le is not None:
            try:
                le.selectAll()
            except Exception:
                pass

    def _focus_paid_input(self):
        self.paid_spin.setFocus()
        try:
            le = self.paid_spin.lineEdit()
        except Exception:
            le = None
        if le is not None:
            try:
                le.selectAll()
            except Exception:
                pass

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            shift_enter = bool(event.modifiers() & QtCore.Qt.ShiftModifier) and key in (
                QtCore.Qt.Key_Return,
                QtCore.Qt.Key_Enter,
            )
            if obj is self.search:
                if key in (QtCore.Qt.Key_Up, QtCore.Qt.Key_Down):
                    if self.results.isVisible() and self.results.count() > 0:
                        row = self.results.currentRow()
                        if row < 0:
                            row = 0
                        if key == QtCore.Qt.Key_Up:
                            row = max(0, row - 1)
                        else:
                            row = min(self.results.count() - 1, row + 1)
                        self.results.setCurrentRow(row)
                        return True
                    # If no search results are open, Down moves into cart editing.
                    if key == QtCore.Qt.Key_Down and self.table.rowCount() > 0:
                        self._focus_cart_from_search()
                        return True
                elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    if self.results.isVisible() and self.results.currentItem():
                        self._add_first_search_result()
                        return True
                    # Enter in search (without an active result) jumps to cart fields.
                    if self.table.rowCount() > 0:
                        self._focus_cart_from_search()
                        return True
                elif key == QtCore.Qt.Key_Right:
                    if self.table.rowCount() > 0:
                        self._focus_cart_from_search()
                        return True
            elif obj is self.table:
                if shift_enter:
                    self._focus_discount_input()
                    return True
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    self._focus_next_cart_field()
                    return True
                if key == QtCore.Qt.Key_Left:
                    self._focus_prev_cart_field()
                    return True
                if key == QtCore.Qt.Key_Right:
                    self._focus_next_cart_field()
                    return True
            elif obj is self.discount or obj is self.discount.lineEdit():
                if shift_enter:
                    self._focus_paid_input()
                    return True
            elif obj is self.paid_spin or obj is self.paid_spin.lineEdit():
                if shift_enter:
                    self.checkout()
                    return True
            else:
                row, col = self._cart_widget_position(obj)
                if row is not None and col is not None:
                    self.table.setCurrentCell(row, col)
                    if shift_enter:
                        self._focus_discount_input()
                        return True
                    if key == QtCore.Qt.Key_Left:
                        self._focus_prev_cart_field()
                        return True
                    if key == QtCore.Qt.Key_Right:
                        self._focus_next_cart_field()
                        return True
                    if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                        self._focus_next_cart_field()
                        return True
        return super().eventFilter(obj, event)

    def _on_search_changed(self, text: str):
        text_raw = (text or "").strip()
        text_l = text_raw.lower()
        self.results.clear()
        # Ensure cache is loaded at least once
        if not self.products_cache:
            try:
                self.products_cache = self.api.products() or []
            except Exception:
                self.products_cache = []
        if not text_l:
            self.results.setVisible(False)
            return
        count = 0
        is_digits = text_raw.isdigit()
        for p in self.products_cache:
            try:
                name = str(p.get("name", ""))
                company = str(p.get("company_name", ""))
                pid = str(p.get("id", ""))
                if (
                    text_l in name.lower()
                    or (company and text_l in company.lower())
                    or (is_digits and text_raw == pid)
                ):
                    label = f"{name} ({company})" if company else name
                    item = QtWidgets.QListWidgetItem(label)
                    item.setData(QtCore.Qt.UserRole, int(p.get("id")))
                    self.results.addItem(item)
                    count += 1
                    if count >= 100:  # cap list for responsiveness
                        break
            except Exception:
                pass
        self.results.setVisible(self.results.count() > 0)
        if self.results.count() > 0:
            self.results.setCurrentRow(0)

    def _add_first_search_result(self):
        item = self.results.currentItem() if self.results.isVisible() else None
        if item is None and self.results.count() > 0:
            item = self.results.item(0)
        if item is None:
            return
        self._on_result_activate(item)

    def _on_result_activate(self, item: QtWidgets.QListWidgetItem):
        pid = int(item.data(QtCore.Qt.UserRole) or 0)
        prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == pid), None)
        if not prod:
            return
        row = self._add_product_to_cart(prod)
        self.search.clear()
        self.results.setVisible(False)
        if row is not None:
            self._focus_cart_cell(row, 2)

    def _selected_product_for_history(self):
        # Prefer selected cart row
        r = self.table.currentRow()
        if r >= 0:
            item = self.table.item(r, 0)
            if item:
                meta = item.data(QtCore.Qt.UserRole) or {}
                try:
                    pid = int(meta.get("id", 0) or 0)
                except Exception:
                    pid = 0
                if pid:
                    return pid, item.text()
        # Fallback to highlighted search result
        it = self.results.currentItem()
        if it is not None:
            try:
                pid = int(it.data(QtCore.Qt.UserRole) or 0)
            except Exception:
                pid = 0
            if pid:
                return pid, it.text()
        return None

    def _show_purchase_history(self):
        sel = self._selected_product_for_history()
        if not sel:
            QtWidgets.QMessageBox.information(
                self,
                "Select product",
                "Select a product in the cart or search results to view its purchase history.",
            )
            return
        pid, name = sel
        try:
            docs = self._with_loader("Loading purchase history...", self.api.purchases_list) or []
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        rows = []
        for p in docs:
            date = p.get("date", "")
            supplier = p.get("supplier_name", "")
            for it in p.get("items") or []:
                try:
                    if int(it.get("product_id", 0) or 0) != pid:
                        continue
                except Exception:
                    continue
                qty = int(it.get("quantity", 0) or 0)
                retail = it.get("retail_price", it.get("price", 0.0))
                trade = it.get("trade_price", it.get("price", 0.0))
                disc = it.get("discount_pct", None)
                extra = it.get("extra_discount_pct", None)
                cut = bool(it.get("is_cut_rate")) if it.get("is_cut_rate") is not None else False
                try:
                    retail = float(retail or 0.0)
                except Exception:
                    retail = 0.0
                try:
                    trade = float(trade or 0.0)
                except Exception:
                    trade = 0.0
                try:
                    disc = float(disc) if disc is not None else None
                except Exception:
                    disc = None
                try:
                    extra = float(extra) if extra is not None else None
                except Exception:
                    extra = None
                try:
                    final = float(it.get("price", trade) or 0.0)
                except Exception:
                    final = trade
                rows.append(
                    {
                        "date": date,
                        "supplier": supplier,
                        "qty": qty,
                        "retail": retail,
                        "trade": trade,
                        "disc": disc,
                        "extra": extra,
                        "final": final,
                        "cut": cut,
                    }
                )
        if not rows:
            QtWidgets.QMessageBox.information(self, "No history", "No purchases found for this product.")
            return
        rows.sort(key=lambda r: r.get("date", ""), reverse=True)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Purchases for {name}")
        v = QtWidgets.QVBoxLayout(dlg)
        v.addWidget(QtWidgets.QLabel(f"Recent purchases for {name}"))
        table = QtWidgets.QTableWidget(len(rows), 9)
        table.setHorizontalHeaderLabels(
            ["Date", "Supplier", "Qty", "Retail", "Trade", "%Disc", "Addl %", "Line Total", "Cut"]
        )
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        for r_idx, row in enumerate(rows):
            table.setItem(r_idx, 0, QtWidgets.QTableWidgetItem(str(row["date"])))
            table.setItem(r_idx, 1, QtWidgets.QTableWidgetItem(str(row["supplier"])))
            table.setItem(r_idx, 2, QtWidgets.QTableWidgetItem(str(row["qty"])))
            table.setItem(r_idx, 3, QtWidgets.QTableWidgetItem(f"{row['retail']:.2f}"))
            table.setItem(r_idx, 4, QtWidgets.QTableWidgetItem(f"{row['trade']:.2f}"))
            disc_val = "" if row["disc"] is None else f"{row['disc']:.2f}"
            extra_val = "" if row["extra"] is None else f"{row['extra']:.2f}"
            table.setItem(r_idx, 5, QtWidgets.QTableWidgetItem(disc_val))
            table.setItem(r_idx, 6, QtWidgets.QTableWidgetItem(extra_val))
            table.setItem(r_idx, 7, QtWidgets.QTableWidgetItem(f"{row['final'] * row['qty']:.2f}"))
            table.setItem(r_idx, 8, QtWidgets.QTableWidgetItem("Yes" if row["cut"] else "No"))
        table.resizeRowsToContents()
        v.addWidget(table)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            dlg.resize(int(geo.width() * 0.92), int(geo.height() * 0.9))
        dlg.exec_()

    def _reopen_invoice_by_number(self):
        raw = (self.invoice_no.text() or "").strip()
        if not raw or not raw.isdigit():
            QtWidgets.QMessageBox.information(self, "Invoice", "Enter a valid invoice number.")
            return
        invoice_id = int(raw)
        if invoice_id <= 0:
            QtWidgets.QMessageBox.information(self, "Invoice", "Enter a valid invoice number.")
            return
        if self.table.rowCount() > 0:
            if QtWidgets.QMessageBox.question(
                self,
                "Replace Cart",
                "Current cart items will be replaced. Continue?",
            ) != QtWidgets.QMessageBox.Yes:
                return
        try:
            txn = self._with_loader("Loading invoice...", lambda: self.api.transaction_get(invoice_id))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        if not isinstance(txn, dict) or int(txn.get("id", 0) or 0) != invoice_id:
            detail = ""
            if isinstance(txn, dict):
                detail = str(txn.get("detail", "") or "").strip()
            if detail:
                QtWidgets.QMessageBox.information(self, "Invoice", detail)
            else:
                QtWidgets.QMessageBox.information(self, "Invoice", "Invoice not found.")
            return
        self._load_transaction_into_cart(txn)
        self.invoice_no.clear()

    def _invoice_id_for_payments(self):
        if self._edit_transaction_id is not None:
            return int(self._edit_transaction_id)
        return None

    def _show_invoice_payments(self):
        inv = self._invoice_id_for_payments()
        if inv is None:
            QtWidgets.QMessageBox.information(self, "Payments", "Reopen an invoice first.")
            return
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Payments for Invoice #{inv}")
        v = QtWidgets.QVBoxLayout(dlg)
        table = QtWidgets.QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Date", "Time", "Amount", "Paid Total", "User ID", "Payment ID"])
        table.setColumnHidden(5, True)
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        table.setAlternatingRowColors(True)
        v.addWidget(table)
        info = QtWidgets.QLabel("You can edit a payment amount and it will recalculate paid totals.")
        v.addWidget(info)

        def _load_rows():
            try:
                rows = self._with_loader("Loading payment history...", lambda: self.api.transaction_payments(inv)) or []
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return False
            if isinstance(rows, dict):
                detail = str(rows.get("detail", "") or "").strip()
                QtWidgets.QMessageBox.information(self, "Payments", detail or "Could not load payment history.")
                return False
            table.setRowCount(0)
            for row in rows:
                rr = table.rowCount()
                table.insertRow(rr)
                dt = str(row.get("date", "") or "").strip()
                date_txt, time_txt = "", ""
                if dt:
                    try:
                        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                        date_txt = parsed.strftime("%Y-%m-%d")
                        time_txt = parsed.strftime("%H:%M:%S")
                    except Exception:
                        normalized = dt.replace("T", " ")
                        parts = normalized.split()
                        date_txt = parts[0] if parts else normalized
                        if len(parts) > 1:
                            time_txt = parts[1]
                            if "." in time_txt:
                                time_txt = time_txt.split(".", 1)[0]
                            if len(time_txt) > 8 and time_txt[8] in ("+", "-"):
                                time_txt = time_txt[:8]
                try:
                    amt_f = float(row.get("amount", 0.0) or 0.0)
                except Exception:
                    amt_f = 0.0
                amt = f"+{amt_f:.2f}" if amt_f >= 0 else f"{amt_f:.2f}"
                try:
                    paid_total = float(row.get("paid_total", 0.0) or 0.0)
                except Exception:
                    paid_total = 0.0
                uid = int(row.get("user_id", 0) or 0)
                pid = int(row.get("id", 0) or 0)
                table.setItem(rr, 0, QtWidgets.QTableWidgetItem(date_txt))
                table.setItem(rr, 1, QtWidgets.QTableWidgetItem(time_txt))
                table.setItem(rr, 2, QtWidgets.QTableWidgetItem(amt))
                table.setItem(rr, 3, QtWidgets.QTableWidgetItem(f"{paid_total:.2f}"))
                table.setItem(rr, 4, QtWidgets.QTableWidgetItem(str(uid)))
                table.setItem(rr, 5, QtWidgets.QTableWidgetItem(str(pid)))
            table.resizeRowsToContents()
            return True

        def _edit_selected():
            rr = table.currentRow()
            if rr < 0:
                QtWidgets.QMessageBox.information(self, "Payments", "Select a payment row first.")
                return
            id_item = table.item(rr, 5)
            amt_item = table.item(rr, 2)
            if not id_item or not amt_item:
                QtWidgets.QMessageBox.information(self, "Payments", "Invalid payment row.")
                return
            try:
                payment_id = int(id_item.text() or 0)
            except Exception:
                payment_id = 0
            if payment_id <= 0:
                QtWidgets.QMessageBox.information(self, "Payments", "Invalid payment ID.")
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
                resp = self._with_loader(
                    "Saving payment...",
                    lambda: self.api.transaction_payment_update(inv, payment_id, float(new_amount)),
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Error", str(e))
                return
            if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                QtWidgets.QMessageBox.information(self, "Payments", str(resp.get("detail")))
                return
            _load_rows()
            self._sync_payment_edit_state(inv)

        if not _load_rows():
            return
        if table.rowCount() <= 0:
            QtWidgets.QMessageBox.information(self, "Payments", f"No payment entries for invoice #{inv}.")
            return
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        edit_btn = QtWidgets.QPushButton("Edit Selected")
        edit_btn.clicked.connect(_edit_selected)
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(_load_rows)
        row_btn = QtWidgets.QHBoxLayout()
        row_btn.addWidget(edit_btn)
        row_btn.addWidget(refresh_btn)
        row_btn.addStretch(1)
        row_btn.addWidget(close_btn)
        v.addLayout(row_btn)
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            dlg.resize(int(geo.width() * 0.92), int(geo.height() * 0.9))
        dlg.exec_()

    def _sync_payment_edit_state(self, invoice_id: int):
        try:
            txn = self.api.transaction_get(int(invoice_id))
        except Exception:
            return
        if not isinstance(txn, dict) or int(txn.get("id", 0) or 0) != int(invoice_id):
            return
        if self._edit_transaction_id is not None and int(self._edit_transaction_id) == int(invoice_id):
            try:
                self._edit_existing_paid = max(0.0, float(txn.get("paid", 0.0) or 0.0))
            except Exception:
                self._edit_existing_paid = 0.0
            self.paid_spin.setValue(0.0)
            self._recalc_totals()
            self._load_products_cache()

    def _load_transaction_into_cart(self, txn: dict):
        tx_id = int(txn.get("id", 0) or 0)
        raw_items = txn.get("items") or []
        items = []
        original_qty_map: dict[int, int] = {}
        for it in raw_items:
            try:
                pid = int(it.get("id", 0) or 0)
                qty = max(0, int(it.get("quantity", 0) or 0))
            except Exception:
                continue
            if pid <= 0 or qty <= 0:
                continue
            items.append({"id": pid, "quantity": qty})
            original_qty_map[pid] = int(original_qty_map.get(pid, 0) or 0) + qty
        if tx_id <= 0 or not items:
            QtWidgets.QMessageBox.information(self, "Invoice", "Invoice has no editable items.")
            return
        self._load_products_cache()
        try:
            existing_paid = float(txn.get("paid", 0.0) or 0.0)
        except Exception:
            existing_paid = 0.0
        self._set_invoice_edit_mode(tx_id, original_qty_map, existing_paid=existing_paid)
        self._clear_cart()
        try:
            cust_id = int(txn.get("customer_id", 0) or 0)
        except Exception:
            cust_id = 0
        idx = self.customer.findData(cust_id)
        self.customer.setCurrentIndex(idx if idx >= 0 else 0)
        try:
            self.discount.setValue(float(txn.get("discount", 0.0) or 0.0))
        except Exception:
            self.discount.setValue(0.0)

        skipped = []
        for it in items:
            pid = int(it["id"])
            qty = int(it["quantity"])
            prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == pid), None)
            if not prod:
                prod = {
                    "id": pid,
                    "name": f"Product #{pid}",
                    "company_id": 0,
                    "company_name": "",
                    "price": 0.0,
                    "quantity": int(original_qty_map.get(pid, 0) or 0),
                }
            row = self._add_product_to_cart(prod)
            if row is None:
                skipped.append(str(pid))
                continue
            qty_spin = self.table.cellWidget(row, 5)
            if isinstance(qty_spin, QtWidgets.QSpinBox):
                qty_spin.setValue(qty)
            self._recalc_row(row)

        self._recalc_totals()
        if self.table.rowCount() <= 0:
            self._exit_invoice_edit_mode()
            QtWidgets.QMessageBox.information(self, "Invoice", "Could not load invoice into cart.")
            return
        if skipped:
            QtWidgets.QMessageBox.warning(
                self,
                "Invoice",
                f"Some invoice items could not be loaded ({', '.join(skipped)}).",
            )
        self._focus_cart_cell(0, 2)

    # ---------- Cart ops ----------
    def _make_money_spin(self, value):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setMaximum(10**9)
        spin.setDecimals(2)
        spin.setValue(float(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        return spin

    def _make_pct_spin(self, value):
        spin = QtWidgets.QDoubleSpinBox()
        spin.setRange(0.0, 100.0)
        spin.setDecimals(2)
        spin.setValue(float(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        return spin

    def _make_qty_spin(self, value):
        spin = QtWidgets.QSpinBox()
        spin.setRange(1, 10**9)
        spin.setValue(int(value))
        spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
        return spin

    def _add_product_to_cart(self, product: dict):
        row = self.table.rowCount()
        pid_for_stock = int(product.get("id", 0) or 0)
        if pid_for_stock:
            existing_row = self._find_row_for_product(pid_for_stock)
            if existing_row is not None:
                QtWidgets.QMessageBox.information(self, "Already added", "This product is already in the cart.")
                self._focus_cart_cell(existing_row, 5)
                return existing_row
            available = self._available_stock(pid_for_stock)
            if available <= 0:
                QtWidgets.QMessageBox.information(self, "Insufficient stock", "No remaining quantity for this product.")
                return
        self.table.insertRow(row)

        # Product column
        name = str(product.get("name", ""))
        company = str(product.get("company_name", ""))
        label = f"{name} ({company})" if company else name
        prod_item = QtWidgets.QTableWidgetItem(label)
        prod_item.setFlags(prod_item.flags() & ~QtCore.Qt.ItemIsEditable)
        prod_item.setData(
            QtCore.Qt.UserRole,
            {
                "id": int(product.get("id", 0) or 0),
                "company_id": int(product.get("company_id", 0) or 0),
            },
        )
        self.table.setItem(row, 0, prod_item)

        # Retail (disabled money spin)
        retail = float(product.get("price", 0.0) or 0.0)
        retail_spin = self._make_money_spin(retail)
        retail_spin.setEnabled(False)
        self.table.setCellWidget(row, 1, retail_spin)

        # % Discount, Trade, Addl %, Qty
        raw_pct = product.get("discount_pct")
        if raw_pct is None:
            raw_pct = product.get("purchase_discount")
        try:
            pct_default = float(raw_pct) if raw_pct is not None else None
        except Exception:
            pct_default = None
        try:
            raw_trade = product.get("trade_price", None)
            trade_default = float(raw_trade) if raw_trade is not None else None
        except Exception:
            trade_default = None
        if pct_default is None and trade_default is not None and retail > 0:
            try:
                pct_default = max(0.0, (1.0 - (trade_default / retail)) * 100.0)
            except Exception:
                pct_default = None
        if trade_default is None and pct_default is not None:
            try:
                trade_default = retail * (1.0 - (pct_default / 100.0))
            except Exception:
                trade_default = None
        pct_spin = self._make_pct_spin(pct_default or 0.0)
        trade_item = QtWidgets.QTableWidgetItem(f"{float(trade_default or retail):.2f}")
        trade_item.setFlags(trade_item.flags() & ~QtCore.Qt.ItemIsEditable)
        extra_spin = self._make_pct_spin(0.0)
        qty_spin = self._make_qty_spin(1)
        self.table.setCellWidget(row, 2, pct_spin)
        self.table.setItem(row, 3, trade_item)
        self.table.setCellWidget(row, 4, extra_spin)
        self.table.setCellWidget(row, 5, qty_spin)

        # Line total
        line_total = QtWidgets.QTableWidgetItem("0.00")
        line_total.setFlags(line_total.flags() & ~QtCore.Qt.ItemIsEditable)
        self.table.setItem(row, 6, line_total)

        # Connect recalc triggers (keep qty/discount within stock)
        for col in (1, 2, 4, 5):
            w = self.table.cellWidget(row, col)
            if w:
                w.valueChanged.connect(lambda _=None, rr=row: self._on_row_value_changed(rr))
        # Capture arrow keys directly from editors for fast keyboard navigation.
        for col in (2, 4, 5):
            w = self.table.cellWidget(row, col)
            if w:
                w.installEventFilter(self)
                try:
                    le = w.lineEdit() if hasattr(w, "lineEdit") else None
                except Exception:
                    le = None
                if le is not None:
                    le.installEventFilter(self)
        # Allow keyboard focus without mouse
        self._focus_cart_cell(row, 2)
        self._recalc_row(row)
        self._recalc_totals()
        return row

    def _remove_row(self, row: int):
        if 0 <= row < self.table.rowCount():
            self.table.removeRow(row)
            self._recalc_totals()

    def _remove_selected_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self._remove_row(r)

    def _clear_cart(self):
        self.table.setRowCount(0)
        self._recalc_totals()
        self.discount.setValue(0.0)
        self.paid_spin.setValue(0.0)

    def _available_stock(self, product_id: int, exclude_row: int | None = None) -> int:
        """Return remaining stock after accounting for items already in cart."""
        try:
            prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == product_id), None)
            stock = int(prod.get("quantity", 0)) if prod else 0
        except Exception:
            stock = 0
        # When editing an existing invoice, include previously deducted qty for that invoice.
        try:
            stock += int(self._edit_original_qty_by_product.get(int(product_id), 0) or 0)
        except Exception:
            pass
        # Subtract quantities already in cart for this product
        used = 0
        for r in range(self.table.rowCount()):
            if exclude_row is not None and r == exclude_row:
                continue
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                if int(meta.get("id", 0) or 0) == product_id:
                    used += int(self.table.cellWidget(r, 5).value())
            except Exception:
                pass
        return max(0, stock - used)

    def _recalc_row(self, r: int):
        try:
            retail = float(self.table.cellWidget(r, 1).value())
            pct = float(self.table.cellWidget(r, 2).value())
            extra = float(self.table.cellWidget(r, 4).value())
            qty = int(self.table.cellWidget(r, 5).value())
            trade = retail * (1.0 - (pct / 100.0))
            final = trade * (1.0 - (extra / 100.0))
            self.table.item(r, 3).setText(f"{trade:.2f}")
            self.table.item(r, 6).setText(f"{final * qty:.2f}")
            # Refresh totals when any row value changes
            self._recalc_totals()
        except Exception:
            pass

    def _on_row_value_changed(self, r: int):
        # Enforce available stock constraint before recalculating totals
        try:
            meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
            pid = int(meta.get("id", 0) or 0)
            if pid:
                max_qty = self._available_stock(pid, exclude_row=r)
                qty_spin = self.table.cellWidget(r, 5)
                if qty_spin and qty_spin.value() > max_qty:
                    qty_spin.setValue(max_qty)
                    QtWidgets.QMessageBox.information(
                        self,
                        "Insufficient stock",
                        f"Quantity exceeds available stock. Adjusted to {max_qty}.",
                    )
        except Exception:
            pass
        self._recalc_row(r)

    def _focus_next_cart_field(self):
        """Move focus to the next editable cart field (discount -> addl -> qty -> next row)."""
        editable_cols = [2, 4, 5]  # discount, addl %, qty
        row = self.table.currentRow()
        if row < 0 and self.table.rowCount() > 0:
            row = 0
            self.table.setCurrentCell(row, editable_cols[0])
        current_col = self.table.currentColumn()
        focus_w = self.focusWidget()
        # Try to infer current column from focused widget
        if focus_w:
            for c in editable_cols:
                if self.table.cellWidget(row, c) is focus_w:
                    current_col = c
                    break
        try:
            idx = editable_cols.index(current_col)
        except ValueError:
            idx = -1
        # If we're on qty (end of row)
        if current_col == 5 or idx == len(editable_cols) - 1:
            if row + 1 < self.table.rowCount():
                # Move to next row's discount
                self._focus_cart_cell(row + 1, editable_cols[0])
            else:
                # Last row: go back to search to add next product
                self._focus_search()
            return
        if idx + 1 < len(editable_cols):
            next_col = editable_cols[idx + 1]
            next_row = row
        else:
            next_col = editable_cols[0]
            next_row = row + 1
        if next_row >= self.table.rowCount():
            next_row = row  # stay on last row
        self._focus_cart_cell(next_row, next_col)

    def _focus_prev_cart_field(self):
        """Move focus to previous editable cart field (qty -> addl -> discount -> prev row)."""
        editable_cols = [2, 4, 5]
        row = self.table.currentRow()
        if row < 0:
            if self.table.rowCount() <= 0:
                return
            row = 0
            self.table.setCurrentCell(row, editable_cols[0])
        current_col = self.table.currentColumn()
        focus_w = self.focusWidget()
        if focus_w:
            for c in editable_cols:
                if self.table.cellWidget(row, c) is focus_w:
                    current_col = c
                    break
                w = self.table.cellWidget(row, c)
                try:
                    le = w.lineEdit() if (w is not None and hasattr(w, "lineEdit")) else None
                except Exception:
                    le = None
                if le is focus_w:
                    current_col = c
                    break
        try:
            idx = editable_cols.index(current_col)
        except ValueError:
            idx = 0
        if current_col == editable_cols[0] or idx <= 0:
            if row - 1 >= 0:
                self._focus_cart_cell(row - 1, editable_cols[-1])
            else:
                self._focus_search()
            return
        prev_col = editable_cols[idx - 1]
        self._focus_cart_cell(row, prev_col)

    def _cart_widget_position(self, obj):
        """Find table row/col for a cart editor widget or its inner line edit."""
        for r in range(self.table.rowCount()):
            for c in (2, 4, 5):
                w = self.table.cellWidget(r, c)
                if w is None:
                    continue
                if obj is w:
                    return r, c
                try:
                    le = w.lineEdit() if hasattr(w, "lineEdit") else None
                except Exception:
                    le = None
                if le is not None and obj is le:
                    return r, c
        return None, None

    def _focus_cart_cell(self, row: int, col: int):
        self.table.setCurrentCell(row, col)
        w = self.table.cellWidget(row, col)
        if w:
            w.setFocus()
            if hasattr(w, "lineEdit") and w.lineEdit():
                try:
                    w.lineEdit().selectAll()
                except Exception:
                    pass

    def _focus_cart_from_search(self):
        """Jump from search box to an editable field in the active cart row."""
        if self.table.rowCount() <= 0:
            return
        row = self.table.currentRow()
        if row < 0 or row >= self.table.rowCount():
            row = self.table.rowCount() - 1
        self._focus_cart_cell(row, 2)

    def _find_row_for_product(self, pid: int):
        for r in range(self.table.rowCount()):
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                if int(meta.get("id", 0) or 0) == pid:
                    return r
            except Exception:
                pass
        return None

    # ---------- Hold/Resume ----------
    def _snapshot_cart(self) -> dict:
        items = []
        for r in range(self.table.rowCount()):
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                pid = int(meta.get("id", 0) or 0)
                cid = int(meta.get("company_id", 0) or 0)
                retail = float(self.table.cellWidget(r, 1).value())
                pct = float(self.table.cellWidget(r, 2).value())
                trade = float(self.table.item(r, 3).text() or 0.0)
                extra = float(self.table.cellWidget(r, 4).value())
                qty = int(self.table.cellWidget(r, 5).value())
                items.append(
                    {
                        "product_id": pid,
                        "company_id": cid,
                        "retail": retail,
                        "pct": pct,
                        "trade": trade,
                        "extra": extra,
                        "qty": qty,
                        "label": self.table.item(r, 0).text(),
                    }
                )
            except Exception:
                pass
        try:
            cust_id = int(self.customer.currentData() or 0)
        except Exception:
            cust_id = 0
        return {
            "items": items,
            "discount": float(self.discount.value() or 0.0),
            "paid": float(self.paid_spin.value() or 0.0),
            "customer_id": cust_id,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _load_cart_from_snapshot(self, snap: dict):
        self._clear_cart()
        # Restore customer and discount
        cust_id = int(snap.get("customer_id", 0) or 0)
        if cust_id:
            idx = self.customer.findData(cust_id)
            if idx >= 0:
                self.customer.setCurrentIndex(idx)
        self.discount.setValue(float(snap.get("discount", 0.0) or 0.0))
        self.paid_spin.setValue(float(snap.get("paid", 0.0) or 0.0))
        # Restore items
        for it in snap.get("items", []):
            pid = int(it.get("product_id", 0) or 0)
            prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == pid), None) or {
                "id": pid,
                "name": it.get("label", f"ID {pid}"),
                "company_id": it.get("company_id", 0),
                "price": it.get("retail", 0.0),
                "company_name": "",
            }
            row = self._add_product_to_cart(prod)
            if row is None:
                continue
            try:
                self.table.cellWidget(row, 1).setValue(float(it.get("retail", 0.0)))
                self.table.cellWidget(row, 2).setValue(float(it.get("pct", 0.0)))
                trade_val = float(it.get("trade", 0.0))
                self.table.item(row, 3).setText(f"{trade_val:.2f}")
                self.table.cellWidget(row, 4).setValue(float(it.get("extra", 0.0)))
                self.table.cellWidget(row, 5).setValue(int(it.get("qty", 1)))
                self._recalc_row(row)
            except Exception:
                pass
        self._recalc_totals()

    def _hold_sale(self):
        if self._edit_transaction_id is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Invoice Edit",
                "Finish or cancel invoice editing before holding a sale.",
            )
            return
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Empty", "No items to hold.")
            return
        snap = self._snapshot_cart()
        default_name = f"Hold {datetime.now().strftime('%H:%M:%S')}"
        name, ok = QtWidgets.QInputDialog.getText(self, "Hold Sale", "Name this hold:", text=default_name)
        if not ok:
            return
        snap["name"] = (name or "").strip() or default_name
        self.held_sales.append(snap)
        self._clear_cart()
        QtWidgets.QMessageBox.information(self, "Held", f"Sale held as \"{snap['name']}\".")

    def _resume_sale(self):
        if self._edit_transaction_id is not None:
            QtWidgets.QMessageBox.information(
                self,
                "Invoice Edit",
                "Finish or cancel invoice editing before resuming a held sale.",
            )
            return
        if not self.held_sales:
            QtWidgets.QMessageBox.information(self, "None", "No held sales.")
            return
        # Ensure product cache is fresh for stock checks
        self._load_products_cache()
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Resume Sale")
        v = QtWidgets.QVBoxLayout(dlg)
        listw = QtWidgets.QListWidget()
        for idx, snap in enumerate(self.held_sales):
            label = snap.get("name", f"Hold {idx+1}")
            ts = snap.get("created", "")
            cnt = len(snap.get("items", []))
            item = QtWidgets.QListWidgetItem(f"{label} ({cnt} items) {ts}")
            item.setData(QtCore.Qt.UserRole, idx)
            listw.addItem(item)
        if listw.count() > 0:
            listw.setCurrentRow(0)
        v.addWidget(listw)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        v.addWidget(btns)
        listw.itemActivated.connect(lambda _item: dlg.accept())
        listw.itemDoubleClicked.connect(lambda _item: dlg.accept())
        QtCore.QTimer.singleShot(0, lambda: listw.setFocus())
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        sel = listw.currentItem()
        if not sel:
            return
        idx = int(sel.data(QtCore.Qt.UserRole))
        selected_snap = self.held_sales.pop(idx)
        # If user switches holds while cart has items, park current cart back into holds.
        if self.table.rowCount() > 0:
            parked = self._snapshot_cart()
            parked["name"] = f"Hold {datetime.now().strftime('%H:%M:%S')}"
            self.held_sales.append(parked)
        self._load_cart_from_snapshot(selected_snap)

    def _with_loader(self, message: str, fn, *args, **kwargs):
        dlg = QtWidgets.QProgressDialog(message, None, 0, 0, self)
        dlg.setWindowTitle("Please wait")
        dlg.setCancelButton(None)
        dlg.setWindowModality(QtCore.Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.show()
        QtWidgets.QApplication.processEvents()
        try:
            return fn(*args, **kwargs)
        finally:
            dlg.close()
            QtWidgets.QApplication.processEvents()

    def _recalc_totals(self):
        # Subtotal
        subtotal = 0.0
        for r in range(self.table.rowCount()):
            try:
                subtotal += float(self.table.item(r, 6).text() or 0.0)
            except Exception:
                pass
        # Discount (global)
        discount_pct = float(self.discount.value() or 0.0)
        discounted = subtotal * (1.0 - discount_pct / 100.0)
        # VAT
        vat_amount = discounted * (self.vat_percent / 100.0)
        grand = discounted + vat_amount
        try:
            payment_input = float(self.paid_spin.value() or 0.0)
        except Exception:
            payment_input = 0.0
        existing_paid = float(self._edit_existing_paid or 0.0) if self._edit_transaction_id is not None else 0.0
        paid_amount = existing_paid + payment_input
        due_amount = max(0.0, grand - paid_amount)
        self.subtotal_label.setText(f"{subtotal:.2f}")
        self.vat_label.setText(f"{vat_amount:.2f} ({self.vat_percent:.2f}%)")
        self.total_label.setText(f"{grand:.2f}")
        self.paid_prior_value_label.setText(f"{existing_paid:.2f}")
        self.paid_total_value_label.setText(f"{paid_amount:.2f}")
        self.due_label.setText(f"{due_amount:.2f}")

    # ---------- Checkout ----------
    def checkout(self):
        if self.table.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Empty", "No items in cart.")
            return
        items = []
        for r in range(self.table.rowCount()):
            try:
                meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                pid = int(meta.get("id", 0) or 0)
                qty_w = self.table.cellWidget(r, 5)
                qty = int(qty_w.value()) if isinstance(qty_w, QtWidgets.QSpinBox) else 1
                if pid and qty > 0:
                    items.append({"id": pid, "quantity": qty})
            except Exception:
                pass
        if not items:
            QtWidgets.QMessageBox.information(self, "Empty", "No valid items to checkout.")
            return

        try:
            # Totals
            subtotal = 0.0
            for r in range(self.table.rowCount()):
                try:
                    subtotal += float(self.table.item(r, 6).text() or 0.0)
                except Exception:
                    pass
            discount_pct = float(self.discount.value() or 0.0)
            discounted = subtotal * (1.0 - discount_pct / 100.0)
            vat_amount = discounted * (self.vat_percent / 100.0)
            grand = discounted + vat_amount
            payment_input = float(self.paid_spin.value() or 0.0)
            existing_paid = float(self._edit_existing_paid or 0.0) if self._edit_transaction_id is not None else 0.0
            paid_amount = existing_paid + payment_input
            due_amount = max(0.0, grand - paid_amount)
            if paid_amount - grand > 1e-6:
                over = paid_amount - grand
                if self._edit_transaction_id is not None:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Overpayment",
                        (
                            f"Paid amount ({paid_amount:.2f}) exceeds updated invoice total ({grand:.2f}) "
                            f"by {over:.2f}.\nReduce Add Payment or edit payment history."
                        ),
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Overpayment",
                        (
                            f"Paid amount ({paid_amount:.2f}) exceeds invoice total ({grand:.2f}) by {over:.2f}.\n"
                            "Reduce paid amount."
                        ),
                    )
                return

            try:
                cust_id = int(self.customer.currentData() or 0)
            except Exception:
                cust_id = 0

            payload = {
                "customer_id": cust_id,
                "user_id": int(self.user_id or 0),
                "total": grand,
                "paid": paid_amount,
                "discount": discount_pct,
                "items": items,
            }
            if self._edit_transaction_id is not None:
                tx_id = int(self._edit_transaction_id)
                resp = self._with_loader(
                    "Updating invoice...",
                    lambda: self.api.transaction_update(tx_id, payload),
                )
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    raise Exception(str(resp.get("detail")))
                invoice_id = int(resp.get("id", tx_id) or tx_id) if isinstance(resp, dict) else tx_id
                self._print_receipt(
                    items,
                    subtotal,
                    discount_pct,
                    vat_amount,
                    self.vat_percent,
                    grand,
                    invoice_number=invoice_id,
                    paid_amount=paid_amount,
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    f"Invoice #{invoice_id} updated. Added: {payment_input:.2f}, Due: {due_amount:.2f}",
                )
            else:
                resp = self._with_loader("Completing checkout...", lambda: self.api.transaction_new(payload))
                if isinstance(resp, dict) and resp.get("detail") and not resp.get("id"):
                    raise Exception(str(resp.get("detail")))
                invoice_id = int(resp.get("id", 0) or 0) if isinstance(resp, dict) else 0
                self._print_receipt(
                    items,
                    subtotal,
                    discount_pct,
                    vat_amount,
                    self.vat_percent,
                    grand,
                    invoice_number=invoice_id if invoice_id > 0 else None,
                    paid_amount=paid_amount,
                )
                msg = (
                    f"Checkout complete. Invoice #{invoice_id}. Due: {due_amount:.2f}"
                    if invoice_id > 0
                    else f"Checkout complete. Due: {due_amount:.2f}"
                )
                QtWidgets.QMessageBox.information(self, "Success", msg)
            self._load_products_cache()
            self._exit_invoice_edit_mode()
            self._clear_cart()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    # ---------- Receipt ----------
    def _print_receipt(
        self,
        items,
        gross,
        discount_pct,
        vat_amount,
        vat_pct,
        total_with_vat,
        invoice_number=None,
        paid_amount=None,
    ):
        printer = QtPrintSupport.QPrinter()
        dialog = QtPrintSupport.QPrintDialog(printer, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        doc = QtGui.QTextDocument()
        cust_name = self.customer.currentText() or "Walk-in"
        try:
            s = self.api.settings_map() or {}
            settings = s.get("settings", {}) or {}
        except Exception:
            settings = {}
        business_name = settings.get("business_name", "PharmaSpot")
        receipt_footer = settings.get("receipt_footer", "Thank you for your purchase!")
        logo_path = settings.get("logo_path", "assets/images/logo.svg")
        logo_data_uri = ""
        try:
            p = Path(logo_path)
            if not p.is_file():
                p = Path.cwd() / logo_path
            with p.open("rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            ext = p.suffix.lower()
            mime = "image/svg+xml" if ext == ".svg" else ("image/png" if ext == ".png" else "image/jpeg")
            logo_data_uri = f"data:{mime};base64,{b64}"
        except Exception:
            logo_data_uri = ""

        rows = []
        for it in items:
            try:
                pid = int(it.get("id", 0) or 0)
                # Lookup row to read final unit price
                name = str(pid)
                final_price = 0.0
                qty = int(it.get("quantity", 0) or 0)
                for r in range(self.table.rowCount()):
                    meta = self.table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                    if int(meta.get("id", 0) or 0) == pid:
                        name = self.table.item(r, 0).text()
                        retail = float(self.table.cellWidget(r, 1).value())
                        pct = float(self.table.cellWidget(r, 2).value())
                        extra = float(self.table.cellWidget(r, 4).value())
                        trade = retail * (1.0 - (pct / 100.0))
                        final_price = trade * (1.0 - (extra / 100.0))
                        break
                rows.append(
                    f"<tr><td>{name}</td><td style='text-align:center'>{qty}</td>"
                    f"<td style='text-align:right'>{final_price:.2f}</td></tr>"
                )
            except Exception:
                pass

        now = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        logo_html = f"<img src='{logo_data_uri}' style='max-height:60px'/>" if logo_data_uri else ""
        invoice_line = f"Invoice #: {int(invoice_number)}<br/>" if invoice_number else ""
        try:
            paid_val = float(total_with_vat if paid_amount is None else paid_amount)
        except Exception:
            paid_val = float(total_with_vat or 0.0)
        due_val = max(0.0, float(total_with_vat or 0.0) - paid_val)
        html = f"""
        <div style='text-align:center'>
            {logo_html}
            <div style='font-size:16px;font-weight:bold'>{business_name}</div>
            <div style='font-size:12px'>Receipt</div>
        </div>
        <p>Date: {now}<br/>{invoice_line}Customer: {cust_name}</p>
        <table width='100%' border='0' cellspacing='0' cellpadding='2'>
        <tr><th align='left'>Item</th><th align='center'>Qty</th><th align='right'>Price</th></tr>
        {''.join(rows)}
        </table>
        <hr/>
        <p>
            Gross: {gross:.2f}<br/>
            Discount: {discount_pct:.2f}%<br/>
            VAT: {vat_amount:.2f} ({vat_pct:.2f}%)<br/>
            Total: {total_with_vat:.2f}<br/>
            Paid: {paid_val:.2f}<br/>
            <b>Due: {due_val:.2f}</b>
        </p>
        <div style='text-align:center;font-size:11px;margin-top:8px'>{receipt_footer}</div>
        """
        doc.setHtml(html)
        doc.print_(printer)

    # ---------- User ----------
    def set_user(self, user: dict):
        try:
            self.user_id = int(user.get("id", 0) or 0)
        except Exception:
            self.user_id = 0
