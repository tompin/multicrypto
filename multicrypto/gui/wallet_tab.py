"""Wallet tab: HD account groups with their addresses and imported private keys."""

from typing import Callable, Dict, List, Optional, Set, Tuple, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from multicrypto.address import translate_private_key
from multicrypto.bip32 import HARDENED
from multicrypto.coins import P2TR, P2WPKH, coins, get_address_types
from multicrypto.gui.dialogs import (
    SecretDialog,
    ask_password,
    coin_box,
    monospace_label,
    password_field,
    secret_line,
)
from multicrypto.gui.forms import (
    ADDRESS_TYPE_NAMES,
    EXPECTED_ERRORS,
    address_type_name,
    coins_with_slip44,
    fetch_balances,
    format_amount,
)
from multicrypto.gui.qr import QrDialog, qr_image
from multicrypto.wallet import (
    AccountGroup,
    WalletAddress,
    account_path,
    check_entry,
    group_address_types,
)

ITEM_ROLE = Qt.ItemDataRole.UserRole
ACCOUNT, ADDRESS, GROUP, ACCOUNT_GROUP = 'account', 'address', 'group', 'account_group'


def group_id(coin_symbol: str, number: int) -> str:
    return f'{coin_symbol}/{number}'


def parse_group_id(item_id: str) -> Tuple[str, int]:
    coin_symbol, number = item_id.rsplit('/', 1)
    return coin_symbol, int(number)


class _CoinTypeForm(QDialog):
    """Dialog with coin and address type fields, the address types depend on the coin."""

    def __init__(self, parent, title: str, symbols, submit):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.submit = submit
        self.label = QLineEdit()
        self.coin = QComboBox()
        self.coin.addItems(symbols)
        self.coin.setCurrentText('BTC')
        self.address_type = QComboBox()
        self.form = QFormLayout(self)
        self.form.addRow('Label', self.label)
        self.form.addRow('Coin', self.coin)
        self.form.addRow('Address type', self.address_type)
        self.coin.currentTextChanged.connect(self._coin_changed)
        self.address_type.currentTextChanged.connect(self.update_preview)

    def add_buttons(self):
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)
        self._coin_changed()

    def _coin_changed(self):
        current = self.address_type.currentText()
        address_types = get_address_types(coins[self.coin.currentText()])
        self.address_type.blockSignals(True)
        self.address_type.clear()
        self.address_type.addItems(address_types)
        if current in address_types:
            self.address_type.setCurrentText(current)
        self.address_type.blockSignals(False)
        self.update_preview()

    def update_preview(self):
        raise NotImplementedError

    def submitted_values(self):
        raise NotImplementedError

    def accept(self):
        try:
            self.submit(*self.submitted_values())
        except EXPECTED_ERRORS as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()


class NewAccountGroupDialog(QDialog):
    """Dialog of the new account group: the accounts of all address types of the coin."""

    def __init__(self, parent, wallet, submit, symbols: Optional[List[str]] = None):
        super().__init__(parent)
        self.setWindowTitle('New account')
        self.wallet = wallet
        self.submit = submit
        self.label = QLineEdit()
        self.coin = coin_box(coins_with_slip44() if symbols is None else symbols)
        self.account = QSpinBox()
        self.account.setRange(0, HARDENED - 1)
        self.paths = QLabel()
        form = QFormLayout(self)
        form.addRow('Label', self.label)
        form.addRow('Coin', self.coin)
        form.addRow('Account number', self.account)
        form.addRow('Paths', self.paths)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.coin.currentTextChanged.connect(self._coin_changed)
        self.account.valueChanged.connect(self._show_paths)
        self._coin_changed()

    def _coin_changed(self):
        self.account.setValue(self.wallet.next_group_number(self.coin.currentText()))
        self._show_paths()

    def _show_paths(self):
        coin_symbol, number = self.coin.currentText(), self.account.value()
        self.paths.setText(
            '\n'.join(
                f'{ADDRESS_TYPE_NAMES[address_type]}: '
                f'{account_path(coin_symbol, address_type, number)}'
                for address_type in group_address_types(coin_symbol)
            )
        )

    def accept(self):
        try:
            self.submit(self.label.text().strip(), self.coin.currentText(), self.account.value())
        except EXPECTED_ERRORS as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()


