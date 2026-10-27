"""Dialog scanning the blockchain for used accounts and addresses of the HD wallet."""

import threading
import time
from typing import List

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from multicrypto.discovery import Cancelled, DiscoveredAccount, add_discovered, discover
from multicrypto.gui.forms import EXPECTED_ERRORS, coins_with_api, coins_with_slip44, describe_error

COLUMNS = 6


def scannable_coins() -> List[str]:
    return sorted(set(coins_with_slip44()) & set(coins_with_api()))


class ScanDialog(QDialog):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.setWindowTitle('Scan for used addresses')
        self.discovered: List[DiscoveredAccount] = []
        self.checked = 0
        self.lock = threading.Lock()
        self.cancel_requested = False
        self.coins = {symbol: QCheckBox(symbol) for symbol in scannable_coins()}
        self.coins['BTC'].setChecked(True)
        grid = QGridLayout()
        for position, box in enumerate(self.coins.values()):
            grid.addWidget(box, position // COLUMNS, position % COLUMNS)
        self.status = QLabel(
            'Addresses of all types and accounts (BIP-44) are checked until 20 unused ones.'
        )
        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.scan_button = QPushButton('Scan')
        self.scan_button.clicked.connect(lambda _checked=False: self.scan())
        self.add_button = QPushButton('Add to wallet')
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(lambda _checked=False: self.add())
        close_button = QPushButton('Close')
        close_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.scan_button)
        buttons.addWidget(self.add_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Coins'))
        layout.addLayout(grid)
        layout.addWidget(self.status)
        layout.addWidget(self.results)
        layout.addLayout(buttons)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._show_progress)
        self.resize(640, 420)

    def _progress(self, count: int):
        with self.lock:  # called from the threads of the worker
            self.checked += count

    def _show_progress(self):
        self.status.setText(f'Checked {self.checked} addresses...')
        # the scan started by the user is activity, the wallet is not locked until it ends
        self.app.last_activity = time.monotonic()

    def scan(self):
        symbols = [symbol for symbol, box in self.coins.items() if box.isChecked()]
        wallet = self.app.wallet
        if not symbols or wallet is None:
            self.status.setText('Select at least one coin')
            return
        self.checked = 0
        self.cancel_requested = False
        self.discovered = []
        self.results.clear()
        self.add_button.setEnabled(False)
        self.scan_button.setEnabled(False)

        def cancelled():
            return self.cancel_requested or self.app.wallet is not wallet

        def run():
            results = []
            for symbol in symbols:
                try:
                    results.append((symbol, discover(wallet, symbol, self._progress, cancelled)))
                except Cancelled:
                    return None
                except EXPECTED_ERRORS as error:
                    results.append((symbol, describe_error(error)))
            return results

        self.timer.start(300)
        self.app.worker.run(run, self._scanned, self._failed)

    def _scanned(self, results):
        self.timer.stop()
        self.scan_button.setEnabled(True)
        if results is None or self.app.wallet is None:
            self.status.setText('Cancelled')
            return
        lines = []
        for symbol, result in results:
            if isinstance(result, str):
                lines.append(f'{symbol}: {result}')
                continue
            self.discovered.extend(result)
            lines.extend(
                f'{item.coin} {item.address_type} account {item.account}: '
                f'{len(item.receive)} receiving, {len(item.change)} change'
                for item in result
            )
        if not self.discovered:
            lines.append('No used addresses found')
        self.results.setPlainText('\n'.join(lines))
        self.status.setText(f'Checked {self.checked} addresses')
        self.add_button.setEnabled(bool(self.discovered))

    def _failed(self, error):
        self.timer.stop()
        self.scan_button.setEnabled(True)
        self.status.setText(describe_error(error))

    def add(self):
        if self.app.wallet is None:
            return
        try:
            added = self.app.modify_wallet(lambda wallet: add_discovered(wallet, self.discovered))
        except EXPECTED_ERRORS as error:
            self.app.show_error(error)
            return
        self.add_button.setEnabled(False)
        self.status.setText(f'Added {added} addresses to the wallet')

    def reject(self):
        self.cancel_requested = True
        super().reject()
