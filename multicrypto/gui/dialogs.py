"""Dialogs of the GUI."""

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from multicrypto.gui.forms import check_password_confirmation

SECRET_DISPLAY_SECONDS = 30
WARNING_COLOR = '#c62828'


def password_field() -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setMinimumWidth(320)
    return field


def coin_box(symbols: List[str]) -> QComboBox:
    """Selection of the coin as wide as its symbols, BTC is selected at the start."""
    box = QComboBox()
    box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    set_coins(box, symbols)
    return box


def set_coins(box: QComboBox, symbols: List[str]) -> None:
    """Replace the coins, the selected coin is kept when it is still on the list."""
    previous = box.currentText()
    box.blockSignals(True)
    box.clear()
    box.addItems(symbols)
    for symbol in (previous, 'BTC'):
        if symbol in symbols:
            box.setCurrentText(symbol)
            break
    box.blockSignals(False)
    if box.currentText() != previous:
        box.currentTextChanged.emit(box.currentText())


def monospace_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    return label


def mnemonic_grid(mnemonic: str, columns: int = 4) -> QWidget:
    """Numbered words of the mnemonic in columns to write them down, below them the warning and
    the button copying the words (the copy_button attribute)."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    words_widget = QWidget()
    grid = QGridLayout(words_widget)
    grid.setContentsMargins(0, 0, 0, 0)
    words = mnemonic.split()
    rows = (len(words) + columns - 1) // columns
    for position, word in enumerate(words):
        label = monospace_label(f'{position + 1:2}. {word}')
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        grid.addWidget(label, position % rows, position // rows)
    # the window must not be smaller than the words, wrapped labels report too small height
    words_widget.setMinimumSize(words_widget.sizeHint())
    layout.addWidget(words_widget)
    layout.addSpacing(12)
    warning = QLabel(
        'Copying the mnemonic is dangerous: other programs and clipboard managers can read the '
        'clipboard, and anyone who gets the words takes the funds. After pasting the words copy '
        'something else to replace them in the clipboard.'
    )
    warning.setObjectName('copy_warning')
    warning.setWordWrap(True)
    warning.setMinimumHeight(warning.heightForWidth(words_widget.sizeHint().width()))
    layout.addWidget(warning)
    widget.copy_button = QPushButton('Copy words')

    def copy_words():
        QApplication.clipboard().setText(' '.join(words))
        widget.copy_button.setText('Copied')

    widget.copy_button.clicked.connect(lambda _checked=False: copy_words())
    buttons = QHBoxLayout()
    buttons.addWidget(widget.copy_button)
    buttons.addStretch()
    layout.addLayout(buttons)
    return widget


def secret_line(secret: str) -> QLineEdit:
    field = QLineEdit(secret)
    field.setReadOnly(True)
    field.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    field.setMinimumWidth(field.fontMetrics().horizontalAdvance(secret) + 24)
    return field


class PasswordDialog(QDialog):
    """Ask for the password (or other secret named by the label), the new password has to be
    entered twice."""

    def __init__(
        self,
        parent: Optional[QWidget],
        title: str,
        prompt: str,
        new_password=False,
        label: str = 'Password',
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.new_password = new_password
        self.label = label
        self.password = password_field()
        self.confirmation = password_field()
        form = QFormLayout(self)
        prompt_label = QLabel(prompt)
        prompt_label.setWordWrap(True)
        form.addRow(prompt_label)
        form.addRow(label, self.password)
        if new_password:
            form.addRow('Repeat password', self.confirmation)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self):
        try:
            if self.new_password:
                check_password_confirmation(self.password.text(), self.confirmation.text())
            elif not self.password.text():
                raise ValueError(f'Enter the {self.label.lower()}')
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()


def ask_password(
    parent: Optional[QWidget],
    title: str,
    prompt: str,
    new_password: bool = False,
    label: str = 'Password',
) -> Optional[str]:
    dialog = PasswordDialog(parent, title, prompt, new_password, label)
    return dialog.password.text() if dialog.exec() else None


class ConfirmDialog(QDialog):
    """Show the rows and ask for confirmation. Cancel is the default button, so Enter does not
    confirm the action by accident."""

    def __init__(self, parent, title: str, rows: List[Tuple[str, str]], confirm_text: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        grid = QGridLayout()
        for row, (name, value) in enumerate(rows):
            name_label = QLabel(f'<b>{name}:</b>')
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if name == 'Warning':
                value_label.setStyleSheet(f'color: {WARNING_COLOR}')
            grid.addWidget(name_label, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value_label, row, 1)
        confirm_button = QPushButton(confirm_text)
        confirm_button.setAutoDefault(False)
        confirm_button.clicked.connect(self.accept)
        cancel_button = QPushButton('Cancel')
        cancel_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(confirm_button)
        buttons.addWidget(cancel_button)
        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addLayout(buttons)
        cancel_button.setFocus()


def confirm(parent, title: str, rows: List[Tuple[str, str]], confirm_text: str) -> bool:
    return bool(ConfirmDialog(parent, title, rows, confirm_text).exec())


class SecretDialog(QDialog):
    """Show the secret (private key, mnemonic), the dialog closes after the given time."""

    def __init__(
        self, parent, title: str, text: str, secret: QWidget, seconds=SECRET_DISPLAY_SECONDS
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.remaining = seconds
        self.countdown = QLabel()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text))
        layout.addWidget(secret)
        layout.addWidget(self.countdown)
        layout.addWidget(buttons)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._show_countdown()

    def _show_countdown(self):
        self.countdown.setText(f'The window closes in {self.remaining} seconds')

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.reject()
        else:
            self._show_countdown()


def show_text(parent, title: str, label: str, text: str) -> None:
    """Show the text (e.g. transaction id) with the button copying it to the clipboard."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    copy_button = QPushButton('Copy')
    copy_button.clicked.connect(lambda: QApplication.clipboard().setText(text))
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(label))
    layout.addWidget(secret_line(text))
    layout.addWidget(buttons)
    dialog.exec()


def show_lines(parent, title: str, label: str, lines: List[str]) -> None:
    """Show the lines (e.g. transaction ids) with the button copying them to the clipboard."""
    text = '\n'.join(lines)
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    view = QPlainTextEdit(text)
    view.setReadOnly(True)
    view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    view.setMinimumWidth(view.fontMetrics().horizontalAdvance(max(lines, key=len)) + 48)
    copy_button = QPushButton('Copy')
    copy_button.clicked.connect(lambda: QApplication.clipboard().setText(text))
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(label))
    layout.addWidget(view)
    layout.addWidget(buttons)
    dialog.exec()