class _AccountTypeForm(QDialog):
    """Dialog with the account group and its address type. The address type of the account or
    of the group (Native SegWit when the coin has it) is selected at the start."""

    def __init__(self, parent, title: str, wallet, groups):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.wallet = wallet
        self.group = QComboBox()
        for account_group in groups:
            self.group.addItem(
                f'{account_group.label} ({account_group.coin})',
                group_id(account_group.coin, account_group.number),
            )
        self.address_type = QComboBox()
        self.form = QFormLayout(self)
        self.form.addRow('Account', self.group)
        self.form.addRow('Address type', self.address_type)

    def select(self, account_id: Optional[str], group: Optional[Tuple[str, int]]):
        """Select the account or the group, called when the widgets of the dialog are created."""
        if account_id is not None:
            account = self.wallet.get_account(account_id)
            group = (account.coin, account.account)
        if group is not None:
            self.group.setCurrentIndex(max(0, self.group.findData(group_id(*group))))
        self._group_changed(account_id)
        self.group.currentIndexChanged.connect(lambda _index: self._group_changed())
        self.address_type.currentIndexChanged.connect(lambda _index: self.account_changed())

    def _group_changed(self, account_id: Optional[str] = None):
        self.address_type.blockSignals(True)
        self.address_type.clear()
        if self.group.count():
            accounts = self.wallet.get_group(*parse_group_id(self.group.currentData())).accounts
            for account in accounts:
                self.address_type.addItem(address_type_name(account.address_type), account.id)
            index = self.address_type.findData(account_id)
            if index < 0:
                native = [account.id for account in accounts if account.address_type == P2WPKH]
                index = self.address_type.findData(native[0] if native else accounts[0].id)
            self.address_type.setCurrentIndex(index)
        self.address_type.blockSignals(False)
        self.account_changed()

    def account_changed(self):
        raise NotImplementedError


class NewAddressDialog(_AccountTypeForm):
    """Dialog of the new receiving address: the account group, its address type and the label."""

    def __init__(
        self,
        parent,
        wallet,
        submit,
        account_id: Optional[str] = None,
        group: Optional[Tuple[str, int]] = None,
        groups=None,
    ):
        super().__init__(
            parent, 'New address', wallet, wallet.account_groups() if groups is None else groups
        )
        self.submit = submit
        self.label = QLineEdit()
        self.label.setPlaceholderText('optional')
        self.path = QLabel()
        self.address = monospace_label('')
        self.address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.form.addRow('Label', self.label)
        self.form.addRow('Path', self.path)
        self.form.addRow('Address', self.address)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)
        self.select(account_id, group)

    def account_changed(self):
        account_id = self.address_type.currentData()
        if account_id is None:
            self.path.setText('')
            self.address.setText('')
            return
        address = self.wallet.next_receiving_address(account_id)
        self.path.setText(address.path)
        self.address.setText(address.address)

    def accept(self):
        try:
            self.submit(self.address_type.currentData(), self.label.text().strip())
        except EXPECTED_ERRORS as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()


class ReceiveDialog(_AccountTypeForm):
    """The latest receiving address of the account with its QR code, a new address is added on
    demand (and when the account has no receiving address)."""

    def __init__(
        self,
        parent,
        wallet,
        add_address: Callable[[str, str], WalletAddress],
        balances: Dict[str, Union[int, str]],
        account_id: Optional[str] = None,
        group: Optional[Tuple[str, int]] = None,
        groups=None,
    ):
        super().__init__(
            parent, 'Receive', wallet, wallet.account_groups() if groups is None else groups
        )
        self.add_address = add_address
        self.balances = balances
        self.current: Optional[WalletAddress] = None
        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.address = monospace_label('')
        self.address.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.address.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.path = QLabel()
        self.label = QLabel()
        self.hint = QLabel(
            'This address has already received funds. Use New address to receive the next '
            'payment on a fresh address, it keeps your payments more private.'
        )
        self.hint.setWordWrap(True)
        self.hint.hide()
        self.form.addRow(self.image)
        self.form.addRow(self.address)
        self.form.addRow('Path', self.path)
        self.form.addRow('Label', self.label)
        self.form.addRow(self.hint)
        copy_button = QPushButton('Copy address')
        copy_button.clicked.connect(lambda _checked=False: self.copy())
        new_button = QPushButton('New address')
        new_button.clicked.connect(lambda _checked=False: self.new_address())
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(new_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)
        self.select(account_id, group)

    def account_changed(self):
        account_id = self.address_type.currentData()
        if account_id is None:
            self._show(None)
            return
        address = self.wallet.last_receiving_address(account_id)
        if address is None:
            self.new_address()
        else:
            self._show(address)

    def new_address(self):
        try:
            address = self.add_address(self.address_type.currentData(), '')
        except EXPECTED_ERRORS as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        self._show(address)

    def copy(self):
        if self.current is not None:
            QApplication.clipboard().setText(self.current.address)

    def _show(self, address: Optional[WalletAddress]):
        self.current = address
        if address is None:
            self.image.clear()
        else:
            self.image.setPixmap(QPixmap.fromImage(qr_image(address.address, scale=5)))
        self.address.setText(address.address if address else '')
        self.path.setText(address.path if address else '')
        self.label.setText(address.label if address else '')
        balance = self.balances.get(address.id) if address else None
        self.hint.setVisible(isinstance(balance, int) and balance > 0)


