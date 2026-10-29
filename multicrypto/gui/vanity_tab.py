"""Vanity tab: searching for addresses starting with the given pattern (genaddress)."""

import html
import os
import time
from typing import Optional, Tuple

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from multicrypto.coins import ETHEREUM, get_address_types, get_any_coin, is_ethereum
from multicrypto.gui.dialogs import password_field
from multicrypto.gui.forms import (
    EXPECTED_ERRORS,
    add_private_key,
    all_coins,
    format_duration,
    parse_vanity_pattern,
)
from multicrypto.vanity import (
    VANITY_ADDRESS_TYPES,
    VanitySearch,
    expected_attempts,
    pattern_hint,
)

INVALID_COLOR = '#c62828'
DEFAULT_SPEED = 10000  # addresses per second per process before the first measurement
LONG_SEARCH_ATTEMPTS = 58**7
# the speed is remembered after this time, earlier it is lowered by starting the processes
SPEED_MEASURE_SECONDS = 5


class VanityTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.search: Optional[VanitySearch] = None
        self.started = 0.0
        self.speed = DEFAULT_SPEED
        # coin, type, address, private key (WIF, hex for Ethereum)
        self.found: Optional[Tuple[str, str, str, str]] = None
        cores = os.cpu_count() or 1
        self.coin = QComboBox()
        self.coin.addItems(all_coins())
        self.coin.setCurrentText('BTC')
        self.address_type = QComboBox()
        self.pattern = QLineEdit()
        self.pattern_status = QLabel()
        self.workers = QSpinBox()
        self.workers.setRange(1, cores)
        self.workers.setValue(max(1, cores - 1))
        self.start_button = QPushButton('Start')
        self.start_button.clicked.connect(lambda _checked=False: self.start())
        self.stop_button = QPushButton('Stop')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(lambda _checked=False: self.stop())
        self.progress = QLabel()
        self.result_address = QLineEdit()
        self.result_address.setReadOnly(True)
        self.result_key = password_field()
        self.result_key.setReadOnly(True)
        show_key = QCheckBox('Show')
        show_key.toggled.connect(
            lambda shown: self.result_key.setEchoMode(
                QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
            )
        )
        copy_key = QPushButton('Copy')
        copy_key.clicked.connect(
            lambda _checked=False: QApplication.clipboard().setText(self.result_key.text())
        )
        self.result_label = QLineEdit()
        add_button = QPushButton('Add to wallet')
        add_button.clicked.connect(lambda _checked=False: self.add_to_wallet())
        discard_button = QPushButton('Discard')
        discard_button.clicked.connect(lambda _checked=False: self.discard())
        form = QFormLayout()
        form.addRow('Coin', self.coin)
        form.addRow('Address type', self.address_type)
        form.addRow('Address starts with', self.pattern)
        form.addRow('', self.pattern_status)
        form.addRow('Processes', self.workers)
        buttons = QHBoxLayout()
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.progress, 1)
        self.result_group = QGroupBox('Found address')
        result_form = QFormLayout(self.result_group)
        result_form.addRow('Address', self.result_address)
        key_row = QHBoxLayout()
        key_row.addWidget(self.result_key)
        key_row.addWidget(show_key)
        key_row.addWidget(copy_key)
        result_form.addRow('Private key', key_row)
        result_form.addRow('Label', self.result_label)
        result_buttons = QHBoxLayout()
        result_buttons.addWidget(add_button)
        result_buttons.addWidget(discard_button)
        result_buttons.addStretch()
        result_form.addRow('', result_buttons)
        result_form.addRow(
            QLabel(
                'Imported keys are not restored from the mnemonic, back up the key separately.\n'
                'The result is lost when the wallet is locked before it is added.'
            )
        )
        self.result_group.hide()
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.result_group)
        layout.addStretch()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.coin.currentTextChanged.connect(lambda _text: self._coin_changed())
        self.address_type.currentTextChanged.connect(lambda _text: self._validate_pattern())
        self.pattern.textChanged.connect(lambda _text: self._validate_pattern())
        self.workers.valueChanged.connect(lambda _value: self._validate_pattern())
        self._coin_changed()

    def refresh(self):
        pass  # the tab does not show wallet addresses

    def clear(self):
        self._stop_search()
        self.discard()
        self.progress.setText('')

    def _coin_changed(self):
        coin_symbol = self.coin.currentText()
        if is_ethereum(coin_symbol):
            address_types = [ETHEREUM]
        else:
            address_types = [
                address_type
                for address_type in get_address_types(get_any_coin(coin_symbol))
                if address_type in VANITY_ADDRESS_TYPES
            ]
        self.address_type.blockSignals(True)
        self.address_type.clear()
        self.address_type.addItems(address_types)
        self.address_type.blockSignals(False)
        self.address_type.setEnabled(not is_ethereum(coin_symbol))
        self._validate_pattern()

    def _validate_pattern(self) -> Optional[str]:
        """Show the hint and the estimated time, return the pattern or None when incorrect."""
        coin_symbol, address_type = self.coin.currentText(), self.address_type.currentText()
        hint = pattern_hint(coin_symbol, address_type)
        try:
            pattern = parse_vanity_pattern(self.pattern.text(), coin_symbol, address_type)
        except ValueError as error:
            self.pattern_status.setText(
                f'{html.escape(hint)}<br><span style="color: {INVALID_COLOR}">'
                f'{html.escape(str(error))}</span>'
            )
            self.start_button.setEnabled(False)
            return None
        attempts = expected_attempts(pattern, coin_symbol, address_type)
        seconds = attempts / (self.speed * self.workers.value())
        estimate = f'~{attempts:,} attempts, ~{format_duration(seconds)}'
        if attempts > LONG_SEARCH_ATTEMPTS:
            estimate += ' (this may take very long)'
        self.pattern_status.setText(f'{html.escape(hint)}<br>{html.escape(estimate)}')
        self.start_button.setEnabled(self.search is None)
        return pattern

    def start(self):
        pattern = self._validate_pattern()
        if pattern is None or self.search is not None:
            return
        try:
            search = VanitySearch(
                self.coin.currentText(),
                self.address_type.currentText(),
                pattern,
                self.workers.value(),
            )
            search.start()
        except EXPECTED_ERRORS as error:
            self.app.show_error(error)
            return
        self.discard()
        self.search = search
        self.started = time.monotonic()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress.setText('Starting processes...')
        self.timer.start(1000)

    def stop(self):
        if self.search is not None:
            self._stop_search()
            self.progress.setText(self.progress.text() + ' (stopped)')

    def _stop_search(self):
        self.timer.stop()
        if self.search is not None:
            self.search.stop()
            self.search = None
        self.stop_button.setEnabled(False)
        self._validate_pattern()

    def _poll(self):
        search = self.search
        if search is None:
            return
        elapsed = time.monotonic() - self.started
        attempts = search.attempts
        if attempts:
            if elapsed >= SPEED_MEASURE_SECONDS:
                self.speed = attempts / elapsed / search.workers
            self.progress.setText(
                f'Checked {attempts:,} addresses in {format_duration(elapsed)} '
                f'({attempts / elapsed:,.0f}/s)'
            )
        result = search.result()
        if result is not None:
            self._stop_search()
            self._show_result(search, *result)
        elif search.failed:
            self._stop_search()
            self.app.show_error(ValueError('Vanity search process ended unexpectedly'))

    def _show_result(self, search: VanitySearch, address: str, wif: str):
        self.found = (search.coin_symbol, search.address_type, address, wif)
        self.result_address.setText(address)
        self.result_key.setText(wif)
        self.result_label.setText(f'Vanity {search.pattern}')
        self.result_group.show()

    def add_to_wallet(self):
        if self.found is None or self.app.wallet is None:
            return
        coin_symbol, address_type, _, wif = self.found
        label = self.result_label.text().strip()
        try:
            if not label:
                raise ValueError('Enter the label')
            self.app.modify_wallet(
                lambda wallet: add_private_key(wallet, label, coin_symbol, wif, address_type)
            )
        except EXPECTED_ERRORS as error:
            self.app.show_error(error)
            return
        self.discard()

    def discard(self):
        self.found = None
        self.result_address.clear()
        self.result_key.clear()
        self.result_label.clear()
        self.result_group.hide()
