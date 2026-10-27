"""Balance tab: unspent outputs of the wallet address or any other address (checkaddress)."""

from argparse import Namespace
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from multicrypto.commands.checkaddress import check_address
from multicrypto.gui.forms import (
    address_description,
    coins_with_api,
    format_amount,
    parse_address,
    parse_thresholds,
)
from multicrypto.wallet import WalletAddress

COLUMNS = ['Transaction id', 'Confirmations', 'Satoshis', 'Amount']


class BalanceTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.addresses: List[WalletAddress] = []
        self.wallet_source = QRadioButton('Wallet address')
        self.wallet_source.setChecked(True)
        self.other_source = QRadioButton('Other address')
        self.address_box = QComboBox()
        self.address_box.activated.connect(lambda _index: self.wallet_source.setChecked(True))
        self.coin = QComboBox()
        self.coin.addItems(coins_with_api())
        self.coin.setCurrentText('BTC')
        self.address = QLineEdit()
        self.address.textEdited.connect(lambda _text: self.other_source.setChecked(True))
        self.minimum = QLineEdit()
        self.maximum = QLineEdit()
        self.limit = QLineEdit()
        for field in (self.minimum, self.maximum):
            field.setPlaceholderText('satoshis')
        self.check_button = QPushButton('Check')
        self.check_button.clicked.connect(lambda _checked=False: self.check())
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.total = QLabel()
        source = QGridLayout()
        source.addWidget(self.wallet_source, 0, 0)
        source.addWidget(self.address_box, 0, 1, 1, 2)
        source.addWidget(self.other_source, 1, 0)
        source.addWidget(self.coin, 1, 1)
        source.addWidget(self.address, 1, 2)
        source.setColumnStretch(2, 1)
        filters = QHBoxLayout()
        for text, field in (
            ('Minimum input', self.minimum),
            ('Maximum input', self.maximum),
            ('Limit of inputs', self.limit),
        ):
            filters.addWidget(QLabel(text))
            filters.addWidget(field)
        filters.addStretch()
        filters.addWidget(self.check_button)
        layout = QVBoxLayout(self)
        layout.addLayout(source)
        layout.addLayout(filters)
        layout.addWidget(self.table)
        layout.addWidget(self.total, alignment=Qt.AlignmentFlag.AlignRight)

    def refresh(self):
        selected = self.address_box.currentData()
        self.addresses = self.app.wallet.addresses()
        self.address_box.clear()
        for address in self.addresses:
            self.address_box.addItem(address_description(address), address.id)
        index = self.address_box.findData(selected)
        if index >= 0:
            self.address_box.setCurrentIndex(index)

    def clear(self):
        self.addresses = []
        self.address_box.clear()
        self.table.setRowCount(0)
        self.total.setText('')

    def check_address(self, address: WalletAddress):
        self.address_box.setCurrentIndex(self.address_box.findData(address.id))
        self.wallet_source.setChecked(True)
        self.app.select_tab(self)
        self.check()

    def _get_address(self):
        if self.wallet_source.isChecked():
            index = self.address_box.currentIndex()
            if index < 0:
                raise ValueError('Select the wallet address')
            address = self.addresses[index]
            return address.coin, address.address
        coin_symbol = self.coin.currentText()
        return coin_symbol, parse_address(self.address.text(), coin_symbol)

    def check(self):
        try:
            coin_symbol, address = self._get_address()
            minimum, maximum, limit = parse_thresholds(
                self.minimum.text(), self.maximum.text(), self.limit.text()
            )
        except ValueError as error:
            self.app.show_error(error)
            return
        args = Namespace(
            coin_symbol=coin_symbol,
            address=address,
            minimum_input_threshold=minimum,
            maximum_input_threshold=maximum,
            limit_inputs=limit,
        )
        self.check_button.setEnabled(False)
        self.app.worker.run(
            lambda: check_address(args), lambda utxos: self._show(utxos, coin_symbol), self._failed
        )

    def _show(self, utxos, coin_symbol: str):
        self.check_button.setEnabled(True)
        self.table.setRowCount(len(utxos))
        for row, utxo in enumerate(utxos):
            values = (
                utxo['txid'],
                str(utxo['confirmations']),
                str(utxo['satoshis']),
                format_amount(utxo['satoshis']),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)
        total = sum(utxo['satoshis'] for utxo in utxos)
        self.total.setText(
            f'{len(utxos)} inputs, total {format_amount(total)} {coin_symbol} ({total} satoshis)'
        )

    def _failed(self, error):
        self.check_button.setEnabled(True)
        self.app.show_error(error)
