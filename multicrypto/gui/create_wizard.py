"""Wizard creating the wallet: file password, new or restored mnemonic and BIP-39 passphrase."""

from typing import Tuple

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from multicrypto.bip39 import generate_mnemonic, normalize_mnemonic, validate_mnemonic
from multicrypto.gui.dialogs import mnemonic_grid, password_field
from multicrypto.gui.forms import (
    check_confirmation_words,
    check_passphrase_confirmation,
    check_password_confirmation,
    choose_word_positions,
)
from multicrypto.wallet import MIN_PASSWORD_LENGTH

PASSWORD_PAGE, MODE_PAGE, SHOW_PAGE, CONFIRM_PAGE, RESTORE_PAGE, PASSPHRASE_PAGE = range(6)


class _Page(QWizardPage):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setTitle(title)
        self.setSubTitle(subtitle)

    def check(self, check, *args) -> bool:
        try:
            check(*args)
        except ValueError as error:
            QMessageBox.warning(self, self.title(), str(error))
            return False
        return True


class PasswordPage(_Page):
    def __init__(self, path: str):
        super().__init__(
            'Wallet file password',
            f'The password encrypts the wallet file {path}. '
            f'It must have at least {MIN_PASSWORD_LENGTH} characters.',
        )
        self.password = password_field()
        self.confirmation = password_field()
        form = QFormLayout(self)
        form.addRow('Password', self.password)
        form.addRow('Repeat password', self.confirmation)

    def validatePage(self):
        return self.check(
            check_password_confirmation, self.password.text(), self.confirmation.text()
        )


class ModePage(_Page):
    def __init__(self):
        super().__init__('Seed', 'Generate a new mnemonic or restore the wallet from yours.')
        self.generate = QRadioButton('Generate a new 24 words mnemonic')
        self.restore = QRadioButton('Restore from mnemonic')
        self.generate.setChecked(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.generate)
        layout.addWidget(self.restore)

    def nextId(self):
        return SHOW_PAGE if self.generate.isChecked() else RESTORE_PAGE


class ShowMnemonicPage(_Page):
    def __init__(self, mnemonic: str):
        super().__init__(
            'Write down the mnemonic',
            'Write the words on paper in this order and keep them safe. Together with the '
            'passphrase (if you set it) they restore all keys of the wallet. The words cannot be '
            'copied.',
        )
        layout = QVBoxLayout(self)
        layout.addWidget(mnemonic_grid(mnemonic))

    def nextId(self):
        return CONFIRM_PAGE


class ConfirmWordsPage(_Page):
    def __init__(self, mnemonic: str):
        super().__init__(
            'Confirm the mnemonic', 'Enter the words with the given numbers from your paper.'
        )
        self.mnemonic = mnemonic
        self.answers = {}
        form = QFormLayout(self)
        for position in choose_word_positions(len(mnemonic.split())):
            self.answers[position] = QLineEdit()
            form.addRow(f'Word {position}', self.answers[position])

    def validatePage(self):
        answers = {position: field.text() for position, field in self.answers.items()}
        return self.check(check_confirmation_words, self.mnemonic, answers)

    def nextId(self):
        return PASSPHRASE_PAGE


class RestorePage(_Page):
    def __init__(self):
        super().__init__(
            'Restore from mnemonic', 'Enter 12, 15, 18, 21 or 24 words separated with spaces.'
        )
        self.text = QPlainTextEdit()
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        layout.addWidget(self.status)
        self.text.textChanged.connect(self._update_status)

    def _update_status(self):
        if not self.text.toPlainText().strip():
            self.status.setText('')
            return
        try:
            validate_mnemonic(self.text.toPlainText())
        except ValueError as error:
            self.status.setText(str(error))
        else:
            self.status.setText('Mnemonic is correct')

    def mnemonic(self) -> str:
        return normalize_mnemonic(self.text.toPlainText())

    def validatePage(self):
        return self.check(validate_mnemonic, self.text.toPlainText())

    def nextId(self):
        return PASSPHRASE_PAGE


class PassphrasePage(_Page):
    def __init__(self):
        super().__init__(
            'BIP-39 passphrase (optional)',
            'You can skip the passphrase, then the mnemonic alone restores the wallet.',
        )
        explanation = QLabel(
            'The passphrase works as an additional word of the mnemonic. If you set it, it is '
            'never saved, you will enter it every time you unlock the wallet and it is required '
            'to restore the wallet - without it the mnemonic gives a different, empty wallet. '
            'Write it down and keep it separately from the mnemonic.'
        )
        explanation.setWordWrap(True)
        self.passphrase = password_field()
        self.confirmation = password_field()
        form = QFormLayout(self)
        form.addRow(explanation)
        form.addRow('Passphrase', self.passphrase)
        form.addRow('Repeat passphrase', self.confirmation)

    def validatePage(self):
        return self.check(
            check_passphrase_confirmation, self.passphrase.text(), self.confirmation.text()
        )

    def nextId(self):
        return -1


class CreateWalletWizard(QWizard):
    def __init__(self, parent, path: str):
        super().__init__(parent)
        self.setWindowTitle('New wallet')
        self.generated_mnemonic = generate_mnemonic()
        self.password_page = PasswordPage(path)
        self.mode_page = ModePage()
        self.show_page = ShowMnemonicPage(self.generated_mnemonic)
        self.confirm_page = ConfirmWordsPage(self.generated_mnemonic)
        self.restore_page = RestorePage()
        self.passphrase_page = PassphrasePage()
        for page_id, page in (
            (PASSWORD_PAGE, self.password_page),
            (MODE_PAGE, self.mode_page),
            (SHOW_PAGE, self.show_page),
            (CONFIRM_PAGE, self.confirm_page),
            (RESTORE_PAGE, self.restore_page),
            (PASSPHRASE_PAGE, self.passphrase_page),
        ):
            self.setPage(page_id, page)
        self.setStartId(PASSWORD_PAGE)

    def values(self) -> Tuple[str, str, str]:
        """Return the password of the file, the mnemonic and the passphrase."""
        if self.mode_page.generate.isChecked():
            mnemonic = self.generated_mnemonic
        else:
            mnemonic = self.restore_page.mnemonic()
        return self.password_page.password.text(), mnemonic, self.passphrase_page.passphrase.text()
