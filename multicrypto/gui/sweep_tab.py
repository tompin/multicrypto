"""Sweep tab: sending all unspent outputs of the address in batches (sweepaddress)."""

import html
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from multicrypto.api import broadcast_prepared, get_utxo_from_private_keys, prepare_sweep
from multicrypto.coins import coins, get_address_types
from multicrypto.gui.dialogs import confirm, password_field, show_lines
from multicrypto.gui.forms import (
    address_description,
    coins_with_api,
    describe_error,
    describe_sweep,
    extract_txid,
    parse_address,
    parse_int,
    parse_thresholds,
    parse_wif,
)
from multicrypto.wallet import WalletAddress

DEFAULT_FEE = 10000
DEFAULT_BATCH_SIZE = 50
VALID_COLOR = '#2e7d32'
INVALID_COLOR = '#c62828'


def colored(text: str, color: str) -> str:
    return f'<span style="color: {color}">{html.escape(text)}</span>'


class SweepTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.addresses: List[WalletAddress] = []  # wallet addresses of coins with API
        self.wallet_source = QRadioButton('Wallet address')
        self.wallet_source.setChecked(True)
        self.key_source = QRadioButton('External private key (WIF)')
        self.source_box = QComboBox()
        self.coin = QComboBox()
        self.coin.addItems(coins_with_api())
        self.coin.setCurrentText('BTC')
        self.address_type = QComboBox()
        self.wif = password_field()
        self.wif.setPlaceholderText('used once, it is not saved in the wallet')
        self.show_wif = QCheckBox('Show')
        self.key_address = QLabel()
        self.same_destination = QRadioButton('The same address')
        self.same_destination.setChecked(True)
        self.wallet_destination = QRadioButton('Wallet address')
        self.other_destination = QRadioButton('Other address')
        self.destination_box = QComboBox()
        self.destination = QLineEdit()
        self.destination_status = QLabel()
        self.fee = QLineEdit(str(DEFAULT_FEE))
        self.minimum = QLineEdit()
        self.maximum = QLineEdit()
        self.batch_size = QLineEdit(str(DEFAULT_BATCH_SIZE))
        self.progress = QLabel()
        self.prepare_button = QPushButton('Prepare sweep...')
        self.prepare_button.clicked.connect(lambda _checked=False: self.prepare())
        # radio buttons are exclusive within their group box
        source = QGroupBox('From')
        source_grid = QGridLayout(source)
        source_grid.addWidget(self.wallet_source, 0, 0)
        source_grid.addWidget(self.source_box, 0, 1, 1, 4)
        source_grid.addWidget(self.key_source, 1, 0)
        source_grid.addWidget(self.coin, 1, 1)
        source_grid.addWidget(self.address_type, 1, 2)
        source_grid.addWidget(self.wif, 1, 3)
        source_grid.addWidget(self.show_wif, 1, 4)
        source_grid.addWidget(self.key_address, 2, 3)
        source_grid.setColumnStretch(3, 1)
        destination = QGroupBox('To')
        destination_grid = QGridLayout(destination)
        destination_grid.addWidget(self.same_destination, 0, 0)
        destination_grid.addWidget(self.wallet_destination, 1, 0)
        destination_grid.addWidget(self.destination_box, 1, 1)
        destination_grid.addWidget(self.other_destination, 2, 0)
        destination_grid.addWidget(self.destination, 2, 1)
        destination_grid.addWidget(self.destination_status, 3, 1)
        destination_grid.setColumnStretch(1, 1)
        form = QFormLayout()
        form.addRow('Fee per transaction (satoshis)', self.fee)
        advanced = QGroupBox('Advanced')
        advanced_form = QFormLayout(advanced)
        advanced_form.addRow('Minimum input (satoshis)', self.minimum)
        advanced_form.addRow('Maximum input (satoshis)', self.maximum)
        advanced_form.addRow('Inputs per transaction', self.batch_size)
        layout = QVBoxLayout(self)
        layout.addWidget(source)
        layout.addWidget(destination)
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(self.progress)
        layout.addWidget(self.prepare_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch()
        self.source_box.activated.connect(lambda _index: self.wallet_source.setChecked(True))
        self.source_box.currentIndexChanged.connect(lambda _index: self._update_destinations())
        self.wallet_source.toggled.connect(lambda _checked: self._update_destinations())
        self.wif.textEdited.connect(lambda _text: self.key_source.setChecked(True))
        self.wif.textChanged.connect(lambda _text: self._update_key_address())
        self.show_wif.toggled.connect(self._show_wif)
        self.coin.currentTextChanged.connect(lambda _text: self._coin_changed())
        self.address_type.currentTextChanged.connect(lambda _text: self._update_key_address())
        self.destination_box.activated.connect(
            lambda _index: self.wallet_destination.setChecked(True)
        )
        self.destination.textEdited.connect(lambda _text: self.other_destination.setChecked(True))
        self.destination.textChanged.connect(lambda _text: self._validate_destination())
        self._coin_changed()

    def refresh(self):
        selected = self.source_box.currentData()
        self.addresses = [
            address for address in self.app.wallet.addresses() if coins[address.coin].get('apis')
        ]
        self.source_box.clear()
        for address in self.addresses:
            self.source_box.addItem(address_description(address), address.id)
        index = self.source_box.findData(selected)
        if index >= 0:
            self.source_box.setCurrentIndex(index)
        self._update_destinations()

    def clear(self):
        self.addresses = []
        self.source_box.clear()
        self.destination_box.clear()
        self.wif.clear()
        self.destination.clear()
        self.progress.setText('')

    def select_source(self, address: WalletAddress):
        self.source_box.setCurrentIndex(self.source_box.findData(address.id))
        self.wallet_source.setChecked(True)
        self.app.select_tab(self)

    def _show_wif(self, shown: bool):
        self.wif.setEchoMode(QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password)

    def _coin_changed(self):
        self.address_type.clear()
        self.address_type.addItems(get_address_types(coins[self.coin.currentText()]))
        self._update_key_address()
        self._update_destinations()

    def _source_coin(self) -> Optional[str]:
        if self.key_source.isChecked():
            return self.coin.currentText()
        index = self.source_box.currentIndex()
        return self.addresses[index].coin if index >= 0 else None

    def _update_key_address(self):
        if not self.wif.text().strip():
            self.key_address.setText('')
            return
        try:
            _, address = parse_wif(
                self.wif.text(), self.coin.currentText(), self.address_type.currentText()
            )
        except ValueError as error:
            self.key_address.setText(colored(str(error), INVALID_COLOR))
        else:
            self.key_address.setText(address)

    def _update_destinations(self):
        """Fill the wallet addresses of the source coin, the same address needs wallet source."""
        wallet_source = self.wallet_source.isChecked()
        self.same_destination.setEnabled(wallet_source)
        if not wallet_source and self.same_destination.isChecked():
            self.wallet_destination.setChecked(True)
        selected = self.destination_box.currentData()
        self.destination_box.clear()
        if self.app.wallet is None:
            return
        coin_symbol = self._source_coin()
        for address in self.app.wallet.addresses():
            if address.coin == coin_symbol:
                self.destination_box.addItem(address_description(address), address.id)
        index = self.destination_box.findData(selected)
        if index >= 0:
            self.destination_box.setCurrentIndex(index)
        self._validate_destination()

    def _validate_destination(self):
        text = self.destination.text()
        coin_symbol = self._source_coin()
        if not text.strip() or coin_symbol is None:
            self.destination_status.setText('')
            return
        try:
            parse_address(text, coin_symbol)
        except ValueError as error:
            self.destination_status.setText(colored(str(error), INVALID_COLOR))
        else:
            self.destination_status.setText(colored(f'Correct {coin_symbol} address', VALID_COLOR))

    def _get_source(self):
        """Return coin symbol, address type, private key and address of the source."""
        if self.key_source.isChecked():
            coin_symbol = self.coin.currentText()
            address_type = self.address_type.currentText()
            wif, address = parse_wif(self.wif.text(), coin_symbol, address_type)
            return coin_symbol, address_type, wif, address
        index = self.source_box.currentIndex()
        if index < 0:
            raise ValueError('Select the wallet address')
        address = self.addresses[index]
        wif = self.app.wallet.private_key_wif(address)
        return address.coin, address.address_type, wif, address.address

    def _get_destination(self, coin_symbol: str, source_address: str) -> str:
        if self.same_destination.isChecked():
            return source_address
        if self.wallet_destination.isChecked():
            address_id = self.destination_box.currentData()
            if address_id is None:
                raise ValueError(f'Select the destination wallet address of {coin_symbol}')
            return self.app.wallet.get_address(address_id).address
        return parse_address(self.destination.text(), coin_symbol)

    def prepare(self):
        try:
            coin_symbol, address_type, wif, source_address = self._get_source()
            destination = self._get_destination(coin_symbol, source_address)
            fee = parse_int(self.fee.text(), 'Fee', minimum=0)
            minimum, maximum, _ = parse_thresholds(self.minimum.text(), self.maximum.text(), '')
            batch_size = parse_int(self.batch_size.text(), 'Inputs per transaction')
        except ValueError as error:
            self.app.show_error(error)
            return
        coin = coins[coin_symbol]

        def prepare_transactions():
            utxos = get_utxo_from_private_keys(coin, [wif], address_type, minimum, maximum)
            return prepare_sweep(coin, list(utxos), destination, fee, batch_size)

        self.prepare_button.setEnabled(False)
        self.app.worker.run(
            prepare_transactions,
            lambda prepared: self._confirm(
                coin, coin_symbol, prepared, source_address, destination
            ),
            self._failed,
        )

    def _confirm(self, coin, coin_symbol, prepared, source_address, destination):
        self.prepare_button.setEnabled(True)
        if self.app.wallet is None:
            return
        rows = describe_sweep(prepared, coin_symbol, source_address, destination)
        if confirm(self, 'Confirm sweep', rows, 'Send'):
            self.prepare_button.setEnabled(False)
            self._broadcast(coin, prepared, [])

    def _broadcast(self, coin, prepared, txids: List[str]):
        """Broadcast the next transaction, the transactions are sent one after another."""
        if self.app.wallet is None:
            self.prepare_button.setEnabled(True)
            self.progress.setText('')
            return
        if len(txids) == len(prepared):
            self._sent(txids)
            return
        self.progress.setText(f'Broadcast {len(txids) + 1}/{len(prepared)}')
        transaction = prepared[len(txids)]
        self.app.worker.run(
            lambda: extract_txid(broadcast_prepared(coin, transaction)),
            lambda txid: self._broadcast(coin, prepared, txids + [txid]),
            lambda error: self._broadcast_failed(error, txids),
        )

    def _sent(self, txids: List[str]):
        self.prepare_button.setEnabled(True)
        self.progress.setText('')
        self.wif.clear()
        show_lines(self, 'Sweep sent', f'Transactions sent: {len(txids)}', txids)

    def _broadcast_failed(self, error, txids: List[str]):
        self.prepare_button.setEnabled(True)
        self.progress.setText('')
        if self.app.wallet is None:
            return
        message = describe_error(error)
        if txids:
            message += '\n\nTransactions sent before the error:\n' + '\n'.join(txids)
        QMessageBox.critical(self, 'Error', message)

    def _failed(self, error):
        self.prepare_button.setEnabled(True)
        self.app.show_error(error)
