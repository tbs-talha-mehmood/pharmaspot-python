from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from .ui_common import apply_form_layout, apply_page_layout, polish_controls, set_accent


class LoginView(QtWidgets.QWidget):
    def __init__(self, api, on_success):
        super().__init__()
        self.api = api
        self.on_success = on_success
        self._build()

    def _logo_pixmap(self, size: int) -> QtGui.QPixmap:
        logo_path = Path(__file__).resolve().parents[1] / "assets" / "pharmaspot-icon.png"
        pix = QtGui.QPixmap(str(logo_path))
        if pix.isNull():
            return QtGui.QPixmap()
        return pix.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        apply_page_layout(root)
        root.addStretch(1)

        shell = QtWidgets.QFrame()
        shell.setObjectName("loginShell")
        shell_row = QtWidgets.QHBoxLayout(shell)
        shell_row.setContentsMargins(0, 0, 0, 0)
        shell_row.setSpacing(0)
        shell_row.addStretch(1)

        card = QtWidgets.QFrame()
        card.setObjectName("loginCard")
        card.setMinimumWidth(460)
        card.setMaximumWidth(520)
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(12)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        logo = QtWidgets.QLabel()
        logo_pix = self._logo_pixmap(56)
        if not logo_pix.isNull():
            logo.setPixmap(logo_pix)
        header.addWidget(logo, 0, QtCore.Qt.AlignTop)

        heading_col = QtWidgets.QVBoxLayout()
        heading_col.setContentsMargins(0, 0, 0, 0)
        heading_col.setSpacing(2)
        title = QtWidgets.QLabel("PharmaSpot")
        title.setObjectName("loginTitle")
        subtitle = QtWidgets.QLabel("Secure sign in to continue")
        subtitle.setObjectName("loginSubtitle")
        heading_col.addWidget(title)
        heading_col.addWidget(subtitle)
        header.addLayout(heading_col, 1)
        card_layout.addLayout(header)

        form = QtWidgets.QFormLayout()
        apply_form_layout(form)
        self.username = QtWidgets.QLineEdit()
        self.username.setObjectName("loginInput")
        self.username.setPlaceholderText("Username")
        self.password = QtWidgets.QLineEdit()
        self.password.setObjectName("loginInput")
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.returnPressed.connect(self._submit)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        card_layout.addLayout(form)

        self.message = QtWidgets.QLabel()
        self.message.setObjectName("error")
        card_layout.addWidget(self.message)

        self.btn_sign_in = QtWidgets.QPushButton("Sign In")
        self.btn_sign_in.setObjectName("loginButton")
        set_accent(self.btn_sign_in)
        self.btn_sign_in.clicked.connect(self._submit)
        card_layout.addWidget(self.btn_sign_in)

        shell_row.addWidget(card)
        shell_row.addStretch(1)
        root.addWidget(shell)
        root.addStretch(1)

        polish_controls(self)
        QtCore.QTimer.singleShot(0, self.username.setFocus)

    def _submit(self):
        user = self.username.text().strip()
        pwd = self.password.text()
        if not user or not pwd:
            self.message.setText("Enter username and password")
            return
        try:
            self.api.users_check()
            resp = self.api.login(user, pwd)
            if resp.get("auth"):
                self.message.setText("")
                self.on_success(resp)
            else:
                self.message.setText("Invalid credentials")
        except Exception as e:
            self.message.setText(f"API error: {e}")
