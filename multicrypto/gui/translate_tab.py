"""Translate tab: address and private key of another coin (transaddress, transprivkey)."""

import html
from typing import Optional

from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from multicrypto.coins import coins
from multicrypto.gui.dialogs import password_field
from multicrypto.gui.forms import (
    parse_private_key_input,
    translate_address_text,
    translated_key_addresses,
)
from multicrypto.gui.wallet_tab import TranslateKeyDialog

INVALID_COLOR = '#c62828'


def coin_box(symbol: str) -> QComboBox:
    box = QComboBox()
    box.addItems(sorted(coins))
    box.setCurrentText(symbol)
    return box


def copy_button(field: QLineEdit) -> QPushButton:
    button = QPushButton('Copy')
    button.clicked.connect(lambda _checked=False: QApplication.clipboard().setText(field.text()))
    return button


class TranslateTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.source_wif: Optional[str] = None
        self.address = QLineEdit()
        self.address_input_coin = coin_box('BTC')
        self.address_output_coin = coin_box('BTG')
        self.translated_address = QLineEdit()
        self.translated_address.setReadOnly(True)
        self.address_status = QLabel()
        address_button = QPushButton('Translate')
        address_button.clicked.connect(lambda _checked=False: self.translate_address())
        self.key = password_field()
        self.integer = QCheckBox('Integer (decimal or hex with 0x)')
        self.show_key = QCheckBox('Show keys')
        self.key_output_coin = coin_box('BTG')
        self.translated_key = password_field()
        self.translated_key.setReadOnly(True)
        self.key_addresses = QTableWidget(0, 2)
        self.key_addresses.setHorizontalHeaderLabels(['Address type', 'Address'])
        self.key_addresses.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.key_addresses.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.key_status = QLabel()
        key_button = QPushButton('Translate')
        key_button.clicked.connect(lambda _checked=False: self.translate_key())
        self.add_button = QPushButton('Add to wallet...')
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(lambda _checked=False: self.add_to_wallet())
        address_group = QGroupBox('Address (the same public key hash or script hash)')
        address_form = QFormLayout(address_group)
        address_form.addRow('Address', self.address)
        coins_row = QHBoxLayout()
        coins_row.addWidget(self.address_input_coin)
        coins_row.addWidget(QLabel('→'))
        coins_row.addWidget(self.address_output_coin)
        coins_row.addWidget(address_button)
        coins_row.addStretch()
        address_form.addRow('Coins', coins_row)
        result_row = QHBoxLayout()
        result_row.addWidget(self.translated_address)
        result_row.addWidget(copy_button(self.translated_address))
        address_form.addRow('Translated', result_row)
        address_form.addRow('', self.address_status)
        key_group = QGroupBox('Private key')
        key_form = QFormLayout(key_group)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key)
        key_row.addWidget(self.integer)
        key_row.addWidget(self.show_key)
        key_form.addRow('Private key', key_row)
        output_row = QHBoxLayout()
        output_row.addWidget(self.key_output_coin)
        output_row.addWidget(key_button)
        output_row.addStretch()
        key_form.addRow('To coin', output_row)
        translated_row = QHBoxLayout()
        translated_row.addWidget(self.translated_key)
        translated_row.addWidget(copy_button(self.translated_key))
        key_form.addRow('Translated key', translated_row)
        key_form.addRow('Addresses', self.key_addresses)
        key_form.addRow('', self.key_status)
        key_form.addRow('', self.add_button)
        layout = QVBoxLayout(self)
        layout.addWidget(address_group)
        layout.addWidget(key_group)
        self.address.textChanged.connect(lambda _text: self._clear_address_result())
        self.key.textChanged.connect(lambda _text: self._clear_key_result())
        self.integer.toggled.connect(lambda _checked: self._clear_key_result())
        self.key_output_coin.currentTextChanged.connect(lambda _text: self._clear_key_result())
        self.show_key.toggled.connect(self._show_keys)

    def refresh(self):
        pass  # the tab does not show wallet addresses

    def clear(self):
        self.address.clear()
        self.key.clear()
        self._clear_address_result()
        self._clear_key_result()

    def _show_keys(self, shown: bool):
        mode = QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        self.key.setEchoMode(mode)
        self.translated_key.setEchoMode(mode)

    def _clear_address_result(self):
        self.translated_address.clear()
        self.address_status.setText('')

    def _clear_key_result(self):
        self.source_wif = None
        self.translated_key.clear()
        self.key_addresses.setRowCount(0)
        self.key_status.setText('')
        self.add_button.setEnabled(False)

    def _error(self, label: QLabel, error: Exception):
        label.setText(f'<span style="color: {INVALID_COLOR}">{html.escape(str(error))}</span>')

    def translate_address(self):
        self._clear_address_result()
        try:
            translated = translate_address_text(
                self.address.text(),
                self.address_input_coin.currentText(),
                self.address_output_coin.currentText(),
            )
        except ValueError as error:
            self._error(self.address_status, error)
            return
        self.translated_address.setText(translated)

    def translate_key(self):
        self._clear_key_result()
        try:
            wif = parse_private_key_input(self.key.text(), self.integer.isChecked())
            translated, addresses = translated_key_addresses(
                wif, self.key_output_coin.currentText()
            )
        except ValueError as error:
            self._error(self.key_status, error)
            return
        self.source_wif = wif
        self.translated_key.setText(translated)
        self.key_addresses.setRowCount(len(addresses))
        for row, (address_type, address) in enumerate(addresses):
            self.key_addresses.setItem(row, 0, QTableWidgetItem(address_type))
            self.key_addresses.setItem(row, 1, QTableWidgetItem(address))
        self.add_button.setEnabled(self.app.wallet is not None)

    def add_to_wallet(self):
        if self.source_wif is None or self.app.wallet is None:
            return

        def submit(label, coin, wif, address_type):
            self.app.modify_wallet(lambda wallet: wallet.add_wif(label, coin, wif, address_type))

        TranslateKeyDialog(
            self,
            'Add private key',
            self.source_wif,
            'Translated key',
            submit,
            self.key_output_coin.currentText(),
        ).exec()
