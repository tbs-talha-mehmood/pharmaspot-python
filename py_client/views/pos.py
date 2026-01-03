from PyQt5 import QtWidgets, QtPrintSupport, QtCore
import base64
from pathlib import Path


class POSView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.cart = []
        self.user_id = 0
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Point of Sale"))
        self.btn_add = QtWidgets.QPushButton("Add Item by SKU")
        self.btn_checkout = QtWidgets.QPushButton("Checkout")
        header.addWidget(self.btn_add)
        header.addWidget(self.btn_checkout)
        header.addWidget(QtWidgets.QLabel("Customer:"))
        self.customer = QtWidgets.QComboBox()
        header.addWidget(self.customer)
        header.addWidget(QtWidgets.QLabel("Discount %:"))
        self.discount = QtWidgets.QDoubleSpinBox(); self.discount.setRange(0, 100); self.discount.setDecimals(2)
        header.addWidget(self.discount)
        header.addStretch(1)
        layout.addLayout(header)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Qty", "Price", "Total"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.btn_add.clicked.connect(self.add_item_dialog)
        self.btn_checkout.clicked.connect(self.checkout)
        self.table.itemChanged.connect(self._on_cell_changed)
        self._load_customers()

    def set_user(self, user: dict):
        try:
            self.user_id = int(user.get("id", 0) or 0)
        except Exception:
            self.user_id = 0

    def add_item_dialog(self):
        sku, ok = QtWidgets.QInputDialog.getText(self, "Add by SKU", "Enter Barcode")
        if not ok or not sku.strip():
            return
        try:
            # backend expects form param skuCode; use GET fallback on full list
            products = self.api.products()
            match = None
            try:
                code = int(sku)
                for p in products:
                    if p.get("barcode") == code:
                        match = p; break
            except Exception:
                pass
            if not match:
                QtWidgets.QMessageBox.information(self, "Not Found", "No product with that barcode")
                return
            self._add_to_cart(match)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _add_to_cart(self, product):
        # Default qty 1
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(str(product.get("id"))))
        self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(product.get("name", "")))
        qty_item = QtWidgets.QTableWidgetItem("1")
        self.table.setItem(r, 2, qty_item)
        price = float(product.get("price", 0.0))
        self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(f"{price:.2f}"))
        self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(f"{price:.2f}"))
        self._recalc_row(r)

    def _recalc_row(self, r: int):
        try:
            qty = int(self.table.item(r, 2).text())
            price = float(self.table.item(r, 3).text())
            total = qty * price
            self.table.item(r, 4).setText(f"{total:.2f}")
        except Exception:
            pass

    def _recalc_totals(self):
        n = self.table.rowCount()
        gross = 0.0
        for r in range(n):
            try:
                gross += float(self.table.item(r, 4).text())
            except Exception:
                pass
        # VAT from settings if available
        try:
            vat_map = self.api.settings_map() or {}
            vat_pct = float((vat_map.get("settings", {}) or {}).get("vat_percent", 0.0))
        except Exception:
            vat_pct = 0.0
        discount_pct = self.discount.value() or 0.0
        net = gross * (1.0 - discount_pct / 100.0)
        vat_amount = net * (vat_pct / 100.0)
        net_with_vat = net + vat_amount
        self.setToolTip(f"Gross: {gross:.2f} | Discount: {discount_pct:.2f}% | VAT: {vat_pct:.2f}% | Total: {net_with_vat:.2f}")

    def _on_cell_changed(self, item):
        r = item.row()
        c = item.column()
        if c in (2, 3):
            self._recalc_row(r)
            self._recalc_totals()

    def checkout(self):
        n = self.table.rowCount()
        items = []
        for r in range(n):
            try:
                pid = int(self.table.item(r, 0).text())
                qty = int(self.table.item(r, 2).text())
                items.append({"id": pid, "quantity": qty})
            except Exception:
                pass
        if not items:
            QtWidgets.QMessageBox.information(self, "Empty", "No items to checkout")
            return
        try:
            # Apply discount to grand total (client-side only for now)
            grand = 0.0
            for r in range(n):
                try:
                    grand += float(self.table.item(r, 4).text())
                except Exception:
                    pass
            discount_pct = self.discount.value() or 0.0
            net = grand * (1.0 - discount_pct / 100.0)
            # VAT
            try:
                vat_map = self.api.settings_map() or {}
                vat_pct = float((vat_map.get("settings", {}) or {}).get("vat_percent", 0.0))
            except Exception:
                vat_pct = 0.0
            vat_amount = net * (vat_pct / 100.0)
            total_after = net + vat_amount

            # Persist transaction with discount and paid=total_after
            try:
                cust_id = int(self.customer.currentData() or 0)
            except Exception:
                cust_id = 0
            tx_payload = {
                "customer_id": cust_id,
                "user_id": int(self.user_id or 0),
                "total": total_after,
                "paid": total_after,
                "discount": discount_pct,
                "items": items,
            }
            self.api.transaction_new(tx_payload)
            self._print_receipt(items, grand, discount_pct, vat_amount, vat_pct, total_after)
            QtWidgets.QMessageBox.information(self, "Success", "Checkout complete")
            self.table.setRowCount(0)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _load_customers(self):
        try:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)
            for c in self.api.customers():
                self.customer.addItem(c.get("name", "Customer"), int(c.get("id")))
        except Exception:
            self.customer.clear()
            self.customer.addItem("Walk-in", 0)

    def _print_receipt(self, items, gross, discount_pct, vat_amount, vat_pct, total_with_vat):
        printer = QtPrintSupport.QPrinter()
        dialog = QtPrintSupport.QPrintDialog(printer, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        doc = QtWidgets.QTextDocument()
        cust_name = self.customer.currentText() or "Walk-in"
        # Settings
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
            # Guess mime type
            ext = p.suffix.lower()
            mime = "image/svg+xml" if ext == ".svg" else ("image/png" if ext == ".png" else "image/jpeg")
            logo_data_uri = f"data:{mime};base64,{b64}"
        except Exception:
            logo_data_uri = ""
        rows = []
        for it in items:
            try:
                pid = it.get("id")
                prod = next((p for p in self.api.products() if p.get("id") == pid), None)
                name = prod.get("name") if prod else str(pid)
                qty = it.get("quantity", 0)
                price = float(prod.get("price", 0.0)) if prod else 0.0
                rows.append(f"<tr><td>{name}</td><td style='text-align:center'>{qty}</td><td style='text-align:right'>{price:.2f}</td></tr>")
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
