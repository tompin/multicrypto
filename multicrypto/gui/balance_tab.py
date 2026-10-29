"""Balance tab: unspent outputs of the wallet address or any other address, or the balance of
Ethereum address (checkaddress)."""

from argparse import Namespace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from multicrypto.coins import is_ethereum
from multicrypto.commands.checkaddress import check_address, check_ethereum_address
from multicrypto.ethereum import format_ether
from multicrypto.gui.address_picker import WalletAddressPicker
from multicrypto.gui.dialogs import coin_box, set_coins
from multicrypto.gui.forms import (
    all_coins_with_api,
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
        self.coin = coin_box(app.visible_coins(all_coins_with_api()))
        self.coin.currentTextChanged.connect(lambda _text: self._coin_changed())
        self.wallet_source = QRadioButton('Wallet address')
        self.wallet_source.setChecked(True)
        self.other_source = QRadioButton('Other address')
        self.picker = WalletAddressPicker()
        self.picker.box.activated.connect(lambda _index: self.wallet_source.setChecked(True))
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
        source.addWidget(QLabel('Coin'), 0, 0)
        source.addWidget(self.coin, 0, 1)
        source.addWidget(self.wallet_source, 1, 0, alignment=Qt.AlignmentFlag.AlignTop)
        source.addWidget(self.picker, 1, 1)
        source.addWidget(self.other_source, 2, 0)
        source.addWidget(self.address, 2, 1)
        source.setColumnStretch(1, 1)
        self.filters = QWidget()
        filters = QHBoxLayout(self.filters)
        filters.setContentsMargins(0, 0, 0, 0)
        for text, field in (
            ('Minimum input', self.minimum),
            ('Maximum input', self.maximum),
            ('Limit of inputs', self.limit),
        ):
            filters.addWidget(QLabel(text))
            filters.addWidget(field)
        actions = QHBoxLayout()
        actions.addWidget(self.filters)
        actions.addStretch()
        actions.addWidget(self.check_button)
        self.account = QLabel()  # balance, nonce and transactions of Ethereum address
        self.account.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.addLayout(source)
        layout.addLayout(actions)
        layout.addWidget(self.table)
        layout.addWidget(self.total, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.account)
        layout.addStretch()
        self._update_mode()

    def refresh(self):
        self._show_addresses()

    def update_coins(self):
        set_coins(self.coin, self.app.visible_coins(all_coins_with_api()))

    def _coin_changed(self):
        self._show_addresses()
        self._update_mode()

    def _update_mode(self):
        """Ethereum addresses have a balance instead of unspent outputs."""
        ethereum = is_ethereum(self.coin.currentText())
        self.filters.setVisible(not ethereum)
        self.table.setVisible(not ethereum)
        self.total.setVisible(not ethereum)
        self.account.setVisible(ethereum)

    def _show_addresses(self):
        wallet = self.app.wallet
        coin_symbol = self.coin.currentText()
        addresses = [] if wallet is None else wallet.addresses()
        self.picker.set_addresses(
            wallet, [address for address in addresses if address.coin == coin_symbol]
        )

    def clear(self):
        self.picker.clear()
        self.table.setRowCount(0)
        self.total.setText('')
        self.account.setText('')

    def check_address(self, address: WalletAddress):
        self.coin.setCurrentText(address.coin)
        self.picker.select(address.id)
        self.wallet_source.setChecked(True)
        self.app.select_tab(self)
        self.check()

    def _get_address(self):
        if self.wallet_source.isChecked():
            address = self.picker.current()
            if address is None:
                raise ValueError('Select the wallet address')
            return address.coin, address.address
        coin_symbol = self.coin.currentText()
        return coin_symbol, parse_address(self.address.text(), coin_symbol)

    def check(self):
        try:
            coin_symbol, address = self._get_address()
            if not is_ethereum(coin_symbol):
                minimum, maximum, limit = parse_thresholds(
                    self.minimum.text(), self.maximum.text(), self.limit.text()
                )
        except ValueError as error:
            self.app.show_error(error)
            return
        self.check_button.setEnabled(False)
        if is_ethereum(coin_symbol):
            args = Namespace(coin_symbol=coin_symbol, address=address, node=None)
            self.app.worker.run(
                lambda: check_ethereum_address(args),
                lambda account: self._show_account(account, coin_symbol),
                self._failed,
            )
            return
        args = Namespace(
            coin_symbol=coin_symbol,
            address=address,
            minimum_input_threshold=minimum,
            maximum_input_threshold=maximum,
            limit_inputs=limit,
        )
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

    def _show_account(self, account, coin_symbol: str):
        self.check_button.setEnabled(True)
        tx_count = 'not available' if account.tx_count is None else str(account.tx_count)
        self.account.setText(
            f'Address: {account.address}\n'
            f'Balance: {format_ether(account.balance)} {coin_symbol} ({account.balance} wei)\n'
            f'Sent transactions (nonce): {account.nonce}\n'
            f'All transactions: {tx_count}'
        )

    def _failed(self, error):
        self.check_button.setEnabled(True)
        self.app.show_error(error)
