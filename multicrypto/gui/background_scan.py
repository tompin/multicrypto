"""Scanning for used addresses in the background, the progress is shown in the status bar."""

import threading
import time
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton

from multicrypto.discovery import (
    Cancelled,
    DiscoveredAccount,
    add_discovered,
    discover,
    scan_account,
)
from multicrypto.gui.forms import EXPECTED_ERRORS, describe_error
from multicrypto.wallet import HDAccount

# job(progress, cancelled, found) appends the discovered accounts to the found list
Job = Callable[[Callable[[int], None], Callable[[], bool], List[DiscoveredAccount]], None]


class BackgroundScan(QObject):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.running = False
        self.title = ''
        self.checked = 0
        self.lock = threading.Lock()
        self.cancel_requested = False
        self.wallet = None
        self.found: List[DiscoveredAccount] = []
        self.label = QLabel()
        self.cancel_button = QPushButton('Cancel')
        self.cancel_button.clicked.connect(lambda _checked=False: self.cancel())
        self.cancel_button.hide()
        app.statusBar().addPermanentWidget(self.label)
        app.statusBar().addPermanentWidget(self.cancel_button)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._show_progress)

    def start_account(self, account: HDAccount) -> bool:
        wallet = self.app.wallet
        title = f'{account.coin} {account.address_type} account {account.account}'
        return self.start(
            title,
            lambda progress, cancelled, found: found.append(
                scan_account(wallet, account, progress, cancelled)
            ),
        )

    def start_coin(self, coin_symbol: str) -> bool:
        wallet = self.app.wallet
        return self.start(
            coin_symbol,
            lambda progress, cancelled, found: discover(
                wallet, coin_symbol, progress, cancelled, found=found
            ),
        )

    def start(self, title: str, job: Job) -> bool:
        if self.running:
            QMessageBox.information(self.app, 'Scan', 'A scan is already running')
            return False
        wallet = self.app.wallet
        if wallet is None:
            return False
        self.running = True
        self.title = title
        self.checked = 0
        self.cancel_requested = False
        self.wallet = wallet
        found: List[DiscoveredAccount] = []
        self.found = found

        def cancelled() -> bool:
            return self.cancel_requested or self.app.wallet is not wallet

        def run() -> Optional[List[DiscoveredAccount]]:
            try:
                job(self._progress, cancelled, found)
            except Cancelled:
                return None
            return found

        self.cancel_button.show()
        self._show_progress()
        self.timer.start(300)
        self.app.worker.run(run, self._finished, self._failed)
        return True

    def cancel(self):
        if self.running:
            self.cancel_requested = True
            self.label.setText(f'Cancelling scan of {self.title}...')

    def _progress(self, count: int):
        with self.lock:  # called from the threads of the scan
            self.checked += count

    def _show_progress(self):
        if not self.cancel_requested:
            self.label.setText(f'Scanning {self.title}: checked {self.checked} addresses')
        # the scan is activity, the wallet is not locked by inactivity until it ends
        self.app.last_activity = time.monotonic()

    def _stop(self):
        self.timer.stop()
        self.running = False
        self.cancel_button.hide()

    def _add(self, found: List[DiscoveredAccount]) -> int:
        """Add the found addresses when the scanned wallet is still unlocked."""
        if self.app.wallet is not self.wallet or not found:
            return 0
        return self.app.modify_wallet(lambda wallet: add_discovered(wallet, found))

    def _finished(self, found: Optional[List[DiscoveredAccount]]):
        self._stop()
        if found is None or self.app.wallet is not self.wallet:
            self.label.setText(f'Scan of {self.title} cancelled')
            return
        try:
            added = self._add(found)
        except EXPECTED_ERRORS as error:
            self._failed(error)
            return
        self.label.setText(f'Scan of {self.title} finished: added {added} addresses')

    def _failed(self, error):
        self._stop()
        try:
            added = self._add(self.found)
        except EXPECTED_ERRORS:
            added = 0
        self.label.setText(f'Scan of {self.title} failed')
        QMessageBox.warning(
            self.app,
            'Scan',
            f'Scan of {self.title} failed: {describe_error(error)}\n'
            f'The addresses found before the error were added: {added}. '
            'Run the scan again to continue.',
        )