class ImportWifDialog(_CoinTypeForm):
    def __init__(self, parent, submit, symbols: Optional[List[str]] = None):
        super().__init__(parent, 'Import private key', symbols or sorted(coins), submit)
        self.wif = password_field()
        self.address = QLabel()
        self.form.addRow('Private key (WIF)', self.wif)
        self.form.addRow('Address', self.address)
        self.wif.textChanged.connect(self.update_preview)
        self.add_buttons()

    def update_preview(self):
        wif = self.wif.text().strip()
        if not wif:
            self.address.setText('')
            return
        try:
            address = check_entry(self.coin.currentText(), wif, self.address_type.currentText())
        except ValueError as error:
            self.address.setText(f'({error})')
        else:
            self.address.setText(address)

    def submitted_values(self):
        label = self.label.text().strip()
        if not label:
            raise ValueError('Enter the label')
        return (
            label,
            self.coin.currentText(),
            self.wif.text().strip(),
            self.address_type.currentText(),
        )


class TranslateKeyDialog(_CoinTypeForm):
    """Add the private key (WIF of any coin) to the wallet as the key of another coin."""

    def __init__(
        self,
        parent,
        title: str,
        wif: str,
        label: str,
        submit,
        coin_symbol='BTC',
        symbols: Optional[List[str]] = None,
    ):
        super().__init__(parent, title, symbols or sorted(coins), submit)
        self.source_wif = wif
        self.base_label = label
        self.address = QLabel()
        self.form.addRow('Address', self.address)
        self.coin.setCurrentText(coin_symbol)
        self.add_buttons()

    def _translated_wif(self) -> str:
        prefix = coins[self.coin.currentText()]['secret_prefix_bytes']
        return translate_private_key(self.source_wif, prefix)

    def update_preview(self):
        coin_symbol = self.coin.currentText()
        if not self.label.isModified():
            self.label.setText(f'{self.base_label} ({coin_symbol})')
        try:
            address = check_entry(
                coin_symbol, self._translated_wif(), self.address_type.currentText()
            )
        except ValueError as error:
            self.address.setText(f'({error})')
        else:
            self.address.setText(address)

    def submitted_values(self):
        label = self.label.text().strip()
        if not label:
            raise ValueError('Enter the label')
        return (
            label,
            self.coin.currentText(),
            self._translated_wif(),
            self.address_type.currentText(),
        )


class WalletTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.balances: Dict[str, Union[int, str]] = {}
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Label', 'Path', 'Address', 'Balance'])
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.expanded: Set[Tuple[str, str]] = set()
        self.tree.itemExpanded.connect(lambda item: self._expanded_changed(item, True))
        self.tree.itemCollapsed.connect(lambda item: self._expanded_changed(item, False))
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_menu)
        buttons = QHBoxLayout()
        for text, slot in (
            ('New account...', self.new_account),
            ('New address...', self.new_address),
            ('Receive...', self.receive),
            ('Import WIF...', self.import_wif),
            ('Copy address', self.copy_address),
            ('Show QR...', self.show_qr),
            ('Show key...', self.show_key),
            ('Rename...', self.rename),
            ('Remove...', self.remove),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, slot=slot: slot())
            buttons.addWidget(button)
        buttons.addStretch()
        self.refresh_button = QPushButton('Refresh balances')
        self.refresh_button.clicked.connect(lambda _checked=False: self.refresh_balances())
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.addLayout(buttons)

    def _visible_groups(self) -> List[AccountGroup]:
        visible = set(self.app.visible_coins(coins))
        return [group for group in self.app.wallet.account_groups() if group.coin in visible]

    def _expanded_changed(self, item: QTreeWidgetItem, expanded: bool):
        """Remember the expanded groups, they are collapsed at the start."""
        if item.parent() is None:
            key = tuple(item.data(0, ITEM_ROLE))
            if expanded:
                self.expanded.add(key)
            else:
                self.expanded.discard(key)

    def refresh(self):
        selected = self._selected()
        self.tree.clear()
        wallet = self.app.wallet
        visible = set(self.app.visible_coins(coins))
        for group in self._visible_groups():
            accounts = [(account, wallet.account_addresses(account)) for account in group.accounts]
            group_addresses = [address for _, addresses in accounts for address in addresses]
            group_item = QTreeWidgetItem(
                self.tree, [group.label, '', group.coin, self._sum_text(group_addresses)]
            )
            group_item.setData(0, ITEM_ROLE, (ACCOUNT_GROUP, group_id(group.coin, group.number)))
            self._align_balance(group_item)
            for account, addresses in accounts:
                account_item = QTreeWidgetItem(
                    group_item,
                    [
                        ADDRESS_TYPE_NAMES[account.address_type],
                        account.path,
                        '',
                        self._sum_text(addresses),
                    ],
                )
                account_item.setData(0, ITEM_ROLE, (ACCOUNT, account.id))
                self._align_balance(account_item)
                for address in addresses:
                    self._add_address_item(
                        account_item, address, f'{address.chain}/{address.index}'
                    )
                account_item.setExpanded(True)
            self._restore_expanded(group_item)
        imported = [address for address in wallet.imported_addresses() if address.coin in visible]
        if imported:
            group = QTreeWidgetItem(self.tree, ['Imported keys (not in mnemonic backup)'])
            group.setData(0, ITEM_ROLE, (GROUP, ''))
            for address in imported:
                self._add_address_item(group, address, f'{address.coin} {address.address_type}')
            self._restore_expanded(group)
        if selected:
            self._select(selected)

    def _restore_expanded(self, item: QTreeWidgetItem):
        item.setExpanded(tuple(item.data(0, ITEM_ROLE)) in self.expanded)

    def _add_address_item(self, parent: QTreeWidgetItem, address: WalletAddress, path: str):
        item = QTreeWidgetItem(
            parent, [address.label, path, address.address, self._balance_text(address.id)]
        )
        item.setData(0, ITEM_ROLE, (ADDRESS, address.id))
        self._align_balance(item)

    @staticmethod
    def _align_balance(item: QTreeWidgetItem):
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _balance_text(self, address_id: str) -> str:
        balance = self.balances.get(address_id)
        if balance is None:
            return ''
        return format_amount(balance) if isinstance(balance, int) else balance

    def _sum_text(self, addresses: List[WalletAddress]) -> str:
        """Sum of the known balances of the addresses (balances not fetched are skipped)."""
        balances = [self.balances.get(address.id) for address in addresses]
        known = [balance for balance in balances if isinstance(balance, int)]
        return format_amount(sum(known)) if known else ''

    def clear(self):
        self.tree.clear()
        self.balances.clear()
        self.expanded.clear()

    def _selected(self):
        item = self.tree.currentItem()
        return tuple(item.data(0, ITEM_ROLE)) if item else None

    def _select(self, selected):
        for item in self._items():
            if tuple(item.data(0, ITEM_ROLE)) == tuple(selected):
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return

    def _items(self, parent: Optional[QTreeWidgetItem] = None):
        parent = self.tree.invisibleRootItem() if parent is None else parent
        for index in range(parent.childCount()):
            child = parent.child(index)
            yield child
            yield from self._items(child)

    def selected_address(self) -> Optional[WalletAddress]:
        selected = self._selected()
        if not selected or selected[0] != ADDRESS:
            QMessageBox.information(self, 'Wallet', 'Select an address first')
            return None
        return self.app.wallet.get_address(selected[1])

    def _selected_account_id(self) -> Optional[str]:
        selected = self._selected()
        if selected and selected[0] == ACCOUNT:
            return selected[1]
        if selected and selected[0] == ADDRESS:
            return self.app.wallet.get_address(selected[1]).account_id
        return None

    def _modify(self, change):
        try:
            return self.app.modify_wallet(change)
        except EXPECTED_ERRORS as error:
            self.app.show_error(error)
            return None

    def new_account(self):
        NewAccountGroupDialog(
            self, self.app.wallet, self.add_group, self.app.visible_coins(coins_with_slip44())
        ).exec()

    def add_group(self, label: str, coin_symbol: str, number: int):
        group = self.app.modify_wallet(
            lambda wallet: wallet.add_account_group(label, coin_symbol, number)
        )
        self._select((ACCOUNT_GROUP, group_id(group.coin, group.number)))

    def _dialog_selection(self, title: str):
        """Groups, account and group selected in the tree for the dialog of the account and its
        address type, None when the wallet has no visible account."""
        groups = self._visible_groups()
        if not groups:
            QMessageBox.information(self, title, 'Add an account first')
            return None
        selected = self._selected()
        group = None
        if selected and selected[0] == ACCOUNT_GROUP:
            group = parse_group_id(selected[1])
        return groups, self._selected_account_id(), group

    def new_address(self):
        selection = self._dialog_selection('New address')
        if selection:
            groups, account_id, group = selection
            NewAddressDialog(
                self, self.app.wallet, self.add_address, account_id, group, groups
            ).exec()

    def receive(self):
        selection = self._dialog_selection('Receive')
        if selection:
            groups, account_id, group = selection
            ReceiveDialog(
                self, self.app.wallet, self.add_address, self.balances, account_id, group, groups
            ).exec()

    def add_address(self, account_id: str, label: str) -> WalletAddress:
        address = self.app.modify_wallet(lambda wallet: wallet.new_address(account_id, label))
        self._select((ADDRESS, address.id))
        return address

    def import_wif(self):
        def submit(label, coin, wif, address_type):
            self.app.modify_wallet(lambda wallet: wallet.add_wif(label, coin, wif, address_type))

        ImportWifDialog(self, submit, self.app.visible_coins(sorted(coins))).exec()

    def translate_key(self, address: WalletAddress):
        def submit(label, coin, wif, address_type):
            self.app.modify_wallet(lambda wallet: wallet.add_wif(label, coin, wif, address_type))

        TranslateKeyDialog(
            self,
            'Translate to another coin',
            self.app.wallet.private_key_wif(address),
            address.label,
            submit,
            symbols=self.app.visible_coins(sorted(coins)),
        ).exec()

    def copy_address(self):
        address = self.selected_address()
        if address:
            QApplication.clipboard().setText(address.address)

    def show_qr(self):
        address = self.selected_address()
        if address:
            QrDialog(self, address).exec()

    def show_key(self):
        address = self.selected_address()
        if not address:
            return
        password = ask_password(
            self,
            'Show private key',
            f'Enter the wallet password to show the key of "{address.label}"',
        )
        if password is None:
            return
        self.app.worker.run(
            lambda: self.app.wallet_file.verify_password(password),
            lambda correct: self._show_key(address, correct),
            self.app.show_error,
        )

    def _show_key(self, address: WalletAddress, correct: bool):
        if not correct:
            QMessageBox.warning(self, 'Show private key', 'Wrong password')
            return
        if self.app.wallet is None:
            return
        SecretDialog(
            self,
            f'Private key of "{address.label}"',
            f'{address.coin} {address.address_type} {address.address}',
            secret_line(self.app.wallet.private_key_wif(address)),
        ).exec()

    def rename(self):
        selected = self._selected()
        if not selected or selected[0] == GROUP:
            QMessageBox.information(self, 'Rename', 'Select an account or an address first')
            return
        kind, item_id = selected
        if kind == ACCOUNT:
            QMessageBox.information(self, 'Rename', 'Rename the account group')
            return
        label, ok = QInputDialog.getText(
            self, 'Rename', 'Label', QLineEdit.EchoMode.Normal, self.tree.currentItem().text(0)
        )
        if not (ok and label.strip()):
            return
        if kind == ACCOUNT_GROUP:
            self._modify(
                lambda wallet: wallet.rename_group(*parse_group_id(item_id), label.strip())
            )
        else:
            self._modify(lambda wallet: wallet.rename(item_id, label.strip()))

    def remove(self):
        selected = self._selected()
        if not selected or selected[0] == GROUP:
            QMessageBox.information(self, 'Remove', 'Select an account or an address first')
            return
        kind, item_id = selected
        label = self.tree.currentItem().text(0)
        if kind == ACCOUNT_GROUP:
            warning = (
                'The account group and its addresses will be removed from the list. '
                'The mnemonic still restores them.'
            )
        elif kind == ACCOUNT:
            warning = (
                'The account and its addresses will be removed from the list. '
                'The mnemonic still restores them.'
            )
        elif self.app.wallet.get_address(item_id).account_id:
            warning = 'The address will be removed from the list. The mnemonic still restores it.'
        else:
            warning = (
                'The imported private key will be permanently deleted from the wallet file. '
                'It is not in the mnemonic backup, make sure you have its backup.'
            )
        answer = QMessageBox.question(
            self,
            'Remove',
            f'Remove "{label}"?\n\n{warning}',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if kind == ACCOUNT_GROUP:
            self._modify(lambda wallet: wallet.remove_group(*parse_group_id(item_id)))
        else:
            self._modify(lambda wallet: wallet.remove(item_id))

    def refresh_balances(self):
        addresses = self.app.wallet.addresses()
        self.refresh_button.setEnabled(False)
        self.app.worker.run(lambda: fetch_balances(addresses), self._show_balances, self._failed)

    def _show_balances(self, balances):
        self.refresh_button.setEnabled(True)
        if self.app.wallet is None:
            return
        self.balances = balances
        self.refresh()

    def _failed(self, error):
        self.refresh_button.setEnabled(True)
        self.app.show_error(error)

    def _account_actions(self, account) -> Dict[str, Callable[[], None]]:
        actions = {'New address...': self.new_address}
        if coins[account.coin].get('apis'):
            actions['Scan for used addresses'] = lambda: self.app.background_scan.start_account(
                account
            )
        return actions

    def _group_actions(self, coin_symbol: str) -> Dict[str, Callable[[], None]]:
        if not coins[coin_symbol].get('apis'):
            return {}
        return {'Scan for used addresses': lambda: self.app.background_scan.start_coin(coin_symbol)}

    def _show_actions(self, position, item: QTreeWidgetItem, actions):
        if not actions:
            return
        self.tree.setCurrentItem(item)
        menu = QMenu(self)
        for text, action in actions.items():
            menu.addAction(text, action)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _show_menu(self, position):
        item = self.tree.itemAt(position)
        if not item:
            return
        kind, item_id = item.data(0, ITEM_ROLE)
        if kind == ACCOUNT_GROUP:
            self._show_actions(position, item, self._group_actions(parse_group_id(item_id)[0]))
            return
        if kind == ACCOUNT:
            account = self.app.wallet.get_account(item_id)
            self._show_actions(position, item, self._account_actions(account))
            return
        if kind != ADDRESS:
            return
        self.tree.setCurrentItem(item)
        address = self.app.wallet.get_address(item_id)
        menu = QMenu(self)
        menu.addAction('Copy address', self.copy_address)
        menu.addAction('Show QR...', self.show_qr)
        menu.addAction('Check UTXO', lambda: self.app.balance_tab.check_address(address))
        menu.addAction('Send from this address', lambda: self.app.send_tab.select_source(address))
        if coins[address.coin].get('apis'):
            menu.addAction('Sweep this address', lambda: self.app.sweep_tab.select_source(address))
        sign_action = menu.addAction(
            'Sign message', lambda: self.app.sign_tab.select_address(address)
        )
        sign_action.setEnabled(address.address_type != P2TR)
        menu.addAction('Translate to another coin...', lambda: self.translate_key(address))
        menu.addAction('Rename...', self.rename)
        menu.addAction('Show key...', self.show_key)
        menu.exec(self.tree.viewport().mapToGlobal(position))
