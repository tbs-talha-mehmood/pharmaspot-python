from PyQt5 import QtWidgets, QtGui

# Light theme stylesheet for consistent UI
STYLE = """
* { font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; }
QWidget { background: #f8fafc; color: #1f2937; }
QLabel#title { font-size: 18px; font-weight: 600; color: #0f172a; }
QLabel#mutedLabel { color: #475569; font-weight: 600; }
QLabel#moneyStrong { font-size: 19px; font-weight: 700; color: #0f172a; }
QFrame#posTopCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
QLineEdit#invoiceInput { min-width: 170px; }
QGroupBox { font-weight: 600; border: 1px solid #e5e7eb; border-radius: 8px; margin-top: 12px; padding: 8px 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #0f172a; }
QGroupBox#totalsCard { background: #ffffff; }
QPushButton {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:disabled { background: #cbd5e1; color: #94a3b8; }
QPushButton:hover { background: #1d4ed8; }
QPushButton:pressed { background: #1e40af; }
QPushButton[secondary="true"] {
    background: #e8eefc;
    color: #1e3a8a;
    border: 1px solid #c7d2fe;
}
QPushButton[secondary="true"]:hover { background: #dbe7ff; }
QPushButton[secondary="true"]:pressed { background: #c7d2fe; }
QPushButton[danger="true"] {
    background: #fee2e2;
    color: #991b1b;
    border: 1px solid #fecaca;
}
QPushButton[danger="true"]:hover { background: #fecaca; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 8px;
    background: white;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus {
    border: 1px solid #2563eb;
    outline: none;
}
QTableWidget, QTableView {
    background: white;
    border: 1px solid #e5e7eb;
    alternate-background-color: #f9fafb;
    gridline-color: #e5e7eb;
}
QHeaderView::section {
    background: #f3f4f6;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    font-weight: 600;
}
QListWidget#sideNav {
    background: white;
    border-right: 1px solid #e5e7eb;
}
QListWidget#sideNav::item {
    padding: 10px 12px;
}
QListWidget#sideNav::item:selected {
    background: #e0ecff;
    color: #1d4ed8;
    font-weight: 600;
}
QLabel#error { color: #b91c1c; }
QStatusBar { background: #f8fafc; }
"""


def apply_theme(app: QtWidgets.QApplication):
    app.setStyle("Fusion")
    base_font = QtGui.QFont("Segoe UI", 10)
    app.setFont(base_font)
    app.setStyleSheet(STYLE)
