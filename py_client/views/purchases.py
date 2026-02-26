from PyQt5 import QtWidgets, QtCore, QtGui


class PurchasesView(QtWidgets.QWidget):
    inventory_changed = QtCore.pyqtSignal()
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._products_cache = None
        self._build()
        self.refresh_history()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        self.new_tab = QtWidgets.QWidget()
        self.history_tab = QtWidgets.QWidget()
        self.tabs.addTab(self.new_tab, "New Purchase")
        self.tabs.addTab(self.history_tab, "History")

        self._build_new_purchase(self.new_tab)
        self._build_history(self.history_tab)

    def _build_new_purchase(self, parent):
        v = QtWidgets.QVBoxLayout(parent)

        form = QtWidgets.QFormLayout()
        self.supplier_cb = QtWidgets.QComboBox()
        self.supplier_cb.setEditable(True)
        self._load_suppliers()
        form.addRow("Supplier", self.supplier_cb)
        v.addLayout(form)

        hint = QtWidgets.QLabel("Trade = Retail minus % Discount; Addl % applies to Trade.")
        v.addWidget(hint)

        # Inline search (POS-style)
        search_row = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Search product by name")
        self.search.textChanged.connect(self._on_search_changed)
        self.search.returnPressed.connect(self._add_first_search_result)
        self.search.installEventFilter(self)
        search_row.addWidget(self.search, 1)
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(lambda: self._load_products(force=True))
        search_row.addWidget(self.refresh_btn)
        v.addLayout(search_row)

        self.results = QtWidgets.QListWidget()
        self.results.setVisible(False)
        self.results.setMaximumHeight(160)
        self.results.itemActivated.connect(self._on_result_activate)
        v.addWidget(self.results)

        self.items_table = QtWidgets.QTableWidget(0, 8)
        self.items_table.setHorizontalHeaderLabels(
            ["Product", "Retail", "% Discount", "Trade", "Addl %", "Qty", "Line Total", "Cut"]
        )
        self.items_table.horizontalHeader().setStretchLastSection(True)
        self.items_table.setAlternatingRowColors(True)
        v.addWidget(self.items_table)
        self._suppress_item_change = False
        # Enable keyboard navigation within the items table
        self.items_table.installEventFilter(self)

        btns_bar = QtWidgets.QHBoxLayout()
        self.btn_remove = QtWidgets.QPushButton("Remove Item")
        self.btn_clear = QtWidgets.QPushButton("Clear")
        btns_bar.addWidget(self.btn_remove)
        btns_bar.addWidget(self.btn_clear)
        btns_bar.addStretch(1)
        v.addLayout(btns_bar)

        total_bar = QtWidgets.QHBoxLayout()
        self.total_label = QtWidgets.QLabel("Total: 0.00")
        total_bar.addStretch(1)
        total_bar.addWidget(self.total_label)
        v.addLayout(total_bar)

        action_bar = QtWidgets.QHBoxLayout()
        self.btn_save = QtWidgets.QPushButton("Save Purchase")
        self.btn_cancel_edit = QtWidgets.QPushButton("Cancel Edit")
        self.btn_cancel_edit.setVisible(False)
        action_bar.addStretch(1)
        action_bar.addWidget(self.btn_cancel_edit)
        action_bar.addWidget(self.btn_save)
        v.addLayout(action_bar)

        self.btn_remove.clicked.connect(self._remove_item)
        self.btn_clear.clicked.connect(self._clear_items)
        self.btn_save.clicked.connect(self._save_purchase)
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)
        self.items_table.itemChanged.connect(self._on_item_changed)
        # Keyboard shortcuts similar to POS
        QtWidgets.QShortcut(QtGui.QKeySequence("F2"), self, activated=self._focus_search)
        QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self, activated=self._remove_item)

    def _build_history(self, parent):
        v = QtWidgets.QVBoxLayout(parent)
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Purchase History"))
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_edit = QtWidgets.QPushButton("Edit")
        self.btn_delete = QtWidgets.QPushButton("Delete")
        header.addWidget(self.btn_refresh)
        header.addWidget(self.btn_edit)
        header.addWidget(self.btn_delete)
        header.addStretch(1)
        v.addLayout(header)

        self.history_table = QtWidgets.QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(["ID", "Date", "Supplier", "Items", "Total"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setColumnHidden(0, True)
        self.history_table.setAlternatingRowColors(True)
        v.addWidget(self.history_table)

        self.btn_refresh.clicked.connect(self.refresh_history)
        self.btn_edit.clicked.connect(self._edit_selected)
        self.btn_delete.clicked.connect(self._delete_selected)

    def _load_products(self, force: bool = False):
        if force or self._products_cache is None:
            self._products_cache = self.api.products() or []
        return self._products_cache

    def _load_suppliers(self):
        self.supplier_cb.clear()
        self.supplier_cb.addItem("Select or type name", 0)
        try:
            for c in self.api.companies() or []:
                self.supplier_cb.addItem(c.get("name", ""), int(c.get("id")))
        except Exception:
            pass


    def _product_picker(self, parent):
        d = QtWidgets.QDialog(parent)
        d.setWindowTitle("Add Item")
        v = QtWidgets.QVBoxLayout(d)
        products = self._load_products(force=True)
        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("Search product by name")
        results = QtWidgets.QListWidget()
        results.setMinimumHeight(200)
        v.addWidget(search)
        v.addWidget(results)
        qty = QtWidgets.QSpinBox()
        qty.setRange(1, 10**9)
        qty.setValue(1)
        retail = QtWidgets.QDoubleSpinBox()
        retail.setMaximum(10**9)
        retail.setDecimals(2)
        retail.setValue(0.0)
        cut_rate = QtWidgets.QCheckBox("Cut rate item")
        trade = QtWidgets.QDoubleSpinBox()
        trade.setMaximum(10**9)
        trade.setDecimals(2)
        trade.setValue(0.0)
        trade.setEnabled(False)
        available_lbl = QtWidgets.QLabel("Available: -")
        form = QtWidgets.QFormLayout()
        form.addRow("Quantity", qty)
        form.addRow("Retail Price", retail)
        form.addRow("Cut rate", cut_rate)
        form.addRow("Trade Price", trade)
        form.addRow("In Stock", available_lbl)
        v.addLayout(form)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        v.addWidget(btns)
        btns.accepted.connect(d.accept)
        btns.rejected.connect(d.reject)

        def _populate(term: str):
            results.clear()
            needle = term.strip().lower()
            if not needle:
                return
            for p in products:
                name = str(p.get("name", ""))
                if needle in name.lower():
                    company = str(p.get("company_name", ""))
                    qty_avail = p.get("quantity", 0)
                    label = f"{name} ({company})" if company else name
                    label = f"{label} • Stock: {qty_avail}"
                    item = QtWidgets.QListWidgetItem(label)
                    item.setData(QtCore.Qt.UserRole, int(p.get("id")))
                    results.addItem(item)

        def _sync_price():
            item = results.currentItem()
            if not item:
                return
            pid = int(item.data(QtCore.Qt.UserRole))
            prod = next((p for p in products if int(p.get("id")) == pid), None)
            if prod:
                try:
                    retail.setValue(float(prod.get("price", 0.0)))
                    if not cut_rate.isChecked():
                        trade.setValue(float(prod.get("price", 0.0)))
                except Exception:
                    pass
                try:
                    available_lbl.setText(f"Available: {int(prod.get('quantity', 0) or 0)}")
                except Exception:
                    available_lbl.setText("Available: -")

        search.textChanged.connect(_populate)
        results.currentItemChanged.connect(lambda _cur, _prev: _sync_price())
        cut_rate.toggled.connect(lambda checked: trade.setEnabled(checked))
        return d, results, qty, retail, cut_rate, trade

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

    # ---------- Search like POS ----------
    def _focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _on_search_changed(self, text: str):
        text_raw = (text or "").strip()
        text_l = text_raw.lower()
        self.results.clear()
        products = self._load_products()
        if not text_l:
            self.results.setVisible(False)
            return
        count = 0
        for p in products:
            try:
                name = str(p.get("name", ""))
                company = str(p.get("company_name", ""))
                pid = str(p.get("id", ""))
                if (
                    text_l in name.lower()
                    or (company and text_l in company.lower())
                    or (text_raw.isdigit() and text_raw == pid)
                ):
                    qty_avail = p.get("quantity", 0)
                    label = f"{name} ({company})" if company else name
                    label = f"{label} • Stock: {qty_avail}"
                    item = QtWidgets.QListWidgetItem(label)
                    item.setData(QtCore.Qt.UserRole, int(p.get("id")))
                    self.results.addItem(item)
                    count += 1
                    if count >= 100:
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
        products = self._load_products()
        prod = next((p for p in products if int(p.get("id", 0) or 0) == pid), None)
        if not prod:
            return
        row = self._add_product_to_table(prod)
        if row is None:
            return
        self.search.clear()
        self.results.setVisible(False)

    def _add_product_to_table(self, product: dict):
        existing = self._find_row_for_product(int(product.get("id", 0) or 0))
        if existing is not None:
            QtWidgets.QMessageBox.warning(self, "Already added", "This product is already in the list.")
            self._focus_items_cell(existing, 1)
            return None
        name = str(product.get("name", ""))
        company = str(product.get("company_name", ""))
        label = f"{name} ({company})" if company else name
        pid = int(product.get("id", 0) or 0)
        company_id = int(product.get("company_id", 0) or 0)
        retail = float(product.get("price", 0.0) or 0.0)
        discount = float(product.get("discount_pct", product.get("purchase_discount", 0.0)) or 0.0)
        trade = product.get("trade_price")
        if trade is None:
            try:
                trade = retail * (1.0 - (discount / 100.0))
            except Exception:
                trade = retail
        row = self._add_row(pid, label, 1, retail, company_id, False, float(trade or retail), discount, 0.0)
        self._focus_items_cell(row, 1)
        return row


    def _add_row(self, prod_id, prod_name, qty, retail_price, company_id=0, is_cut_rate=False, trade_price=0.0, discount_pct=0.0, extra_pct=0.0):
        r = self.items_table.rowCount()
        self.items_table.insertRow(r)
        prod_item = QtWidgets.QTableWidgetItem(prod_name)
        prod_item.setData(QtCore.Qt.UserRole, {"product_id": int(prod_id), "company_id": int(company_id or 0)})
        prod_item.setFlags(prod_item.flags() & ~QtCore.Qt.ItemIsEditable)
        self.items_table.setItem(r, 0, prod_item)
        retail_spin = self._make_money_spin(retail_price)
        self.items_table.setCellWidget(r, 1, retail_spin)
        pct_spin = self._make_pct_spin(discount_pct)
        extra_spin = self._make_pct_spin(extra_pct)
        qty_spin = self._make_qty_spin(qty)
        trade_item = QtWidgets.QTableWidgetItem(f"{float(trade_price or retail_price):.2f}")
        trade_item.setFlags(trade_item.flags() & ~QtCore.Qt.ItemIsEditable)
        cut_cb = QtWidgets.QCheckBox()
        cut_cb.setChecked(bool(is_cut_rate))
        self.items_table.setCellWidget(r, 2, pct_spin)
        self.items_table.setItem(r, 3, trade_item)
        self.items_table.setCellWidget(r, 4, extra_spin)
        self.items_table.setCellWidget(r, 5, qty_spin)
        self.items_table.setItem(r, 6, QtWidgets.QTableWidgetItem("0.00"))
        self.items_table.setCellWidget(r, 7, cut_cb)

        for col in (1, 2, 4, 5):
            widget = self.items_table.cellWidget(r, col)
            if widget:
                widget.valueChanged.connect(lambda _=None, w=widget: self._on_widget_changed(w))
        cut_cb.toggled.connect(lambda _checked, row=r: self._on_cut_toggled(row))

        self._apply_cut_state(r)
        self._recalc_row(r)
        self._recalc_total()
        self._focus_items_cell(r, 2)
        return r

    def _on_widget_changed(self, widget):
        row = self._find_row_for_widget(widget)
        if row is None:
            return
        self._recalc_row(row)
        self._recalc_total()

    def _find_row_for_widget(self, widget):
        for r in range(self.items_table.rowCount()):
            for c in (1, 2, 4, 5):
                if self.items_table.cellWidget(r, c) is widget:
                    return r
        return None

    def _find_row_for_product(self, pid: int):
        for r in range(self.items_table.rowCount()):
            try:
                meta = self.items_table.item(r, 0).data(QtCore.Qt.UserRole) or {}
                if int(meta.get("product_id", 0) or 0) == pid:
                    return r
            except Exception:
                pass
        return None

    def _recalc_row(self, row):
        try:
            retail = float(self.items_table.cellWidget(row, 1).value())
            pct = float(self.items_table.cellWidget(row, 2).value())
            extra = float(self.items_table.cellWidget(row, 4).value())
            qty = int(self.items_table.cellWidget(row, 5).value())
            cut = bool(self.items_table.cellWidget(row, 7).isChecked())
            if cut:
                trade = float(self.items_table.item(row, 3).text())
                final = trade
            else:
                trade = retail * (1.0 - (pct / 100.0))
                final = trade * (1.0 - (extra / 100.0))
                self._suppress_item_change = True
                self.items_table.item(row, 3).setText(f"{trade:.2f}")
                self._suppress_item_change = False
            self.items_table.item(row, 6).setText(f"{final * qty:.2f}")
        except Exception:
            pass

    def _recalc_total(self):
        total = 0.0
        for r in range(self.items_table.rowCount()):
            try:
                total += float(self.items_table.item(r, 6).text())
            except Exception:
                pass
        self.total_label.setText(f"Total: {total:.2f}")

    def _focus_items_cell(self, row: int, col: int):
        if row is None or col is None:
            return
        self.items_table.setCurrentCell(row, col)
        w = self.items_table.cellWidget(row, col)
        if w:
            w.setFocus()
            if hasattr(w, "lineEdit") and w.lineEdit():
                try:
                    w.lineEdit().selectAll()
                except Exception:
                    pass

    def _remove_item(self):
        r = self.items_table.currentRow()
        if r >= 0:
            self.items_table.removeRow(r)
            self._recalc_total()

    def _clear_items(self):
        self.items_table.setRowCount(0)
        self._recalc_total()

    def _save_purchase(self):
        sid = self.supplier_cb.currentData() or 0
        sname = self.supplier_cb.currentText().strip()
        rows = []
        total = 0.0
        for r in range(self.items_table.rowCount()):
            try:
                prod_item = self.items_table.item(r, 0)
                meta = prod_item.data(QtCore.Qt.UserRole) or {}
                pid = int(meta.get("product_id", 0) if isinstance(meta, dict) else meta)
                company_id = int(meta.get("company_id", 0) if isinstance(meta, dict) else 0)
                retail = float(self.items_table.cellWidget(r, 1).value())
                pct = float(self.items_table.cellWidget(r, 2).value())
                extra = float(self.items_table.cellWidget(r, 4).value())
                qty = int(self.items_table.cellWidget(r, 5).value())
                cut = bool(self.items_table.cellWidget(r, 7).isChecked())
                if cut:
                    trade = float(self.items_table.item(r, 3).text())
                    final = trade
                else:
                    trade = retail * (1.0 - (pct / 100.0))
                    final = trade * (1.0 - (extra / 100.0))
                rows.append(
                    {
                        "product_id": pid,
                        "company_id": company_id,
                        "quantity": qty,
                        "price": final,
                        "retail_price": retail,
                        "discount_pct": pct,
                        "extra_discount_pct": extra,
                        "trade_price": trade,
                        "is_cut_rate": cut,
                    }
                )
                total += qty * final
            except Exception:
                pass
        if not rows:
            QtWidgets.QMessageBox.information(self, "No Items", "Add at least one item.")
            return
        payload = {"supplier_id": int(sid or 0), "supplier_name": sname, "total": total, "items": rows}
        try:
            if sid == 0 and sname:
                self.api.company_upsert({"name": sname})
            if getattr(self, "_edit_purchase_id", None):
                self.api.purchase_update(int(self._edit_purchase_id), payload)
                QtWidgets.QMessageBox.information(self, "Saved", "Purchase updated")
            else:
                self.api.purchase_new(payload)
                QtWidgets.QMessageBox.information(self, "Saved", "Purchase saved")
            self._clear_items()
            self._exit_edit_mode()
            self.refresh_history()
            self.inventory_changed.emit()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def refresh_history(self):
        try:
            docs = self.api.purchases_list()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
            return
        self.history_table.setRowCount(0)
        for p in docs or []:
            r = self.history_table.rowCount()
            self.history_table.insertRow(r)
            self.history_table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(p.get("id", ""))))
            self.history_table.setItem(r, 1, QtWidgets.QTableWidgetItem(p.get("date", "")))
            self.history_table.setItem(r, 2, QtWidgets.QTableWidgetItem(p.get("supplier_name", "")))
            items = p.get("items") or []
            self.history_table.setItem(r, 3, QtWidgets.QTableWidgetItem(str(len(items))))
            self.history_table.setItem(r, 4, QtWidgets.QTableWidgetItem(f"{float(p.get('total', 0.0)):.2f}"))

    def _edit_selected(self):
        r = self.history_table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a purchase row first")
            return
        pid_item = self.history_table.item(r, 0)
        if not pid_item:
            return
        try:
            pid = int(pid_item.text())
        except Exception:
            return
        docs = self.api.purchases_list() or []
        match = next((p for p in docs if int(p.get("id", 0) or 0) == pid), None)
        if not match:
            QtWidgets.QMessageBox.information(self, "Not Found", "Could not locate purchase to edit")
            return
        self._load_purchase_into_form(match)

    def _delete_selected(self):
        r = self.history_table.currentRow()
        if r < 0:
            QtWidgets.QMessageBox.information(self, "Select", "Select a purchase row first")
            return
        pid_item = self.history_table.item(r, 0)
        if not pid_item:
            return
        try:
            pid = int(pid_item.text())
        except Exception:
            return
        if QtWidgets.QMessageBox.question(self, "Confirm", "Delete this purchase?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            import requests
            requests.delete(self.api.base_url + f"/api/purchases/purchase/{pid}")
            QtWidgets.QMessageBox.information(self, "Deleted", "Purchase deleted")
            self.refresh_history()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _load_purchase_into_form(self, purchase: dict):
        self._edit_purchase_id = int(purchase.get("id", 0) or 0)
        self.btn_save.setText("Update Purchase")
        self.btn_cancel_edit.setVisible(True)
        self.tabs.setCurrentIndex(0)
        self._load_suppliers()
        sid = int(purchase.get("supplier_id", 0) or 0)
        sname = purchase.get("supplier_name", "")
        if sid:
            idx = self.supplier_cb.findData(sid)
            if idx >= 0:
                self.supplier_cb.setCurrentIndex(idx)
            else:
                self.supplier_cb.setCurrentText(sname)
        else:
            self.supplier_cb.setCurrentText(sname)
        self._clear_items()
        products = self._load_products(force=True)
        for it in purchase.get("items", []) or []:
            pid = int(it.get("product_id", 0) or 0)
            company_id = int(it.get("company_id", 0) or 0)
            prod = next((p for p in products if int(p.get("id")) == pid), None)
            name = prod.get("name", f"ID {pid}") if prod else f"ID {pid}"
            retail_val = it.get("retail_price")
            if retail_val is None:
                retail_val = it.get("price", 0.0)
            discount_val = it.get("discount_pct")
            extra_val = it.get("extra_discount_pct")
            retail = float(retail_val or 0.0)
            discount_pct = float(discount_val or 0.0)
            extra_pct = float(extra_val or 0.0)
            qty = int(it.get("quantity", 1) or 1)
            trade = it.get("trade_price")
            is_cut = bool(it.get("is_cut_rate")) if it.get("is_cut_rate") is not None else False
            if company_id == 0 and prod:
                company_id = int(prod.get("company_id", 0) or 0)
            base_price = float(trade or it.get("price", 0.0) or 0.0)
            self._add_row(pid, name, qty, retail, company_id, is_cut, base_price, discount_pct, extra_pct)

    def _exit_edit_mode(self):
        self._edit_purchase_id = None
        self.btn_save.setText("Save Purchase")
        self.btn_cancel_edit.setVisible(False)

    def _apply_cut_state(self, row):
        cut = bool(self.items_table.cellWidget(row, 7).isChecked())
        pct_spin = self.items_table.cellWidget(row, 2)
        extra_spin = self.items_table.cellWidget(row, 4)
        trade_item = self.items_table.item(row, 3)
        if cut:
            pct_spin.setEnabled(False)
            extra_spin.setEnabled(False)
            trade_item.setFlags(trade_item.flags() | QtCore.Qt.ItemIsEditable)
        else:
            pct_spin.setEnabled(True)
            extra_spin.setEnabled(True)
            trade_item.setFlags(trade_item.flags() & ~QtCore.Qt.ItemIsEditable)

    def _on_cut_toggled(self, row):
        self._apply_cut_state(row)
        self._recalc_row(row)
        self._recalc_total()

    def _on_item_changed(self, item):
        if self._suppress_item_change:
            return
        if item.column() == 3:
            row = item.row()
            if self.items_table.cellWidget(row, 7) and self.items_table.cellWidget(row, 7).isChecked():
                self._recalc_row(row)
                self._recalc_total()

    def _cancel_edit(self):
        if QtWidgets.QMessageBox.question(self, "Cancel Edit", "Discard changes?") != QtWidgets.QMessageBox.Yes:
            return
        self._clear_items()
        self._exit_edit_mode()

    # ---------- Keyboard navigation ----------
    def eventFilter(self, obj, event):
        table = getattr(self, "items_table", None)
        if obj is table and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                self._focus_next_item_field()
                return True
            if event.key() == QtCore.Qt.Key_Delete:
                self._remove_item()
                return True
        if obj is getattr(self, "search", None) and event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Down and self.results.isVisible() and self.results.count() > 0:
                row = self.results.currentRow()
                self.results.setCurrentRow(min(self.results.count() - 1, row + 1))
                return True
            if event.key() == QtCore.Qt.Key_Up and self.results.isVisible() and self.results.count() > 0:
                row = self.results.currentRow()
                self.results.setCurrentRow(max(0, row - 1))
                return True
        return super().eventFilter(obj, event)

    def _focus_next_item_field(self):
        if self.items_table.rowCount() == 0:
            return
        editable_cols = [1, 2, 4, 5]  # retail, discount, addl %, qty
        row = self.items_table.currentRow()
        if row < 0:
            row = 0
        col = self.items_table.currentColumn()
        focus_w = self.focusWidget()
        # If cut rate, allow trade price edit
        try:
            cut = bool(self.items_table.cellWidget(row, 7).isChecked())
        except Exception:
            cut = False
        if cut:
            editable_cols = [1, 2, 3, 4, 5]
        for c in editable_cols:
            if self.items_table.cellWidget(row, c) is focus_w:
                col = c
                break
        try:
            idx = editable_cols.index(col)
        except ValueError:
            idx = -1
        # At end of row
        if idx == len(editable_cols) - 1:
            if row + 1 < self.items_table.rowCount():
                self._focus_items_cell(row + 1, editable_cols[0])
            else:
                self._focus_search()
            return
        if idx + 1 < len(editable_cols):
            next_row, next_col = row, editable_cols[idx + 1]
        else:
            next_row, next_col = row + 1, editable_cols[0]
        if next_row >= self.items_table.rowCount():
            next_row = row
        self._focus_items_cell(next_row, next_col)
