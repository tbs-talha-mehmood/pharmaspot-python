from PyQt5 import QtWidgets, QtCore
from .ui_common import apply_page_layout, polish_controls


class DashboardView(QtWidgets.QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self._build()

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        apply_page_layout(root)

        card = QtWidgets.QGroupBox("Dashboard")
        card.setObjectName("totalsCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setSpacing(6)

        title = QtWidgets.QLabel("Welcome to PharmaSpot")
        title.setObjectName("moneyStrong")
        title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        card_layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Overview widgets can be added here.")
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)
        card_layout.addWidget(subtitle)

        root.addWidget(card)
        root.addStretch(1)
        polish_controls(self)

    def refresh(self):
        # Placeholder module for future dashboard widgets.
        return
