"""Main window: wallet file handling, tabs and automatic locking."""

import copy
import os
import time
from typing import Optional

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from multicrypto.gui.balance_tab import BalanceTab
from multicrypto.gui.create_wizard import CreateWalletWizard
from multicrypto.gui.dialogs import SecretDialog, UnlockDialog, ask_password, mnemonic_grid
from multicrypto.gui.forms import describe_error
from multicrypto.gui.send_tab import SendTab
from multicrypto.gui.sign_tab import SignTab
from multicrypto.gui.sweep_tab import SweepTab
from multicrypto.gui.wallet_tab import WalletTab
from multicrypto.gui.worker import Worker
from multicrypto.wallet import MIN_PASSWORD_LENGTH, Wallet, WalletFile

AUTO_LOCK_SECONDS = 5 * 60
WALLET_FILE_FILTER = 'multicrypto wallet (*.mcw);;All files (*)'
ACTIVITY_EVENTS = (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove)


def _opened(wallet: Wallet) -> Wallet:
    """Derive the addresses in background, so showing the wallet doesn't block the GUI."""
    wallet.addresses()
    return wallet


class MainWindow(QMainWindow):
    def __init__(self, wallet_file: WalletFile, auto_lock_seconds: int = AUTO_LOCK_SECONDS):
        super().__init__()
        self.wallet_file = wallet_file
        self.auto_lock_seconds = auto_lock_seconds
        self.wallet: Optional[Wallet] = None
        self.last_activity = time.monotonic()
        self.worker = Worker(self)
        self.setWindowTitle('multicrypto')
        self.resize(1150, 700)
        self.wallet_tab = WalletTab(self)
        self.balance_tab = BalanceTab(self)
        self.send_tab = SendTab(self)
        self.sweep_tab = SweepTab(self)
        self.sign_tab = SignTab(self)
        self.tabs = (
            self.wallet_tab,
            self.balance_tab,
            self.send_tab,
            self.sweep_tab,
            self.sign_tab,
        )
        self.tab_widget = QTabWidget()
        for tab, title in zip(
            self.tabs, ('Wallet', 'Balance', 'Send', 'Sweep', 'Sign / Verify'), strict=True
        ):
            self.tab_widget.addTab(tab, title)
        self.locked_message = QLabel()
        self.locked_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unlock_button = QPushButton('Unlock...')
        self.locked_screen = QWidget()
        locked_layout = QVBoxLayout(self.locked_screen)
        locked_layout.addStretch()
        locked_layout.addWidget(self.locked_message)
        for button, slot in (
            (self.unlock_button, self.unlock),
            (QPushButton('Create new wallet...'), self.new_wallet),
            (QPushButton('Open wallet file...'), self.open_wallet),
        ):
            button.clicked.connect(lambda _checked=False, slot=slot: slot())
            locked_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        locked_layout.addStretch()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.locked_screen)
        self.stack.addWidget(self.tab_widget)
        self.setCentralWidget(self.stack)
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        self._create_menu()
        QApplication.instance().installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self._show_locked()

    def _create_menu(self):
        file_menu = self.menuBar().addMenu('&File')
        for text, slot in (
            ('New wallet...', self.new_wallet),
            ('Open wallet...', self.open_wallet),
            ('Change password...', self.change_password),
            ('Show mnemonic...', self.show_mnemonic),
            ('Lock', self.lock),
            ('Quit', self.close),
        ):
            action = file_menu.addAction(text)
            action.triggered.connect(lambda _checked=False, slot=slot: slot())

    def eventFilter(self, watched, event):
        if event.type() in ACTIVITY_EVENTS:
            self.last_activity = time.monotonic()
        return False

    def closeEvent(self, event):
        self.lock()
        super().closeEvent(event)

    def start(self):
        """Ask for the password when the wallet file exists."""
        if self.wallet_file.exists():
            self.unlock()

    def select_tab(self, tab: QWidget):
        self.tab_widget.setCurrentWidget(tab)

    def tick(self):
        """Update the status and lock the wallet after inactivity, called every second."""
        if self.wallet is not None:
            self._update_unlocked_status()

    def _update_unlocked_status(self):
        remaining = self.auto_lock_seconds - (time.monotonic() - self.last_activity)
        if remaining <= 0:
            self.lock()
            return
        minutes, seconds = divmod(int(remaining), 60)
        self.status.setText(
            f'{self.wallet_file.path} · fingerprint {self.wallet.fingerprint} · unlocked · '
            f'locks in {minutes}:{seconds:02d}'
        )

    def _show_locked(self):
        if self.wallet_file.exists():
            self.locked_message.setText(f'Wallet {self.wallet_file.path} is locked')
            self.unlock_button.setEnabled(True)
        else:
            self.locked_message.setText(
                f'Wallet file {self.wallet_file.path} does not exist.\n'
                'Create a new wallet or open another wallet file.'
            )
            self.unlock_button.setEnabled(False)
        self.status.setText(f'{self.wallet_file.path} · locked')
        self.stack.setCurrentWidget(self.locked_screen)

    def show_wallet(self, wallet: Wallet):
        self.wallet = wallet
        self.last_activity = time.monotonic()
        self.stack.setCurrentWidget(self.tab_widget)
        for tab in self.tabs:
            tab.refresh()
        self._update_unlocked_status()

    def lock(self):
        if self.wallet is not None:
            self.wallet.close()
        self.wallet = None
        self.wallet_file.lock()
        for tab in self.tabs:
            tab.clear()
        self._show_locked()

    def _derive_keys(self, message: str, func, on_success):
        """Run operation deriving keys from the password and the passphrase in background."""
        self.status.setText(message)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def succeeded(result):
            QApplication.restoreOverrideCursor()
            on_success(result)

        def failed(error):
            QApplication.restoreOverrideCursor()
            if self.wallet is None:
                self._show_locked()
            else:
                self._update_unlocked_status()
            self.show_error(error)

        self.worker.run(func, succeeded, failed)

    def unlock(self):
        dialog = UnlockDialog(self, self.wallet_file.path)
        if not dialog.exec():
            return
        password, passphrase = dialog.values()
        wallet_file = self.wallet_file
        self._derive_keys(
            'Unlocking...',
            lambda: _opened(wallet_file.unlock(password, passphrase)),
            self.show_wallet,
        )

    def new_wallet(self):
        path = self.wallet_file.path
        if self.wallet_file.exists():
            path, _ = QFileDialog.getSaveFileName(
                self,
                'New wallet file',
                os.path.join(os.path.dirname(os.path.abspath(path)), 'wallet.mcw'),
                WALLET_FILE_FILTER,
            )
            if not path:
                return
        wizard = CreateWalletWizard(self, path)
        if not wizard.exec():
            return
        password, mnemonic, passphrase = wizard.values()
        self.lock()
        wallet_file = self.wallet_file = WalletFile(path)
        self._derive_keys(
            'Creating wallet...',
            lambda: _opened(wallet_file.create(password, mnemonic, passphrase)),
            self._created,
        )

    def _created(self, wallet: Wallet):
        self.show_wallet(wallet)
        QMessageBox.information(
            self,
            'New wallet',
            f'The wallet {self.wallet_file.path} has been created, its fingerprint is '
            f'{wallet.fingerprint}.',
        )

    def open_wallet(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            'Open wallet file',
            os.path.dirname(os.path.abspath(self.wallet_file.path)),
            WALLET_FILE_FILTER,
        )
        if not path:
            return
        self.lock()
        self.wallet_file = WalletFile(path)
        self._show_locked()
        self.unlock()

    def change_password(self):
        if self.wallet is None:
            return
        old_password = ask_password(self, 'Change password', 'Current password')
        if old_password is None:
            return
        new_password = ask_password(
            self,
            'Change password',
            f'New password (at least {MIN_PASSWORD_LENGTH} characters)',
            new_password=True,
        )
        if new_password is None:
            return
        wallet_file, wallet = self.wallet_file, self.wallet
        self._derive_keys(
            'Changing password...',
            lambda: wallet_file.change_password(old_password, new_password, wallet),
            lambda _result: self._password_changed(),
        )

    def _password_changed(self):
        self._update_unlocked_status()
        QMessageBox.information(self, 'Change password', 'The password has been changed')

    def show_mnemonic(self):
        if self.wallet is None:
            return
        password = ask_password(self, 'Show mnemonic', 'Enter the wallet password')
        if password is None:
            return
        self.worker.run(
            lambda: self.wallet_file.verify_password(password),
            self._show_mnemonic,
            self.show_error,
        )

    def _show_mnemonic(self, correct: bool):
        if not correct:
            QMessageBox.warning(self, 'Show mnemonic', 'Wrong password')
            return
        if self.wallet is None:
            return
        SecretDialog(
            self,
            'Mnemonic',
            'The passphrase is not shown, the mnemonic restores the wallet only with it.',
            mnemonic_grid(self.wallet.mnemonic),
        ).exec()

    def modify_wallet(self, change):
        """Apply the change to the wallet and save it, the change is reverted when saving fails."""
        snapshot = copy.deepcopy((self.wallet.accounts, self.wallet.imported))
        result = change(self.wallet)
        try:
            self.wallet_file.save(self.wallet)
        except BaseException:
            self.wallet.accounts, self.wallet.imported = snapshot
            raise
        for tab in self.tabs:
            tab.refresh()
        return result

    def show_error(self, error: BaseException):
        QMessageBox.critical(self, 'Error', describe_error(error))
