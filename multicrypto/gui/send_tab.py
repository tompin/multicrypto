"""Send tab: preparing, confirming and broadcasting transactions (sendcrypto)."""

import json
from typing import List, Optional

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from multicrypto.api import broadcast_prepared, prepare_from_private_keys
from multicrypto.coins import coins
from multicrypto.gui.dialogs import coin_box, confirm, set_coins, show_text
from multicrypto.gui.fee import FeeRateField
from multicrypto.gui.forms import (
    EXPECTED_ERRORS,
    address_details,
    check_sources,
    coins_with_api,
    describe_transaction,
    extract_txid,
    parse_address,
    parse_amount,
    parse_nodes,
    parse_thresholds,
)
from multicrypto.network import broadcast_transaction
from multicrypto.wallet import CHANGE_CHAIN, WalletAddress

ID_ROLE = Qt.ItemDataRole.UserRole
SOURCE_COLUMNS = ['Address', 'Account', 'Address type', 'Path', 'Label']


class SendTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.coin = coin_box(app.visible_coins(coins_with_api()))
        self.coin.currentTextChanged.connect(lambda _text: self.refresh())
        self.sources = QTableWidget(0, len(SOURCE_COLUMNS))
        self.sources.setHorizontalHeaderLabels(SOURCE_COLUMNS)
        self.sources.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sources.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.sources.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sources.verticalHeader().hide()
        header = self.sources.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.destination = QLineEdit()
        self.destination_status = QLabel()
        self.amount = QLineEdit()
        self.amount.setPlaceholderText('in coin units, e.g. 0.001')
        self.fee = FeeRateField(app, self._source_coin)
        self.minimum = QLineEdit()
        self.maximum = QLineEdit()
        self.limit = QLineEdit()
        self.p2p = QCheckBox('Send directly to the peer-to-peer network')
        self.nodes = QLineEdit()
        self.nodes.setPlaceholderText('optional, host[:port] separated with commas')
        self.prepare_button = QPushButton('Prepare transaction...')
        self.prepare_button.clicked.connect(lambda _checked=False: self.prepare())
        form = QFormLayout()
        form.addRow('To address', self.destination)
        form.addRow('', self.destination_status)
        form.addRow('Amount', self.amount)
        form.addRow('Fee rate (sat/vB)', self.fee)
        advanced = QGroupBox('Advanced')
        advanced_form = QFormLayout(advanced)
        advanced_form.addRow('Minimum input (satoshis)', self.minimum)
        advanced_form.addRow('Maximum input (satoshis)', self.maximum)
        advanced_form.addRow('Limit of inputs', self.limit)
        advanced_form.addRow(self.p2p)
        advanced_form.addRow('Nodes', self.nodes)
        coin_form = QFormLayout()
        coin_form.addRow('Coin', self.coin)
        layout = QVBoxLayout(self)
        layout.addLayout(coin_form)
        layout.addWidget(QLabel('From (one or more addresses with the same address type)'))
        layout.addWidget(self.sources)
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(self.prepare_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.destination.textChanged.connect(self._validate_destination)
        self.sources.itemSelectionChanged.connect(self._validate_destination)

    def refresh(self):
        selected = set(self._selected_ids())
        wallet = self.app.wallet
        coin_symbol = self.coin.currentText()
        addresses = [] if wallet is None else wallet.addresses()
        addresses = [address for address in addresses if address.coin == coin_symbol]
        self.sources.clearSelection()
        self.sources.setRowCount(len(addresses))
        for row, address in enumerate(addresses):
            values = [address.address] + [text for _, text in address_details(wallet, address)]
            for column, value in enumerate(values):
                self.sources.setItem(row, column, QTableWidgetItem(value))
            self.sources.item(row, 0).setData(ID_ROLE, address.id)
            if address.id in selected:
                self._select_row(row)

    def update_coins(self):
        set_coins(self.coin, self.app.visible_coins(coins_with_api()))

    def clear(self):
        self.sources.setRowCount(0)
        self.destination.clear()
        self.amount.clear()

    def select_source(self, address: WalletAddress):
        self.coin.setCurrentText(address.coin)
        self.sources.clearSelection()
        for row in range(self.sources.rowCount()):
            if self.sources.item(row, 0).data(ID_ROLE) == address.id:
                self._select_row(row)
        self.app.select_tab(self)

    def _select_row(self, row: int):
        """Add the row to the selected sources (selectRow would replace the selection)."""
        self.sources.selectionModel().select(
            self.sources.model().index(row, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )

    def _selected_ids(self) -> List[str]:
        rows = sorted({index.row() for index in self.sources.selectedIndexes()})
        return [self.sources.item(row, 0).data(ID_ROLE) for row in rows]

    def _selected_addresses(self) -> List[WalletAddress]:
        return [self.app.wallet.get_address(address_id) for address_id in self._selected_ids()]

    def _source_coin(self) -> Optional[str]:
        try:
            return check_sources(self._selected_addresses())[0]
        except ValueError:
            return None

    def _validate_destination(self):
        text = self.destination.text()
        if not text.strip() or self.app.wallet is None:
            self.destination_status.setText('')
            return
        try:
            coin_symbol, _ = check_sources(self._selected_addresses())
            parse_address(text, coin_symbol)
        except ValueError as error:
            self.destination_status.setText(f'<span style="color: #c62828">{error}</span>')
        else:
            self.destination_status.setText(
                f'<span style="color: #2e7d32">Correct {coin_symbol} address</span>'
            )

    def prepare(self):
        try:
            addresses = self._selected_addresses()
            coin_symbol, address_type = check_sources(addresses)
            coin = coins[coin_symbol]
            if not coin.get('apis'):
                raise ValueError(f'No API has been defined for the coin {coin_symbol}')
            destination = parse_address(self.destination.text(), coin_symbol)
            satoshis = parse_amount(self.amount.text())
            fee_rate = self.fee.value()
            minimum, maximum, limit = parse_thresholds(
                self.minimum.text(), self.maximum.text(), self.limit.text()
            )
            broadcast, target = self._get_broadcast(coin, coin_symbol)
        except ValueError as error:
            self.app.show_error(error)
            return
        wif_private_keys = [self.app.wallet.private_key_wif(address) for address in addresses]
        source_addresses = [address.address for address in addresses]
        change = self._change_address(addresses)

        def prepare_transaction():
            return prepare_from_private_keys(
                coin=coin,
                wif_private_keys=wif_private_keys,
                input_addresses=None,
                unlocking_scripts=None,
                destination_address=destination,
                satoshis=satoshis,
                fee=None,
                minimum_input_threshold=minimum,
                maximum_input_threshold=maximum,
                limit_inputs=limit,
                address_type=address_type,
                change_address=change.address if change else None,
                fee_rate=fee_rate,
            )

        self.prepare_button.setEnabled(False)
        self.app.worker.run(
            prepare_transaction,
            lambda prepared: self._confirm(
                coin, coin_symbol, prepared, source_addresses, broadcast, target, change
            ),
            self._failed,
        )

    def _get_broadcast(self, coin, coin_symbol: str):
        """Return function broadcasting the transaction (None for the API) and its description."""
        if not self.p2p.isChecked() and not self.nodes.text().strip():
            return None, 'block explorer API'
        if 'network' not in coin:
            raise ValueError(f'No peer-to-peer network has been defined for the coin {coin_symbol}')
        nodes = parse_nodes(self.nodes.text(), coin['network']['port'])

        def broadcast(raw_transaction):
            return json.dumps({'txid': broadcast_transaction(coin, raw_transaction, nodes)})

        return broadcast, 'peer-to-peer network'

    def _change_address(self, addresses: List[WalletAddress]) -> Optional[WalletAddress]:
        """Next change address of the HD account of all sources, None sends the change back to
        the source address."""
        account_ids = {address.account_id for address in addresses}
        if len(account_ids) != 1 or None in account_ids:
            return None
        return self.app.wallet.next_change_address(account_ids.pop())

    def _confirm(
        self, coin, coin_symbol, prepared, source_addresses, broadcast, target, change=None
    ):
        self.prepare_button.setEnabled(True)
        has_change = change is not None and any(
            output['address'] == change.address for output in prepared.outputs[1:]
        )
        change = change if has_change else None
        rows = describe_transaction(
            prepared, coin_symbol, source_addresses, target, change.path if change else None
        )
        if not confirm(self, 'Confirm transaction', rows, 'Send'):
            return
        self.prepare_button.setEnabled(False)
        self.app.worker.run(
            lambda: extract_txid(broadcast_prepared(coin, prepared, broadcast)),
            lambda txid: self._sent(txid, change),
            self._failed,
        )

    def _sent(self, txid: str, change: Optional[WalletAddress] = None):
        self.prepare_button.setEnabled(True)
        self.amount.clear()
        if change is not None and self.app.wallet is not None:
            try:
                self.app.modify_wallet(
                    lambda wallet: wallet.add_address(change.account_id, CHANGE_CHAIN, change.index)
                )
            except EXPECTED_ERRORS as error:
                QMessageBox.warning(
                    self,
                    'Change address',
                    f'The change was sent to {change.address} ({change.path}), but it could not '
                    f'be saved in the wallet: {error}. Scan for used addresses finds it.',
                )
        show_text(self, 'Transaction sent', 'Transaction id', txid)

    def _failed(self, error):
        self.prepare_button.setEnabled(True)
        self.app.show_error(error)
