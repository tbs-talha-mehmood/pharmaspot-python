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
        self._build()
        self._load_customers()
        self._load_products_cache()
        self._load_settings()

    # ---------- UI ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)

        # Top: header + customer + global discount
        top = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Point of Sale")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(QtWidgets.QLabel("Customer:"))
        self.customer = QtWidgets.QComboBox()
        self.customer.setMinimumWidth(200)
        top.addWidget(self.customer)
        top.addSpacing(12)
        top.addWidget(QtWidgets.QLabel("Discount %:"))
        self.discount = QtWidgets.QDoubleSpinBox()
        self.discount.setRange(0, 100)
        self.discount.setDecimals(2)
        self.discount.setSingleStep(1.0)
        self.discount.valueChanged.connect(self._recalc_totals)
        top.addWidget(self.discount)
        root.addLayout(top)

        # Search row
        search_row = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Scan barcode or type to search products…")
        self.search.textChanged.connect(self._on_search_changed)
        self.search.returnPressed.connect(self._add_first_search_result)
        search_row.addWidget(self.search, 1)
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_products_cache)
        search_row.addWidget(self.refresh_btn)
        self.history_btn = QtWidgets.QPushButton("Purchase History")
        self.history_btn.clicked.connect(self._show_purchase_history)
        search_row.addWidget(self.history_btn)
        root.addLayout(search_row)

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
        root.addWidget(self.table, 1)

        # Bottom: totals + actions
        bottom = QtWidgets.QHBoxLayout()
        self.clear_btn = QtWidgets.QPushButton("Clear Cart")
        self.clear_btn.clicked.connect(self._clear_cart)
        bottom.addWidget(self.clear_btn)
        self.hold_btn = QtWidgets.QPushButton("Hold Sale")
        self.hold_btn.clicked.connect(self._hold_sale)
        bottom.addWidget(self.hold_btn)
        self.resume_btn = QtWidgets.QPushButton("Resume Sale")
        self.resume_btn.clicked.connect(self._resume_sale)
        bottom.addWidget(self.resume_btn)
        bottom.addStretch(1)

        totals_box = QtWidgets.QGroupBox("Totals")
        totals_layout = QtWidgets.QFormLayout(totals_box)
        self.subtotal_label = QtWidgets.QLabel("0.00")
        self.vat_label = QtWidgets.QLabel("0.00")
        self.total_label = QtWidgets.QLabel("0.00")
        font_bold = self.total_label.font()
        font_bold.setPointSize(font_bold.pointSize() + 1)
        font_bold.setBold(True)
        self.total_label.setFont(font_bold)
        totals_layout.addRow("Subtotal:", self.subtotal_label)
        totals_layout.addRow("VAT:", self.vat_label)
        totals_layout.addRow("Total:", self.total_label)
        bottom.addWidget(totals_box)

        self.checkout_btn = QtWidgets.QPushButton("Checkout")
        self.checkout_btn.setStyleSheet("padding: 8px 18px; font-size: 14px; font-weight: 600;")
        self.checkout_btn.clicked.connect(self.checkout)
        bottom.addWidget(self.checkout_btn)
        root.addLayout(bottom)

        # Shortcuts
        QtWidgets.QShortcut(QtGui.QKeySequence("F2"), self, activated=self._focus_search)
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self, activated=self._remove_selected_row)
        # Keyboard-only navigation helpers
        self.search.installEventFilter(self)
        self.table.installEventFilter(self)

    # ---------- Data loads ----------
    def _load_products_cache(self):
        try:
            self.products_cache = self.api.products() or []
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
        try:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)
            for c in self.api.customers():
                self.customer.addItem(c.get("name", "Customer"), int(c.get("id")))
        except Exception:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)

    # ---------- Search ----------
    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
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
                elif key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    if self.results.isVisible() and self.results.currentItem():
                        self._add_first_search_result()
                        return True
            elif obj is self.table:
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
                barcode = str(p.get("barcode", "") or "")
                pid = str(p.get("id", ""))
                if (
                    text_l in name.lower()
                    or (company and text_l in company.lower())
                    or (barcode and text_l in barcode.lower())
                    or (is_digits and text_raw == pid)
                ):
                    label = f"{name} ({company})" if company else name
                    if barcode:
                        label = f"{label} • {barcode}"
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
            docs = self.api.purchases_list() or []
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
        table.horizontalHeader().setStretchLastSection(True)
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
        table.resizeColumnsToContents()
        v.addWidget(table)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)
        dlg.exec_()

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

    def _available_stock(self, product_id: int, exclude_row: int | None = None) -> int:
        """Return remaining stock after accounting for items already in cart."""
        try:
            prod = next((p for p in self.products_cache if int(p.get("id", 0) or 0) == product_id), None)
            stock = int(prod.get("quantity", 0)) if prod else 0
        except Exception:
            stock = 0
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
        v.addWidget(listw)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        v.addWidget(btns)
        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        sel = listw.currentItem()
        if not sel:
            return
        idx = int(sel.data(QtCore.Qt.UserRole))
        snap = self.held_sales.pop(idx)
        self._load_cart_from_snapshot(snap)

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
        self.subtotal_label.setText(f"{subtotal:.2f}")
        self.vat_label.setText(f"{vat_amount:.2f} ({self.vat_percent:.2f}%)")
        self.total_label.setText(f"{grand:.2f}")

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

            try:
                cust_id = int(self.customer.currentData() or 0)
            except Exception:
                cust_id = 0

            payload = {
                "customer_id": cust_id,
                "user_id": int(self.user_id or 0),
                "total": grand,
                "paid": grand,
                "discount": discount_pct,
                "items": items,
            }
            self.api.transaction_new(payload)
            self._print_receipt(items, subtotal, discount_pct, vat_amount, self.vat_percent, grand)
            QtWidgets.QMessageBox.information(self, "Success", "Checkout complete")
            self._load_products_cache()
            self._clear_cart()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    # ---------- Receipt ----------
    def _print_receipt(self, items, gross, discount_pct, vat_amount, vat_pct, total_with_vat):
        printer = QtPrintSupport.QPrinter()
        dialog = QtPrintSupport.QPrintDialog(printer, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        doc = QtWidgets.QTextDocument()
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
        html = f"""
        <div style='text-align:center'>
            {logo_html}
            <div style='font-size:16px;font-weight:bold'>{business_name}</div>
            <div style='font-size:12px'>Receipt</div>
        </div>
        <p>Date: {now}<br/>Customer: {cust_name}</p>
        <table width='100%' border='0' cellspacing='0' cellpadding='2'>
        <tr><th align='left'>Item</th><th align='center'>Qty</th><th align='right'>Price</th></tr>
        {''.join(rows)}
        </table>
        <hr/>
        <p>
            Gross: {gross:.2f}<br/>
            Discount: {discount_pct:.2f}%<br/>
            VAT: {vat_amount:.2f} ({vat_pct:.2f}%)<br/>
            <b>Total: {total_with_vat:.2f}</b>
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
