"""Wallet tab: HD accounts with their addresses and imported private keys."""

from typing import Dict, Optional, Union

from PySide6.QtCore import Qt
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
from multicrypto.coins import P2TR, coins, get_address_types
from multicrypto.gui.dialogs import SecretDialog, ask_password, password_field, secret_line
from multicrypto.gui.forms import EXPECTED_ERRORS, coins_with_slip44, fetch_balances, format_amount
from multicrypto.gui.qr import QrDialog
from multicrypto.wallet import WalletAddress, account_path, check_entry

ITEM_ROLE = Qt.ItemDataRole.UserRole
ACCOUNT, ADDRESS, GROUP = 'account', 'address', 'group'


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


class NewAccountDialog(_CoinTypeForm):
    def __init__(self, parent, wallet, submit):
        super().__init__(parent, 'New account', coins_with_slip44(), submit)
        self.wallet = wallet
        self.account = QSpinBox()
        self.account.setRange(0, HARDENED - 1)
        self.path = QLabel()
        self.form.addRow('Account number', self.account)
        self.form.addRow('Path', self.path)
        self.account.valueChanged.connect(self._show_path)
        self.add_buttons()

    def update_preview(self):
        coin, address_type = self.coin.currentText(), self.address_type.currentText()
        if address_type:
            self.account.setValue(self.wallet.next_account_number(coin, address_type))
            self._show_path()

    def _show_path(self):
        self.path.setText(
            account_path(
                self.coin.currentText(), self.address_type.currentText(), self.account.value()
            )
        )

    def submitted_values(self):
        coin, address_type = self.coin.currentText(), self.address_type.currentText()
        label = self.label.text().strip() or f'{coin} {address_type} #{self.account.value()}'
        return label, coin, address_type, self.account.value()


class ImportWifDialog(_CoinTypeForm):
    def __init__(self, parent, submit):
        super().__init__(parent, 'Import private key', sorted(coins), submit)
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

    def __init__(self, parent, title: str, wif: str, label: str, submit, coin_symbol='BTC'):
        super().__init__(parent, title, sorted(coins), submit)
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
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_menu)
        buttons = QHBoxLayout()
        for text, slot in (
            ('New account...', self.new_account),
            ('New address...', self.new_address),
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

    def refresh(self):
        selected = self._selected()
        self.tree.clear()
        wallet = self.app.wallet
        for account in wallet.accounts:
            account_item = QTreeWidgetItem(
                self.tree,
                [account.label, account.path, f'{account.coin} {account.address_type}', ''],
            )
            account_item.setData(0, ITEM_ROLE, (ACCOUNT, account.id))
            for address in wallet.account_addresses(account):
                self._add_address_item(account_item, address, f'{address.chain}/{address.index}')
        if wallet.imported:
            group = QTreeWidgetItem(self.tree, ['Imported keys (not in mnemonic backup)'])
            group.setData(0, ITEM_ROLE, (GROUP, ''))
            for address in wallet.imported_addresses():
                self._add_address_item(group, address, f'{address.coin} {address.address_type}')
        self.tree.expandAll()
        if selected:
            self._select(selected)

    def _add_address_item(self, parent: QTreeWidgetItem, address: WalletAddress, path: str):
        item = QTreeWidgetItem(
            parent, [address.label, path, address.address, self._balance_text(address.id)]
        )
        item.setData(0, ITEM_ROLE, (ADDRESS, address.id))
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _balance_text(self, address_id: str) -> str:
        balance = self.balances.get(address_id)
        if balance is None:
            return ''
        return format_amount(balance) if isinstance(balance, int) else balance

    def clear(self):
        self.tree.clear()
        self.balances.clear()

    def _selected(self):
        item = self.tree.currentItem()
        return tuple(item.data(0, ITEM_ROLE)) if item else None

    def _select(self, selected):
        for item in self._items():
            if tuple(item.data(0, ITEM_ROLE)) == tuple(selected):
                self.tree.setCurrentItem(item)
                return

    def _items(self):
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            yield top
            for child_index in range(top.childCount()):
                yield top.child(child_index)

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
        if len(self.app.wallet.accounts) == 1:
            return self.app.wallet.accounts[0].id
        return None

    def _modify(self, change):
        try:
            return self.app.modify_wallet(change)
        except EXPECTED_ERRORS as error:
            self.app.show_error(error)
            return None

    def new_account(self):
        def submit(label, coin, address_type, account):
            self.app.modify_wallet(
                lambda wallet: wallet.add_account(label, coin, address_type, account)
            )

        NewAccountDialog(self, self.app.wallet, submit).exec()

    def new_address(self):
        account_id = self._selected_account_id()
        if account_id is None:
            QMessageBox.information(self, 'New address', 'Select an account first')
            return
        label, ok = QInputDialog.getText(self, 'New address', 'Label (optional)')
        if ok:
            address = self._modify(lambda wallet: wallet.new_address(account_id, label.strip()))
            if address:
                self._select((ADDRESS, address.id))

    def import_wif(self):
        def submit(label, coin, wif, address_type):
            self.app.modify_wallet(lambda wallet: wallet.add_wif(label, coin, wif, address_type))

        ImportWifDialog(self, submit).exec()

    def translate_key(self, address: WalletAddress):
        def submit(label, coin, wif, address_type):
            self.app.modify_wallet(lambda wallet: wallet.add_wif(label, coin, wif, address_type))

        TranslateKeyDialog(
            self,
            'Translate to another coin',
            self.app.wallet.private_key_wif(address),
            address.label,
            submit,
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
        label, ok = QInputDialog.getText(
            self, 'Rename', 'Label', QLineEdit.EchoMode.Normal, self.tree.currentItem().text(0)
        )
        if ok and label.strip():
            self._modify(lambda wallet: wallet.rename(selected[1], label.strip()))

    def remove(self):
        selected = self._selected()
        if not selected or selected[0] == GROUP:
            QMessageBox.information(self, 'Remove', 'Select an account or an address first')
            return
        kind, item_id = selected
        label = self.tree.currentItem().text(0)
        if kind == ACCOUNT:
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
        if answer == QMessageBox.StandardButton.Yes:
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

    def _show_menu(self, position):
        item = self.tree.itemAt(position)
        if not item or item.data(0, ITEM_ROLE)[0] != ADDRESS:
            return
        self.tree.setCurrentItem(item)
        address = self.app.wallet.get_address(item.data(0, ITEM_ROLE)[1])
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
