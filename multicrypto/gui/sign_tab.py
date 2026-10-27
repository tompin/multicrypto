"""Sign / Verify tab: signing messages with wallet keys and verifying signatures (BIP-137)."""

import html
from typing import List

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from multicrypto.coins import P2TR, coins
from multicrypto.ecdsa import sign_message, verify_signature
from multicrypto.gui.forms import address_description, check_signable, parse_address
from multicrypto.wallet import WalletAddress

VALID_COLOR = '#2e7d32'
INVALID_COLOR = '#c62828'


class SignTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.addresses: List[WalletAddress] = []
        self.sign_address = QComboBox()
        self.sign_message = QPlainTextEdit()
        self.sign_button = QPushButton('Sign')
        self.sign_button.clicked.connect(lambda _checked=False: self.sign())
        self.signature = QLineEdit()
        self.signature.setReadOnly(True)
        copy_button = QPushButton('Copy')
        copy_button.clicked.connect(
            lambda _checked=False: QApplication.clipboard().setText(self.signature.text())
        )
        self.verify_coin = QComboBox()
        self.verify_coin.addItems(sorted(coins))
        self.verify_coin.setCurrentText('BTC')
        self.verify_address = QLineEdit()
        self.verify_address.textChanged.connect(self._detect_coin)
        self.verify_message = QPlainTextEdit()
        self.verify_signature = QLineEdit()
        self.verify_button = QPushButton('Verify')
        self.verify_button.clicked.connect(lambda _checked=False: self.verify())
        self.verify_result = QLabel()
        sign_row = QHBoxLayout()
        sign_row.addWidget(self.sign_button)
        sign_row.addStretch()
        signature_row = QHBoxLayout()
        signature_row.addWidget(self.signature)
        signature_row.addWidget(copy_button)
        sign_group = QGroupBox('Sign message (p2pkh, p2sh-p2wpkh and p2wpkh addresses, BIP-137)')
        sign_form = QFormLayout(sign_group)
        sign_form.addRow('Address', self.sign_address)
        sign_form.addRow('Message', self.sign_message)
        sign_form.addRow('', sign_row)
        sign_form.addRow('Signature', signature_row)
        verify_row = QHBoxLayout()
        verify_row.addWidget(self.verify_button)
        verify_row.addWidget(self.verify_result, 1)
        verify_group = QGroupBox('Verify message')
        verify_form = QFormLayout(verify_group)
        verify_form.addRow('Coin', self.verify_coin)
        verify_form.addRow('Address', self.verify_address)
        verify_form.addRow('Message', self.verify_message)
        verify_form.addRow('Signature', self.verify_signature)
        verify_form.addRow('', verify_row)
        layout = QVBoxLayout(self)
        layout.addWidget(sign_group)
        layout.addWidget(verify_group)

    def refresh(self):
        selected = self.sign_address.currentData()
        self.addresses = self.app.wallet.addresses()
        self.sign_address.clear()
        for address in self.addresses:
            taproot = address.address_type == P2TR
            suffix = ' (taproot: not supported)' if taproot else ''
            self.sign_address.addItem(address_description(address) + suffix, address.id)
            if taproot:
                self.sign_address.model().item(self.sign_address.count() - 1).setEnabled(False)
        index = self.sign_address.findData(selected)
        if index >= 0:
            self.sign_address.setCurrentIndex(index)

    def clear(self):
        self.addresses = []
        self.sign_address.clear()
        for text_edit in (self.sign_message, self.verify_message):
            text_edit.clear()
        for line_edit in (self.signature, self.verify_address, self.verify_signature):
            line_edit.clear()
        self.verify_result.setText('')

    def select_address(self, address: WalletAddress):
        self.sign_address.setCurrentIndex(self.sign_address.findData(address.id))
        self.signature.clear()
        self.app.select_tab(self)

    def sign(self):
        try:
            index = self.sign_address.currentIndex()
            if index < 0:
                raise ValueError('Select the wallet address')
            address = self.addresses[index]
            check_signable(address)
            message = self.sign_message.toPlainText()
            if not message:
                raise ValueError('Enter the message')
        except ValueError as error:
            self.app.show_error(error)
            return
        wif = self.app.wallet.private_key_wif(address)
        self.signature.clear()
        self.sign_button.setEnabled(False)
        self.app.worker.run(
            lambda: sign_message(coins[address.coin], message, wif, address.address_type).decode(),
            self._signed,
            self._failed,
        )

    def _signed(self, signature: str):
        self.sign_button.setEnabled(True)
        if self.app.wallet is not None:
            self.signature.setText(signature)

    def _failed(self, error):
        self.sign_button.setEnabled(True)
        self.app.show_error(error)

    def _detect_coin(self, text: str):
        """Select the coin of the wallet address entered for verification."""
        for address in self.addresses:
            if address.address == text.strip():
                self.verify_coin.setCurrentText(address.coin)
                return

    def verify(self):
        coin_symbol = self.verify_coin.currentText()
        try:
            address = parse_address(self.verify_address.text(), coin_symbol)
            valid = verify_signature(
                coins[coin_symbol],
                self.verify_message.toPlainText(),
                self.verify_signature.text(),
                address,
            )
        except ValueError as error:
            self._show_result(str(error), INVALID_COLOR)
            return
        if valid:
            self._show_result('Signature is valid', VALID_COLOR)
        else:
            self._show_result('Signature is not valid', INVALID_COLOR)

    def _show_result(self, text: str, color: str):
        self.verify_result.setText(f'<span style="color: {color}">{html.escape(text)}</span>')
