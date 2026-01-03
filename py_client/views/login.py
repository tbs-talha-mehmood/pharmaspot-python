from PyQt5 import QtWidgets


class LoginView(QtWidgets.QWidget):
    def __init__(self, api, on_success):
        super().__init__()
        self.api = api
        self.on_success = on_success
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        title = QtWidgets.QLabel("Login")
        title.setStyleSheet("font-size:18px;font-weight:bold")
        layout.addWidget(title)

        form = QtWidgets.QFormLayout()
        self.username = QtWidgets.QLineEdit()
        self.password = QtWidgets.QLineEdit()
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        layout.addLayout(form)

        self.message = QtWidgets.QLabel()
        self.message.setStyleSheet("color:#b00")
        layout.addWidget(self.message)

        btn = QtWidgets.QPushButton("Sign In")
        btn.clicked.connect(self._submit)
        layout.addWidget(btn)

        layout.addStretch(1)

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

