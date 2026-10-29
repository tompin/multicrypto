"""Sign / Verify tab: signing messages with wallet keys and verifying signatures (BIP-137, EIP-191
for Ethereum)."""

import html

from PySide6.QtWidgets import (
    QApplication,
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

from multicrypto import ethereum
from multicrypto.coins import P2TR, coins, is_ethereum
from multicrypto.ecdsa import sign_message, verify_signature
from multicrypto.gui.address_picker import WalletAddressPicker
from multicrypto.gui.dialogs import coin_box, set_coins
from multicrypto.gui.forms import all_coins, check_signable, parse_address
from multicrypto.wallet import WalletAddress

VALID_COLOR = '#2e7d32'
INVALID_COLOR = '#c62828'


class SignTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.sign_coin = coin_box(app.visible_coins(all_coins()))
        self.sign_coin.currentTextChanged.connect(lambda _text: self.refresh())
        self.sign_picker = WalletAddressPicker()
        self.sign_message = QPlainTextEdit()
        self.sign_button = QPushButton('Sign')
        self.sign_button.clicked.connect(lambda _checked=False: self.sign())
        self.signature = QLineEdit()
        self.signature.setReadOnly(True)
        copy_button = QPushButton('Copy')
        copy_button.clicked.connect(
            lambda _checked=False: QApplication.clipboard().setText(self.signature.text())
        )
        self.verify_coin = coin_box(app.visible_coins(all_coins()))
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
        sign_group = QGroupBox(
            'Sign message (p2pkh, p2sh-p2wpkh and p2wpkh addresses, BIP-137, taproot addresses '
            'are not supported; Ethereum addresses like personal_sign, EIP-191)'
        )
        sign_form = QFormLayout(sign_group)
        sign_form.addRow('Coin', self.sign_coin)
        sign_form.addRow('Address', self.sign_picker)
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
        wallet = self.app.wallet
        coin_symbol = self.sign_coin.currentText()
        addresses = [] if wallet is None else wallet.addresses()
        self.sign_picker.set_addresses(
            wallet,
            [
                address
                for address in addresses
                if address.coin == coin_symbol and address.address_type != P2TR
            ],
        )

    def update_coins(self):
        set_coins(self.sign_coin, self.app.visible_coins(all_coins()))
        set_coins(self.verify_coin, self.app.visible_coins(all_coins()))

    def clear(self):
        self.sign_picker.clear()
        for text_edit in (self.sign_message, self.verify_message):
            text_edit.clear()
        for line_edit in (self.signature, self.verify_address, self.verify_signature):
            line_edit.clear()
        self.verify_result.setText('')

    def select_address(self, address: WalletAddress):
        self.sign_coin.setCurrentText(address.coin)
        self.sign_picker.select(address.id)
        self.signature.clear()
        self.app.select_tab(self)

    def sign(self):
        try:
            address = self.sign_picker.current()
            if address is None:
                raise ValueError('Select the wallet address')
            check_signable(address)
            message = self.sign_message.toPlainText()
            if not message:
                raise ValueError('Enter the message')
        except ValueError as error:
            self.app.show_error(error)
            return
        self.signature.clear()
        self.sign_button.setEnabled(False)
        if is_ethereum(address.coin):
            private_key = self.app.wallet.private_key(address)
            self.app.worker.run(
                lambda: ethereum.sign_message(message, private_key), self._signed, self._failed
            )
            return
        wif = self.app.wallet.private_key_wif(address)
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
        """Select the coin of the wallet address entered for verification (the selected coin is
        kept when it has the address, e.g. ETH and TETH have the same addresses), an address
        starting with 0x selects ETH unless an Ethereum coin is selected."""
        address_text = text.strip()
        if self.app.wallet is not None:
            wallet_coins = [
                address.coin
                for address in self.app.wallet.addresses()
                if address.address == address_text
            ]
            if wallet_coins:
                if self.verify_coin.currentText() not in wallet_coins:
                    self.verify_coin.setCurrentText(wallet_coins[0])
                return
        if address_text.startswith('0x') and not is_ethereum(self.verify_coin.currentText()):
            self.verify_coin.setCurrentText('ETH')

    def verify(self):
        coin_symbol = self.verify_coin.currentText()
        message = self.verify_message.toPlainText()
        signature = self.verify_signature.text()
        try:
            address = parse_address(self.verify_address.text(), coin_symbol)
            if is_ethereum(coin_symbol):
                valid = ethereum.verify_message(message, signature, address)
            else:
                valid = verify_signature(coins[coin_symbol], message, signature, address)
        except ValueError as error:
            self._show_result(str(error), INVALID_COLOR)
            return
        if valid:
            self._show_result('Signature is valid', VALID_COLOR)
        else:
            self._show_result('Signature is not valid', INVALID_COLOR)

    def _show_result(self, text: str, color: str):
        self.verify_result.setText(f'<span style="color: {color}">{html.escape(text)}</span>')
