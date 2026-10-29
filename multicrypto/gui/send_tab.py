"""Send tab: preparing, confirming and broadcasting transactions (sendcrypto)."""

import json
from typing import List, Optional

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
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

from multicrypto import ethereum_api
from multicrypto.api import broadcast_prepared, prepare_from_private_keys
from multicrypto.coins import coins, ethereum_coins, is_ethereum
from multicrypto.ethereum import format_ether, format_gwei
from multicrypto.gui.dialogs import coin_box, confirm, set_coins, show_text
from multicrypto.gui.fee import FeeRateField
from multicrypto.gui.forms import (
    EXPECTED_ERRORS,
    address_details,
    all_coins_with_api,
    check_sources,
    describe_ethereum_transaction,
    describe_transaction,
    extract_txid,
    parse_address,
    parse_amount,
    parse_ether_amount,
    parse_gwei_field,
    parse_nodes,
    parse_rpc_nodes,
    parse_thresholds,
)
from multicrypto.network import broadcast_transaction
from multicrypto.wallet import CHANGE_CHAIN, WalletAddress

ID_ROLE = Qt.ItemDataRole.UserRole
SOURCE_COLUMNS = ['Address', 'Account', 'Address type', 'Path', 'Label']
UTXO_SOURCES_TEXT = 'From (one or more addresses with the same address type)'
ETHEREUM_SOURCES_TEXT = 'From (one address)'
P2P_NODES_PLACEHOLDER = 'optional, host[:port] separated with commas'
RPC_NODES_PLACEHOLDER = 'optional, JSON-RPC URLs of own nodes separated with commas'
MAX_NOTE = 'The unused part of the max fee stays on the address, the fee paid is usually lower.'


class SendTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.coin = coin_box(app.visible_coins(all_coins_with_api()))
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
        self.max_button = QPushButton('Max')
        self.max_button.clicked.connect(lambda _checked=False: self.fill_max())
        self.amount_field = QWidget()
        amount_row = QHBoxLayout(self.amount_field)
        amount_row.setContentsMargins(0, 0, 0, 0)
        amount_row.addWidget(self.amount)
        amount_row.addWidget(self.max_button)
        self.amount_note = QLabel()
        self.amount_note.setWordWrap(True)
        self.priority_fee = QLineEdit()
        self.max_fee = QLineEdit()
        for field in (self.priority_fee, self.max_fee):
            field.setPlaceholderText('automatic')
        self.suggest_button = QPushButton('Suggest')
        self.suggest_button.clicked.connect(lambda _checked=False: self.suggest_fees())
        self.ethereum_fees = QWidget()
        fees_row = QHBoxLayout(self.ethereum_fees)
        fees_row.setContentsMargins(0, 0, 0, 0)
        fees_row.addWidget(QLabel('Priority fee'))
        fees_row.addWidget(self.priority_fee)
        fees_row.addWidget(QLabel('Max fee'))
        fees_row.addWidget(self.max_fee)
        fees_row.addWidget(self.suggest_button)
        self.fee = FeeRateField(app, self._source_coin)
        self.minimum = QLineEdit()
        self.maximum = QLineEdit()
        self.limit = QLineEdit()
        self.p2p = QCheckBox('Send directly to the peer-to-peer network')
        self.nodes = QLineEdit()
        self.nodes.setPlaceholderText(P2P_NODES_PLACEHOLDER)
        self.prepare_button = QPushButton('Prepare transaction...')
        self.prepare_button.clicked.connect(lambda _checked=False: self.prepare())
        self.form = QFormLayout()
        self.form.addRow('To address', self.destination)
        self.form.addRow('', self.destination_status)
        self.form.addRow('Amount', self.amount_field)
        self.form.addRow('', self.amount_note)
        self.form.addRow('Fee rate (sat/vB)', self.fee)
        self.form.addRow('Fees per gas (gwei)', self.ethereum_fees)
        advanced = QGroupBox('Advanced')
        self.advanced_form = QFormLayout(advanced)
        self.advanced_form.addRow('Minimum input (satoshis)', self.minimum)
        self.advanced_form.addRow('Maximum input (satoshis)', self.maximum)
        self.advanced_form.addRow('Limit of inputs', self.limit)
        self.advanced_form.addRow(self.p2p)
        self.advanced_form.addRow('Nodes', self.nodes)
        self.sources_label = QLabel(UTXO_SOURCES_TEXT)
        coin_form = QFormLayout()
        coin_form.addRow('Coin', self.coin)
        layout = QVBoxLayout(self)
        layout.addLayout(coin_form)
        layout.addWidget(self.sources_label)
        layout.addWidget(self.sources)
        layout.addLayout(self.form)
        layout.addWidget(advanced)
        layout.addWidget(self.prepare_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.destination.textChanged.connect(self._validate_destination)
        self.sources.itemSelectionChanged.connect(self._validate_destination)
        self._update_mode()

    def refresh(self):
        self._update_mode()
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
        set_coins(self.coin, self.app.visible_coins(all_coins_with_api()))

    def _update_mode(self):
        """Ethereum transactions have one source address and fees per gas in gwei."""
        ethereum = is_ethereum(self.coin.currentText())
        self.sources.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
            if ethereum
            else QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.sources_label.setText(ETHEREUM_SOURCES_TEXT if ethereum else UTXO_SOURCES_TEXT)
        self.max_button.setVisible(ethereum)
        self.form.setRowVisible(self.amount_note, ethereum and bool(self.amount_note.text()))
        self.form.setRowVisible(self.fee, not ethereum)
        self.form.setRowVisible(self.ethereum_fees, ethereum)
        for widget in (self.minimum, self.maximum, self.limit, self.p2p):
            self.advanced_form.setRowVisible(widget, not ethereum)
        self.nodes.setPlaceholderText(RPC_NODES_PLACEHOLDER if ethereum else P2P_NODES_PLACEHOLDER)

    def clear(self):
        self.sources.setRowCount(0)
        self.destination.clear()
        self.amount.clear()
        self.amount_note.clear()
        self.priority_fee.clear()
        self.max_fee.clear()

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

    def _single_source(self) -> WalletAddress:
        addresses = self._selected_addresses()
        if len(addresses) != 1:
            raise ValueError('Select one source address')
        return addresses[0]

    def _ethereum_rpc(self, coin_symbol: str):
        """Client of the nodes entered in the form (public nodes when empty) and its
        description."""
        nodes = parse_rpc_nodes(self.nodes.text())
        rpc = ethereum_api.get_rpc(ethereum_coins[coin_symbol], nodes)
        return rpc, 'own node' if nodes else 'public nodes'

    def _ethereum_fees(self):
        return (
            parse_gwei_field(self.priority_fee.text(), 'Priority fee'),
            parse_gwei_field(self.max_fee.text(), 'Max fee'),
        )

    def suggest_fees(self):
        try:
            rpc, _ = self._ethereum_rpc(self.coin.currentText())
        except ValueError as error:
            self.app.show_error(error)
            return
        self.suggest_button.setEnabled(False)
        self.app.worker.run(
            lambda: ethereum_api.suggest_fees(rpc), self._show_suggestion, self._fees_failed
        )

    def _show_suggestion(self, suggestion):
        self.suggest_button.setEnabled(True)
        self.priority_fee.setText(format_gwei(suggestion.max_priority_fee_per_gas))
        self.max_fee.setText(format_gwei(suggestion.max_fee_per_gas))

    def _fees_failed(self, error):
        self.suggest_button.setEnabled(True)
        self.max_button.setEnabled(True)
        self.app.show_error(error)

    def fill_max(self):
        coin_symbol = self.coin.currentText()
        try:
            source = self._single_source()
            destination = parse_address(self.destination.text(), coin_symbol)
            priority_fee, max_fee = self._ethereum_fees()
            rpc, _ = self._ethereum_rpc(coin_symbol)
        except ValueError as error:
            self.app.show_error(error)
            return
        self.max_button.setEnabled(False)
        self.app.worker.run(
            lambda: ethereum_api.max_value(rpc, source.address, destination, priority_fee, max_fee),
            self._show_max,
            self._fees_failed,
        )

    def _show_max(self, result):
        self.max_button.setEnabled(True)
        self.amount.setText(format_ether(result.value))
        self.priority_fee.setText(format_gwei(result.max_priority_fee_per_gas))
        self.max_fee.setText(format_gwei(result.max_fee_per_gas))
        self.amount_note.setText(MAX_NOTE)
        self.form.setRowVisible(self.amount_note, True)

    def prepare(self):
        coin_symbol = self.coin.currentText()
        if is_ethereum(coin_symbol):
            self._prepare_ethereum(coin_symbol)
            return
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

    def _prepare_ethereum(self, coin_symbol: str):
        try:
            source = self._single_source()
            destination = parse_address(self.destination.text(), coin_symbol)
            value = parse_ether_amount(self.amount.text())
            priority_fee, max_fee = self._ethereum_fees()
            rpc, target = self._ethereum_rpc(coin_symbol)
        except ValueError as error:
            self.app.show_error(error)
            return
        coin = ethereum_coins[coin_symbol]
        private_key = self.app.wallet.private_key(source)
        self.prepare_button.setEnabled(False)
        self.app.worker.run(
            lambda: ethereum_api.prepare_transfer(
                coin,
                rpc,
                private_key,
                destination,
                value,
                max_priority_fee_per_gas=priority_fee,
                max_fee_per_gas=max_fee,
            ),
            lambda prepared: self._confirm_ethereum(rpc, coin_symbol, prepared, target),
            self._failed,
        )

    def _confirm_ethereum(self, rpc, coin_symbol: str, prepared, target: str):
        self.prepare_button.setEnabled(True)
        rows = describe_ethereum_transaction(prepared, coin_symbol, target)
        if not confirm(self, 'Confirm transaction', rows, 'Send'):
            return
        self.prepare_button.setEnabled(False)
        self.app.worker.run(
            lambda: ethereum_api.broadcast_transaction(rpc, prepared), self._sent, self._failed
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
        self.amount_note.clear()
        self.form.setRowVisible(self.amount_note, False)
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
