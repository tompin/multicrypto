import json
import threading
import time
from unittest.mock import Mock

import pyqrcode
import pytest
from nacl import pwhash
from tests import http_mock

from multicrypto.address import convert_private_key_to_coin_address, get_private_key_from_wif_format
from multicrypto.api import get_api
from multicrypto.coins import coins, ethereum_coins
from multicrypto.ethereum import GWEI, decode_transaction, parse_private_key, private_key_to_address
from multicrypto.scripts import address_to_script

pytest.importorskip('PySide6')

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QAbstractItemView, QLabel  # noqa: E402

import multicrypto.gui.balance_tab as balance_tab_module  # noqa: E402
import multicrypto.gui.send_tab as send_tab_module  # noqa: E402
from multicrypto.commands.checkaddress import EthereumAccount  # noqa: E402
from multicrypto.gui.address_picker import WalletAddressPicker  # noqa: E402
import multicrypto.gui.scan_dialog as scan_dialog_module  # noqa: E402
from multicrypto.discovery import Cancelled, DiscoveredAccount  # noqa: E402
import multicrypto.gui.sweep_tab as sweep_tab_module  # noqa: E402
import multicrypto.gui.vanity_tab as vanity_tab_module  # noqa: E402
import multicrypto.gui.wallet_tab as wallet_tab_module  # noqa: E402
from multicrypto.gui.create_wizard import RESTORE_PAGE, SHOW_PAGE, CreateWalletWizard  # noqa: E402
from multicrypto.gui.dialogs import mnemonic_grid  # noqa: E402
from multicrypto.gui.qr import QUIET_ZONE, QrDialog, qr_image  # noqa: E402
from multicrypto.gui.settings import (  # noqa: E402
    load_auto_lock,
    load_scale,
    load_show_testnets,
    save_auto_lock,
    save_scale,
    save_show_testnets,
)
from multicrypto.gui.window import SCALE_MESSAGE, MainWindow  # noqa: E402
from multicrypto.wallet import WalletAddress, WalletFile, check_entry  # noqa: E402

PASSWORD = 'correct horse battery'
PASSPHRASE = 'secret passphrase'
MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])
BTC_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'


def test_wizard_restores_mnemonic(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')
    wizard.password_page.password.setText(PASSWORD)
    wizard.password_page.confirmation.setText(PASSWORD)
    wizard.mode_page.restore.setChecked(True)
    wizard.restore_page.text.setPlainText(MNEMONIC.upper())
    wizard.passphrase_page.passphrase.setText(PASSPHRASE)
    wizard.passphrase_page.confirmation.setText(PASSPHRASE)

    assert wizard.password_page.validatePage()
    assert wizard.mode_page.nextId() == RESTORE_PAGE
    assert wizard.restore_page.status.text() == 'Mnemonic is correct'
    assert wizard.restore_page.validatePage()
    assert wizard.passphrase_page.validatePage()
    assert wizard.values() == (PASSWORD, MNEMONIC, PASSPHRASE)


def test_wizard_allows_empty_passphrase(qapp, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        'multicrypto.gui.create_wizard.QMessageBox.warning', lambda *args: warnings.append(args)
    )
    wizard = CreateWalletWizard(None, 'wallet.mcw')

    assert wizard.passphrase_page.validatePage()
    assert wizard.values()[2] == ''
    assert warnings == []


def test_wizard_confirms_generated_mnemonic(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')
    words = wizard.generated_mnemonic.split()
    for position, field in wizard.confirm_page.answers.items():
        field.setText(words[position - 1])

    assert len(words) == 24
    assert wizard.mode_page.nextId() == SHOW_PAGE
    assert wizard.confirm_page.validatePage()
    assert wizard.values()[1] == wizard.generated_mnemonic


def test_mnemonic_copy_button_copies_words(qapp):
    from PySide6.QtWidgets import QApplication

    grid = mnemonic_grid(MNEMONIC)

    grid.copy_button.click()

    assert QApplication.clipboard().text() == MNEMONIC
    assert grid.copy_button.text() == 'Copied'
    assert 'dangerous' in grid.findChild(QLabel, 'copy_warning').text()


def test_wizard_shows_copyable_mnemonic(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')

    assert 'cannot be copied' not in wizard.show_page.subTitle()
    assert wizard.show_page.findChild(QLabel, 'copy_warning') is not None


def test_restore_page_shows_mnemonic_errors(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')

    wizard.restore_page.text.setPlainText(' '.join(['abandon'] * 12))

    assert 'checksum' in wizard.restore_page.status.text()


@pytest.fixture
def window(qapp, tmp_path):
    wallet_file = WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )
    settings_path = str(tmp_path / 'gui.json')
    save_show_testnets(settings_path, True)  # the tests send testnet coins
    window = MainWindow(wallet_file, settings_path=settings_path)
    yield window
    close_window(qapp, window)


def close_window(qapp, window):
    """Stop the window and delete it, so the windows of the tests do not pile up until the end."""
    window.timer.stop()
    qapp.removeEventFilter(window)
    window.deleteLater()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def unlock(window):
    window.show_wallet(window.wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE))


def btc_account(window, address_type='p2wpkh', number=0):
    return next(
        account
        for account in window.wallet.accounts
        if (account.coin, account.address_type, account.account) == ('BTC', address_type, number)
    )


def answer_unlock_dialogs(monkeypatch, answers):
    """Answer the password dialogs in order, return the labels of the asked fields."""
    labels = []

    def ask_password(parent, title, prompt, new_password=False, label='Password'):
        labels.append(label)
        return answers.pop(0)

    monkeypatch.setattr('multicrypto.gui.window.ask_password', ask_password)
    return labels


def test_unlock_without_passphrase_asks_only_for_password(window, qapp, monkeypatch):
    window.wallet_file.create(PASSWORD, MNEMONIC, '')
    window.wallet_file.lock()
    labels = answer_unlock_dialogs(monkeypatch, [PASSWORD])

    window.unlock()
    wait_until(qapp, lambda: window.wallet is not None)

    assert labels == ['Password']
    assert window.wallet.fingerprint == '73c5da0a'


def test_unlock_asks_for_passphrase_until_correct(window, qapp, monkeypatch):
    window.wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    window.wallet_file.lock()
    labels = answer_unlock_dialogs(monkeypatch, [PASSWORD, 'wrong', PASSPHRASE])
    warnings = []
    monkeypatch.setattr(
        'multicrypto.gui.window.QMessageBox.warning', lambda *args: warnings.append(args[2])
    )

    window.unlock()
    wait_until(qapp, lambda: window.wallet is not None)

    assert labels == ['Password', 'Passphrase', 'Passphrase']
    assert len(warnings) == 1
    assert 'Check the passphrase' in warnings[0]
    assert 'unlocked' in window.status.text()


def test_cancelled_passphrase_keeps_wallet_locked(window, qapp, monkeypatch):
    window.wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    window.wallet_file.lock()
    answer_unlock_dialogs(monkeypatch, [PASSWORD, None])

    window.unlock()
    wait_until(qapp, lambda: window.worker.pending == 0)

    assert window.wallet is None
    assert not window.wallet_file.is_unlocked
    assert 'locked' in window.status.text()


def test_wallet_is_shown_when_unlocked_and_cleared_when_locked(window):
    unlock(window)
    account = btc_account(window)

    address = window.modify_wallet(lambda wallet: wallet.new_address(account.id, 'Savings'))

    tree = window.wallet_tab.tree
    assert 'unlocked' in window.status.text()
    assert window.wallet.fingerprint in window.status.text()
    assert tree.topLevelItemCount() == 8  # groups #0 of 6 coins with UTXO, ETH and TETH
    assert tree.topLevelItem(0).child(1).child(1).text(2) == address.address
    assert window.balance_tab.picker.box.count() == 5
    assert window.send_tab.sources.rowCount() == 5

    window.lock()

    assert window.wallet is None
    assert not window.wallet_file.is_unlocked
    assert tree.topLevelItemCount() == 0
    assert window.send_tab.sources.rowCount() == 0
    assert window.balance_tab.picker.box.count() == 0
    assert 'locked' in window.status.text()


def test_wallet_address_picker(window):
    unlock(window)
    picker = WalletAddressPicker()
    addresses = [address for address in window.wallet.addresses() if address.coin == 'BTC']

    picker.set_addresses(window.wallet, addresses)

    assert [picker.box.itemText(index) for index in range(picker.box.count())] == [
        address.address for address in addresses
    ]
    assert picker.current() == addresses[0]
    assert picker.details['Account'].text() == 'Bitcoin #0'
    assert picker.details['Address type'].text() == 'Taproot (p2tr)'
    assert picker.select(addresses[1].id)
    assert picker.details['Path'].text() == "m/84'/0'/0'/0/0"
    picker.set_addresses(window.wallet, addresses)
    assert picker.current() == addresses[1]
    assert not picker.select('missing')
    picker.clear()
    assert picker.current() is None
    assert picker.details['Account'].text() == ''


def test_balance_tab_filters_wallet_addresses_by_coin(window, monkeypatch):
    unlock(window)
    tab = window.balance_tab
    monkeypatch.setattr(tab, 'check', lambda: None)
    [address] = window.wallet.account_addresses(window.wallet.get_group('LTC', 0).accounts[1])

    tab.coin.setCurrentText('TBTC')

    assert {address.coin for address in tab.picker.addresses} == {'TBTC'}
    assert tab.picker.box.count() == 4
    tab.check_address(address)
    assert tab.coin.currentText() == 'LTC'
    assert tab.picker.current() == address
    assert tab.wallet_source.isChecked()


def test_testnets_are_hidden_by_default(qapp, tmp_path):
    settings_path = str(tmp_path / 'gui.json')
    wallet_file = WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )
    window = MainWindow(wallet_file, settings_path=settings_path)
    unlock(window)
    tree = window.wallet_tab.tree

    assert not window.testnets_action.isChecked()
    assert [tree.topLevelItem(index).text(2) for index in range(tree.topLevelItemCount())] == [
        'BTC',
        'DASH',
        'DOGE',
        'LTC',
        'ETH',
    ]
    assert 'TBTC' not in [
        window.send_tab.coin.itemText(i) for i in range(window.send_tab.coin.count())
    ]
    window.sweep_tab.coin.setCurrentText('LTC')

    window.set_show_testnets(True)

    assert tree.topLevelItemCount() == 8
    assert window.sweep_tab.coin.findText('TLTC') >= 0
    assert window.sweep_tab.coin.currentText() == 'LTC'
    assert load_show_testnets(settings_path)
    close_window(qapp, window)


def test_account_groups_are_collapsed_and_remember_expanding(window):
    unlock(window)
    tab = window.wallet_tab
    tree = tab.tree

    assert not any(tree.topLevelItem(index).isExpanded() for index in range(6))
    tree.topLevelItem(1).setExpanded(True)
    tab.refresh()
    assert [tree.topLevelItem(index).isExpanded() for index in range(3)] == [False, True, False]

    address = tab.add_address(btc_account(window).id, 'Exchange')

    assert tree.topLevelItem(0).isExpanded()
    assert tree.currentItem().text(2) == address.address


def test_receive_dialog_shows_last_address(window):
    unlock(window)
    tab = window.wallet_tab
    account = btc_account(window)
    [first] = window.wallet.account_addresses(account)
    tab.balances = {first.id: 1000}
    tab.tree.setCurrentItem(tab.tree.topLevelItem(0))

    dialog = wallet_tab_module.ReceiveDialog(
        tab, window.wallet, tab.add_address, tab.balances, group=('BTC', 0)
    )

    assert dialog.address_type.currentText() == 'Native SegWit (p2wpkh)'
    assert dialog.address.text() == first.address
    assert dialog.path.text() == "m/84'/0'/0'/0/0"
    assert not dialog.image.pixmap().isNull()
    assert not dialog.hint.isHidden()
    dialog.new_address()
    assert dialog.path.text() == "m/84'/0'/0'/0/1"
    assert dialog.hint.isHidden()
    assert len(btc_account(window).addresses) == 2
    dialog.copy()
    from PySide6.QtWidgets import QApplication

    assert QApplication.clipboard().text() == dialog.address.text()


def test_receive_dialog_adds_address_to_empty_account(window):
    unlock(window)
    tab = window.wallet_tab
    account = btc_account(window)
    window.modify_wallet(lambda wallet: wallet.remove(wallet.account_addresses(account)[0].id))

    dialog = wallet_tab_module.ReceiveDialog(
        tab, window.wallet, tab.add_address, tab.balances, account_id=account.id
    )

    assert dialog.path.text() == "m/84'/0'/0'/0/0"
    assert len(btc_account(window).addresses) == 1


def test_imported_keys_are_shown_in_separate_group(window):
    unlock(window)

    window.modify_wallet(lambda wallet: wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh'))

    tree = window.wallet_tab.tree
    group = tree.topLevelItem(tree.topLevelItemCount() - 1)
    assert group.text(0).startswith('Imported keys')
    assert group.child(0).text(0) == 'Old'


def test_modify_wallet_reverts_change_when_saving_fails(window, monkeypatch):
    unlock(window)
    account_id = btc_account(window).id
    monkeypatch.setattr(window.wallet_file, 'save', Mock(side_effect=OSError('disk full')))

    with pytest.raises(OSError):
        window.modify_wallet(lambda wallet: wallet.new_address(account_id, 'Savings'))

    assert len(btc_account(window).addresses) == 1


def test_wallet_is_not_locked_by_default(window):
    unlock(window)
    window.last_activity -= 24 * 60 * 60

    window.tick()

    assert window.wallet is not None
    assert window.auto_lock_seconds is None
    assert 'locks in' not in window.status.text()
    assert auto_lock_actions(window)['Never'].isChecked()


def test_wallet_is_locked_after_chosen_inactivity(window):
    unlock(window)
    auto_lock_actions(window)['15 minutes'].trigger()
    assert 'locks in 15:00' in window.status.text() or 'locks in 14:59' in window.status.text()
    window.last_activity -= 15 * 60

    window.tick()

    assert window.wallet is None
    assert load_auto_lock(window.settings_path) == 15


def test_auto_lock_from_settings_and_command_line(qapp, tmp_path):
    settings_path = str(tmp_path / 'gui.json')
    save_auto_lock(settings_path, 30)
    wallet_file = WalletFile(str(tmp_path / 'wallet.mcw'))
    saved = MainWindow(wallet_file, settings_path=settings_path)
    overridden = MainWindow(wallet_file, auto_lock_minutes=5, settings_path=settings_path)

    assert saved.auto_lock_seconds == 30 * 60
    assert auto_lock_actions(saved)['30 minutes'].isChecked()
    assert overridden.auto_lock_seconds == 5 * 60
    assert auto_lock_actions(overridden)['5 minutes'].isChecked()
    close_window(qapp, saved)
    close_window(qapp, overridden)


def test_send_tab_shows_sources_of_coin_in_table(window):
    unlock(window)
    tab = window.send_tab
    [address] = window.wallet.account_addresses(window.wallet.get_group('LTC', 0).accounts[1])

    tab.select_source(address)

    assert tab.coin.currentText() == 'LTC'
    assert tab.sources.rowCount() == 4
    assert [tab.sources.item(1, column).text() for column in range(5)] == [
        address.address,
        'Litecoin #0',
        'Native SegWit (p2wpkh)',
        "m/84'/2'/0'/0/0",
        'Address 0',
    ]
    assert tab._selected_addresses() == [address]


def test_send_tab_keeps_selected_sources(window):
    unlock(window)
    tab = window.send_tab
    first = btc_account(window)
    second = window.modify_wallet(lambda wallet: wallet.new_address(first.id))
    tab.select_source(window.wallet.account_addresses(first)[0])
    tab._select_row(2)

    tab.refresh()

    assert tab._selected_addresses() == window.wallet.account_addresses(first)[:1] + [second]


def test_send_tab_validates_destination(window):
    unlock(window)
    account = window.wallet.accounts[0]
    window.modify_wallet(lambda wallet: wallet.new_address(account.id, 'Savings'))
    window.send_tab.sources.selectRow(0)

    window.send_tab.destination.setText('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu')
    assert 'Correct BTC address' in window.send_tab.destination_status.text()

    window.send_tab.destination.setText('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyx')
    assert 'Incorrect bech32 address' in window.send_tab.destination_status.text()


def test_qr_image_draws_matrix_with_quiet_zone(qapp):
    text = 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'
    matrix = pyqrcode.create(text, error='M').code
    size = len(matrix) + 2 * QUIET_ZONE

    image = qr_image(text, scale=3)

    assert image.width() == image.height() == size * 3
    for row in range(size):
        for column in range(size):
            inside = QUIET_ZONE <= min(row, column) and max(row, column) < size - QUIET_ZONE
            dark = inside and matrix[row - QUIET_ZONE][column - QUIET_ZONE] == 1
            assert (image.pixelColor(column * 3 + 1, row * 3 + 1).lightness() < 128) == dark


def test_qr_dialog_shows_address(qapp):
    address = WalletAddress(
        'a', 'Savings', 'BTC', 'p2wpkh', 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'
    )

    dialog = QrDialog(None, address)

    assert dialog.address_label.text() == address.address
    assert 'Savings' in dialog.windowTitle()


def wait_until(qapp, condition, seconds=10):
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline
        qapp.processEvents()
        time.sleep(0.01)


def add_address(window, coin_symbol='BTC', address_type='p2wpkh'):
    accounts = [
        account
        for account in window.wallet.accounts
        if (account.coin, account.address_type) == (coin_symbol, address_type)
    ]
    if accounts:
        account = accounts[0]
    else:
        account = window.modify_wallet(
            lambda wallet: wallet.add_account('Test', coin_symbol, address_type)
        )
    return window.modify_wallet(lambda wallet: wallet.new_address(account.id))


def test_sign_and_verify_message(qapp, window):
    unlock(window)
    address = add_address(window)
    tab = window.sign_tab
    message = 'Zażółć gęślą jaźń'

    tab.select_address(address)
    tab.sign_message.setPlainText(message)
    tab.sign()
    wait_until(qapp, lambda: tab.signature.text())
    tab.verify_coin.setCurrentText('LTC')
    tab.verify_address.setText(address.address)
    tab.verify_message.setPlainText(message)
    tab.verify_signature.setText(tab.signature.text())
    tab.verify()

    assert window.tab_widget.currentWidget() is tab
    assert tab.verify_coin.currentText() == 'BTC'  # detected from the wallet address
    assert 'Signature is valid' in tab.verify_result.text()

    tab.verify_message.setPlainText('Other message')
    tab.verify()
    assert 'Signature is not valid' in tab.verify_result.text()

    tab.verify_signature.setText('abc')
    tab.verify()
    assert 'Signature is not correct base64' in tab.verify_result.text()


def test_sign_tab_shows_addresses_of_coin_without_taproot(window):
    unlock(window)
    tab = window.sign_tab
    [address] = window.wallet.account_addresses(window.wallet.get_group('LTC', 0).accounts[1])

    tab.select_address(address)

    assert tab.sign_coin.currentText() == 'LTC'
    assert tab.sign_picker.current() == address
    assert [address.address_type for address in tab.sign_picker.addresses] == [
        'p2wpkh',
        'p2sh-p2wpkh',
        'p2pkh',
    ]


def test_lock_clears_sign_tab(window):
    unlock(window)
    window.sign_tab.sign_message.setPlainText('Secret plan')
    window.sign_tab.signature.setText('signature')

    window.lock()

    assert window.sign_tab.sign_message.toPlainText() == ''
    assert window.sign_tab.signature.text() == ''
    assert window.sign_tab.sign_picker.box.count() == 0


EXTERNAL_WIF = 'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo'
EXTERNAL_ADDRESS = 'tb1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uhq9l7n'
TBTC_API = get_api(coins['TBTC']).base_url


def esplora_utxos(values):
    return [
        {'txid': f'{i:02x}' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': value}
        for i, value in enumerate(values)
    ]


def capture_sweep_dialogs(monkeypatch):
    confirmations, shown, errors = [], [], []
    monkeypatch.setattr(
        sweep_tab_module,
        'confirm',
        lambda parent, title, rows, button: confirmations.append(dict(rows)) or True,
    )
    monkeypatch.setattr(
        sweep_tab_module, 'show_lines', lambda parent, title, label, lines: shown.append(lines)
    )
    monkeypatch.setattr(
        sweep_tab_module.QMessageBox, 'critical', lambda parent, title, text: errors.append(text)
    )
    return confirmations, shown, errors


@http_mock.activate
def test_sweep_wallet_address_to_itself_in_batches(qapp, window, monkeypatch):
    unlock(window)
    address = add_address(window, 'TBTC', 'p2wpkh')
    http_mock.add(
        http_mock.GET,
        f'{TBTC_API}/address/{address.address}/utxo',
        json=esplora_utxos([100000, 100000, 100000]),
    )
    http_mock.add(http_mock.POST, f'{TBTC_API}/tx', body='tx1')
    http_mock.add(http_mock.POST, f'{TBTC_API}/tx', body='tx2')
    confirmations, shown, _ = capture_sweep_dialogs(monkeypatch)
    tab = window.sweep_tab

    tab.select_source(address)
    tab.fee.rate.setText('2')
    tab.batch_size.setText('2')
    tab.prepare()
    wait_until(qapp, lambda: shown)

    assert window.tab_widget.currentWidget() is tab
    assert shown == [['tx1', 'tx2']]
    assert confirmations[0]['From'] == confirmations[0]['To'] == address.address
    assert confirmations[0]['Transactions'] == '2'
    assert confirmations[0]['Received'].endswith(' TBTC')
    assert tab.prepare_button.isEnabled()


@http_mock.activate
def test_sweep_stops_after_failed_batch(qapp, window, monkeypatch):
    unlock(window)
    address = add_address(window, 'TBTC', 'p2wpkh')
    http_mock.add(
        http_mock.GET,
        f'{TBTC_API}/address/{address.address}/utxo',
        json=esplora_utxos([100000, 100000, 100000]),
    )
    http_mock.add(http_mock.POST, f'{TBTC_API}/tx', body='tx1')
    http_mock.add(http_mock.POST, f'{TBTC_API}/tx', body='bad-txns-inputs-missing', status=400)
    _, shown, errors = capture_sweep_dialogs(monkeypatch)
    tab = window.sweep_tab

    tab.select_source(address)
    tab.batch_size.setText('1')
    tab.fee.rate.setText('2')
    tab.prepare()
    wait_until(qapp, lambda: errors)

    assert 'Transaction rejected: bad-txns-inputs-missing' in errors[0]
    assert 'tx1' in errors[0]
    assert shown == []
    assert len([call for call in http_mock.calls if call.request.method == 'POST']) == 2


@http_mock.activate
def test_sweep_external_key_to_wallet_address(qapp, window, monkeypatch):
    unlock(window)
    address = add_address(window, 'TBTC', 'p2wpkh')
    http_mock.add(
        http_mock.GET, f'{TBTC_API}/address/{EXTERNAL_ADDRESS}/utxo', json=esplora_utxos([50000])
    )
    http_mock.add(http_mock.POST, f'{TBTC_API}/tx', body='tx1')
    confirmations, shown, _ = capture_sweep_dialogs(monkeypatch)
    tab = window.sweep_tab

    tab.key_source.setChecked(True)
    tab.coin.setCurrentText('TBTC')
    tab.address_type.setCurrentText('p2wpkh')
    tab.wif.setText(EXTERNAL_WIF)
    assert tab.key_address.text() == EXTERNAL_ADDRESS
    assert not tab.same_destination.isEnabled()
    tab.wallet_destination.setChecked(True)
    tab.destination_picker.select(address.id)
    tab.fee.rate.setText('2')
    tab.prepare()
    wait_until(qapp, lambda: shown)

    assert confirmations[0]['From'] == EXTERNAL_ADDRESS
    assert confirmations[0]['To'] == address.address
    assert shown == [['tx1']]
    assert tab.wif.text() == ''
    assert window.wallet.imported == []


def test_sweep_validates_external_key_and_destination(window):
    unlock(window)
    tab = window.sweep_tab

    tab.key_source.setChecked(True)
    tab.coin.setCurrentText('BTC')
    tab.wif.setText(EXTERNAL_WIF)
    tab.other_destination.setChecked(True)
    tab.destination.setText('tb1qerzrlxcfu24davlur5sqmgzzgsal6wusda40er')

    assert 'not in WIF format of BTC' in tab.key_address.text()
    assert 'Incorrect' in tab.destination_status.text()


def test_sweep_tab_filters_wallet_addresses_by_coin(window):
    unlock(window)
    tab = window.sweep_tab
    [address] = window.wallet.account_addresses(window.wallet.get_group('TLTC', 0).accounts[0])

    tab.coin.setCurrentText('LTC')

    assert {address.coin for address in tab.source_picker.addresses} == {'LTC'}
    assert {address.coin for address in tab.destination_picker.addresses} == {'LTC'}
    tab.select_source(address)
    assert tab.coin.currentText() == 'TLTC'
    assert tab.source_picker.current() == address
    assert tab._source_coin() == 'TLTC'


def test_lock_clears_sweep_key(window):
    unlock(window)
    window.sweep_tab.wif.setText(EXTERNAL_WIF)

    window.lock()

    assert window.sweep_tab.wif.text() == ''
    assert window.sweep_tab.source_picker.box.count() == 0


def test_show_qr_of_selected_address(window, monkeypatch):
    unlock(window)
    address = add_address(window)
    shown = []
    monkeypatch.setattr(
        wallet_tab_module.QrDialog, 'exec', lambda dialog: shown.append(dialog.address_label.text())
    )

    window.wallet_tab._select(('address', address.id))
    window.wallet_tab.show_qr()

    assert shown == [address.address]


def test_translate_key_dialog_shows_address_of_another_coin(window):
    unlock(window)
    address = add_address(window)
    wif = window.wallet.private_key_wif(address)
    submitted = []

    dialog = wallet_tab_module.TranslateKeyDialog(
        window, 'Translate', wif, 'Savings', lambda *values: submitted.append(values)
    )
    dialog.coin.setCurrentText('LTC')
    dialog.address_type.setCurrentText('p2wpkh')
    private_key, compressed = get_private_key_from_wif_format(wif)
    expected = convert_private_key_to_coin_address(private_key, coins['LTC'], compressed, 'p2wpkh')

    assert dialog.address.text() == expected
    assert dialog.label.text() == 'Savings (LTC)'
    dialog.accept()
    label, coin_symbol, ltc_wif, address_type = submitted[0]
    assert (label, coin_symbol, address_type) == ('Savings (LTC)', 'LTC', 'p2wpkh')
    assert check_entry('LTC', ltc_wif, 'p2wpkh') == expected


def test_wallet_tab_adds_translated_key(window, monkeypatch):
    unlock(window)
    address = add_address(window)

    def accept_litecoin(dialog):
        dialog.coin.setCurrentText('LTC')
        dialog.address_type.setCurrentText('p2wpkh')
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.TranslateKeyDialog, 'exec', accept_litecoin)
    window.wallet_tab.translate_key(address)

    [imported] = window.wallet.imported_addresses()
    assert (imported.label, imported.coin, imported.address_type) == (
        'Address 1 (LTC)',
        'LTC',
        'p2wpkh',
    )


def test_translate_address_tab(window):
    unlock(window)
    tab = window.translate_tab

    tab.address.setText('1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi')
    tab.address_input_coin.setCurrentText('BTC')
    tab.address_output_coin.setCurrentText('DOGE')
    tab.translate_address()
    assert tab.translated_address.text() == 'DMLko4rFfwapsw1D6cWd1hw5QSTZpJn6vU'

    tab.address.setText('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu')
    tab.translate_address()
    assert tab.translated_address.text() == ''
    assert 'need the private key' in tab.address_status.text()


def test_translate_key_tab_and_add_to_wallet(window, monkeypatch):
    unlock(window)
    tab = window.translate_tab

    tab.integer.setChecked(True)
    tab.key.setText('43265286516710475498079662292151387463063605274999989765271924584279496871562')
    tab.key_output_coin.setCurrentText('LTC')
    tab.translate_key()

    assert tab.translated_key.text() == 'T6Fv2DdAqxFBdhL8FNKEA11EmLbNkvXu8QFWJJwVi1HEGS1NSUTV'
    assert [tab.key_addresses.item(row, 1).text() for row in range(4)] == [
        'LbRcX2DSTBvbbjWmYAWMjxqEjX6YWvssUp',
        '3Png2L1DD4tqaHeu5p6USVcUuo55MmrWoR',
        'ltc1qkxmgtft32j3uxfjmseypq84xlwaglttjrr3k59',
        'ltc1pk5jxttt9wcct7sp4eg4m2gdhd49tpns2kz8wqfzt79z4amzyqkeqgrc3cz',
    ]
    monkeypatch.setattr(
        wallet_tab_module.TranslateKeyDialog, 'exec', lambda dialog: dialog.accept()
    )
    tab.add_to_wallet()
    [imported] = window.wallet.imported_addresses()
    assert (imported.coin, imported.address) == ('LTC', 'LbRcX2DSTBvbbjWmYAWMjxqEjX6YWvssUp')

    tab.key.setText('other')
    assert tab.translated_key.text() == ''
    assert not tab.add_button.isEnabled()


def test_lock_clears_translate_tab(window):
    unlock(window)
    tab = window.translate_tab
    tab.key.setText('KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu')
    tab.translate_key()

    window.lock()

    assert tab.key.text() == ''
    assert tab.translated_key.text() == ''
    assert tab.key_addresses.rowCount() == 0


def test_vanity_search_and_add_to_wallet(qapp, window):
    unlock(window)
    tab = window.vanity_tab
    tab.coin.setCurrentText('BTC')
    tab.address_type.setCurrentText('p2wpkh')
    tab.pattern.setText('bc1qq')
    tab.workers.setValue(1)
    assert 'Addresses start with bc1q' in tab.pattern_status.text()

    tab.start()
    wait_until(qapp, lambda: not tab.result_group.isHidden(), seconds=60)

    address = tab.result_address.text()
    assert address.startswith('bc1qq')
    assert check_entry('BTC', tab.result_key.text(), 'p2wpkh') == address
    assert tab.search is None
    assert tab.speed == vanity_tab_module.DEFAULT_SPEED  # not measured during the start
    tab.result_label.setText('Vanity')
    tab.add_to_wallet()
    [imported] = window.wallet.imported_addresses()
    assert (imported.label, imported.address) == ('Vanity', address)
    assert tab.result_group.isHidden()
    assert tab.result_key.text() == ''


def test_vanity_pattern_validation(window):
    unlock(window)
    tab = window.vanity_tab
    tab.coin.setCurrentText('BTC')
    tab.address_type.setCurrentText('p2pkh')

    tab.pattern.setText('2Ab')

    assert 'Impossible prefix' in tab.pattern_status.text()
    assert not tab.start_button.isEnabled()


def test_lock_stops_vanity_search(qapp, window):
    unlock(window)
    tab = window.vanity_tab
    tab.coin.setCurrentText('BTC')
    tab.address_type.setCurrentText('p2wpkh')
    tab.pattern.setText('bc1qqqqqqqqqqq')
    tab.workers.setValue(1)
    tab.start()
    search = tab.search

    window.lock()

    assert tab.search is None
    assert not search.running
    assert tab.start_button.isEnabled()


@http_mock.activate
def test_fee_rate_estimate(qapp, window):
    unlock(window)
    address = add_address(window, 'TBTC', 'p2wpkh')
    http_mock.add(
        http_mock.GET,
        f'{TBTC_API}/fee-estimates',
        json={'1': 12.04, '3': 8.1, '6': 4.0, '144': 1.0},
    )
    tab = window.sweep_tab
    tab.select_source(address)

    tab.fee.target.setCurrentIndex(tab.fee.target.findData(1))
    tab.fee.estimate()
    wait_until(qapp, lambda: tab.fee.rate.text())

    assert tab.fee.rate.text() == '12.1'


@http_mock.activate
def test_fee_rate_estimate_not_available(qapp, window):
    unlock(window)
    address = add_address(window, 'TBTC', 'p2wpkh')
    http_mock.add(http_mock.GET, f'{TBTC_API}/fee-estimates', json={})
    tab = window.sweep_tab
    tab.select_source(address)

    tab.fee.estimate()
    wait_until(qapp, lambda: tab.fee.status.text())

    assert 'Fee estimate is not available' in tab.fee.status.text()


@http_mock.activate
def test_send_change_to_change_chain(qapp, window, monkeypatch):
    unlock(window)
    address = add_address(window, 'TBTC', 'p2wpkh')
    http_mock.add(
        http_mock.GET, f'{TBTC_API}/address/{address.address}/utxo', json=esplora_utxos([100000])
    )
    http_mock.add(http_mock.POST, f'{TBTC_API}/tx', body='tx1')
    confirmations, sent = [], []
    monkeypatch.setattr(
        send_tab_module,
        'confirm',
        lambda parent, title, rows, button: confirmations.append(dict(rows)) or True,
    )
    monkeypatch.setattr(
        send_tab_module, 'show_text', lambda parent, title, label, text: sent.append(text)
    )
    change = window.wallet.next_change_address(address.account_id)
    tab = window.send_tab

    tab.select_source(address)
    tab.destination.setText(EXTERNAL_ADDRESS)
    tab.amount.setText('0.0003')
    tab.fee.rate.setText('2')
    tab.prepare()
    wait_until(qapp, lambda: sent)

    assert change.path in confirmations[0]['Change']
    assert change.address in confirmations[0]['Change']
    assert sent == ['tx1']
    assert window.wallet.get_address(change.id) == change  # saved after sending
    raw_transaction = http_mock.calls[-1].request.body
    assert address_to_script(change.address, coins['TBTC']).hex() in raw_transaction


def test_scan_dialog_adds_discovered_addresses(qapp, window, monkeypatch):
    unlock(window)

    def fake_discover(wallet, coin_symbol, progress, cancelled):
        progress(40)
        if coin_symbol == 'LTC':
            raise ValueError('API error: timeout')
        return [DiscoveredAccount('BTC', 'p2tr', 0, [0, 2], [1])]

    monkeypatch.setattr(scan_dialog_module, 'discover', fake_discover)
    dialog = scan_dialog_module.ScanDialog(window)
    dialog.coins['LTC'].setChecked(True)

    dialog.scan()
    wait_until(qapp, lambda: dialog.scan_button.isEnabled())

    text = dialog.results.toPlainText()
    assert 'BTC p2tr account 0: 2 receiving, 1 change' in text
    assert 'LTC: API error: timeout' in text
    dialog.add()
    assert len(btc_account(window, 'p2tr').addresses) == 3


def test_scan_dialog_cancelled_when_wallet_is_locked(qapp, window, monkeypatch):
    unlock(window)

    def fake_discover(wallet, coin_symbol, progress, cancelled):
        window.wallet = None  # the wallet is locked during the scan (widgets only in GUI thread)
        if cancelled():
            raise Cancelled()
        return []

    monkeypatch.setattr(scan_dialog_module, 'discover', fake_discover)
    dialog = scan_dialog_module.ScanDialog(window)

    dialog.scan()
    wait_until(qapp, lambda: dialog.scan_button.isEnabled())

    assert 'Cancelled' in dialog.status.text()
    assert not dialog.add_button.isEnabled()


def test_restored_wallet_is_not_scanned(window, monkeypatch):
    started, messages = [], []
    monkeypatch.setattr(window.background_scan, 'start_coin', started.append)
    monkeypatch.setattr(
        'multicrypto.gui.window.QMessageBox.information', lambda *args: messages.append(args[2])
    )

    window._created(window.wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE), restored=True)

    assert started == []
    assert 'right-click a coin and choose Scan for used addresses' in messages[0]


def test_account_menu_scans_account(window, monkeypatch):
    unlock(window)
    started = []
    monkeypatch.setattr(window.background_scan, 'start_account', started.append)

    actions = window.wallet_tab._account_actions(window.wallet.accounts[0])
    actions['Scan for used addresses']()

    assert started == [window.wallet.accounts[0]]


def test_wallet_tab_shows_change_path(window):
    unlock(window)
    account = btc_account(window)
    window.modify_wallet(lambda wallet: wallet.add_address(account.id, 1, 0))

    item = window.wallet_tab.tree.topLevelItem(0).child(1).child(1)

    assert (item.text(0), item.text(1)) == ('Change 0', '1/0')


def test_wallet_tree_shows_account_groups(window):
    unlock(window)
    account = btc_account(window)
    address = window.modify_wallet(lambda wallet: wallet.new_address(account.id))
    first = window.wallet.account_addresses(account)[0]
    window.wallet_tab.balances = {first.id: 1000, address.id: 500}
    window.wallet_tab.refresh()

    group = window.wallet_tab.tree.topLevelItem(0)
    native = group.child(1)

    assert [group.text(column) for column in range(4)] == ['Bitcoin #0', '', 'BTC', '0.00001500']
    assert [native.text(column) for column in range(4)] == [
        'Native SegWit',
        "m/84'/0'/0'",
        '',
        '0.00001500',
    ]
    assert [group.child(index).text(0) for index in range(4)] == [
        'Taproot',
        'Native SegWit',
        'SegWit',
        'Legacy',
    ]
    assert group.child(0).text(3) == ''
    assert native.child(1).text(2) == address.address


def test_new_address_dialog_defaults(window):
    unlock(window)
    wallet = window.wallet
    btc = wallet.get_group('BTC', 0)

    def dialog(**kwargs):
        return wallet_tab_module.NewAddressDialog(
            window.wallet_tab, wallet, lambda *args: None, **kwargs
        )

    from_group = dialog(group=('BTC', 0))
    assert from_group.group.currentText() == 'Bitcoin #0 (BTC)'
    assert from_group.address_type.currentText() == 'Native SegWit (p2wpkh)'
    assert from_group.path.text() == "m/84'/0'/0'/0/1"
    assert from_group.address.text() == wallet.next_receiving_address(btc.accounts[1].id).address
    assert dialog(group=('DOGE', 0)).address_type.currentText() == 'Legacy (p2pkh)'
    assert dialog(account_id=btc.accounts[0].id).address_type.currentText() == 'Taproot (p2tr)'
    other = dialog()
    assert other.group.currentIndex() == 0
    other.group.setCurrentIndex(other.group.findData(wallet_tab_module.group_id('LTC', 0)))
    assert other.address_type.count() == 4
    assert other.path.text() == "m/84'/2'/0'/0/1"


def test_new_address_of_selected_group(window, monkeypatch):
    unlock(window)
    tab = window.wallet_tab

    def accept(dialog):
        dialog.label.setText('Exchange')
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.NewAddressDialog, 'exec', accept)
    tab.tree.setCurrentItem(tab.tree.topLevelItem(0))

    tab.new_address()

    [_, address] = window.wallet.account_addresses(btc_account(window))
    assert (address.label, address.path) == ('Exchange', "m/84'/0'/0'/0/1")
    assert tab.tree.currentItem().text(2) == address.address


def test_rename_and_remove_account_group(window, monkeypatch):
    unlock(window)
    tab = window.wallet_tab
    monkeypatch.setattr(wallet_tab_module.QInputDialog, 'getText', lambda *args: ('Savings', True))
    monkeypatch.setattr(
        wallet_tab_module.QMessageBox,
        'question',
        lambda *args: wallet_tab_module.QMessageBox.StandardButton.Yes,
    )
    tab.tree.setCurrentItem(tab.tree.topLevelItem(0))

    tab.rename()

    assert window.wallet.get_group('BTC', 0).label == 'Savings'
    assert tab.tree.currentItem().text(0) == 'Savings'
    tab.remove()
    assert 'BTC' not in [group.coin for group in window.wallet.account_groups()]


def test_account_of_group_is_not_renamed(window, monkeypatch):
    unlock(window)
    messages = []
    monkeypatch.setattr(
        wallet_tab_module.QMessageBox, 'information', lambda *args: messages.append(args[2])
    )
    tab = window.wallet_tab
    tab.tree.setCurrentItem(tab.tree.topLevelItem(0).child(0))

    tab.rename()

    assert messages == ['Rename the account group']


def test_new_account_dialog_creates_group(window):
    unlock(window)
    tab = window.wallet_tab
    dialog = wallet_tab_module.NewAccountGroupDialog(tab, window.wallet, tab.add_group)

    dialog.coin.setCurrentText('DOGE')
    assert dialog.account.value() == 1
    assert dialog.paths.text() == "Legacy: m/44'/3'/1'"
    dialog.coin.setCurrentText('BTC')
    dialog.label.setText('Savings')
    dialog.accept()

    group = window.wallet.get_group('BTC', 1)
    assert (group.label, len(group.accounts)) == ('Savings', 4)
    assert tab.tree.currentItem().text(0) == 'Savings'


def test_new_account_dialog_shows_error(window, monkeypatch):
    unlock(window)
    warnings = []
    monkeypatch.setattr(
        wallet_tab_module.QMessageBox, 'warning', lambda *args: warnings.append(args[2])
    )
    tab = window.wallet_tab
    dialog = wallet_tab_module.NewAccountGroupDialog(tab, window.wallet, tab.add_group)

    dialog.account.setValue(0)
    dialog.accept()

    assert 'already in the wallet' in warnings[0]


def test_group_menu_scans_coin(window, monkeypatch):
    unlock(window)
    started = []
    monkeypatch.setattr(window.background_scan, 'start_coin', started.append)

    window.wallet_tab._group_actions('LTC')['Scan for used addresses']()

    assert started == ['LTC']
    assert window.wallet_tab._group_actions('DOGE') == {}


def test_running_scan_keeps_wallet_unlocked(window):
    unlock(window)
    dialog = scan_dialog_module.ScanDialog(window)
    window.set_auto_lock(5)
    window.last_activity -= window.auto_lock_seconds

    dialog._show_progress()
    window.tick()

    assert window.wallet is not None


def p2tr_account_job(progress, cancelled, found):
    progress(40)
    found.append(DiscoveredAccount('BTC', 'p2tr', 0, [0, 2], [1]))


def test_background_scan_adds_found_addresses(qapp, window):
    unlock(window)
    scan = window.background_scan

    assert scan.start('BTC', p2tr_account_job)
    wait_until(qapp, lambda: not scan.running)

    assert len(btc_account(window, 'p2tr').addresses) == 3
    assert scan.label.text() == 'Scan of BTC finished: added 2 addresses'
    assert scan.cancel_button.isHidden()


def test_background_scan_runs_one_scan(qapp, window, monkeypatch):
    unlock(window)
    messages = []
    monkeypatch.setattr(
        'multicrypto.gui.background_scan.QMessageBox.information',
        lambda parent, title, text: messages.append(text),
    )
    release = threading.Event()

    def slow_job(progress, cancelled, found):
        release.wait(5)

    scan = window.background_scan
    assert scan.start('BTC', slow_job)
    assert not scan.start('LTC', p2tr_account_job)
    release.set()
    wait_until(qapp, lambda: not scan.running)

    assert messages == ['A scan is already running']


def test_background_scan_cancel(qapp, window):
    unlock(window)

    def job(progress, cancelled, found):
        while not cancelled():
            time.sleep(0.01)
        raise Cancelled()

    scan = window.background_scan
    scan.start('BTC', job)
    scan.cancel()
    wait_until(qapp, lambda: not scan.running)

    assert scan.label.text() == 'Scan of BTC cancelled'
    assert len(window.wallet.addresses()) == 20


def test_lock_cancels_background_scan(qapp, window):
    unlock(window)

    def job(progress, cancelled, found):
        found.append(DiscoveredAccount('BTC', 'p2tr', 0, [0], []))
        while not cancelled():
            time.sleep(0.01)
        raise Cancelled()

    scan = window.background_scan
    scan.start('BTC', job)
    window.lock()
    wait_until(qapp, lambda: not scan.running)

    assert scan.label.text() == 'Scan of BTC cancelled'


def test_background_scan_error_adds_partial_results(qapp, window, monkeypatch):
    unlock(window)
    warnings = []
    monkeypatch.setattr(
        'multicrypto.gui.background_scan.QMessageBox.warning',
        lambda parent, title, text: warnings.append(text),
    )

    def job(progress, cancelled, found):
        found.append(DiscoveredAccount('BTC', 'p2tr', 0, [1], []))
        raise ValueError('API error: broken')

    scan = window.background_scan
    scan.start('BTC', job)
    wait_until(qapp, lambda: not scan.running)

    assert len(btc_account(window, 'p2tr').addresses) == 2
    assert 'API error: broken' in warnings[0]
    assert 'found before the error were added: 1' in warnings[0]


def test_background_scan_keeps_wallet_unlocked(qapp, window):
    unlock(window)
    scan = window.background_scan
    scan.running = True
    window.set_auto_lock(5)
    window.last_activity -= window.auto_lock_seconds

    scan._show_progress()
    window.tick()

    assert window.wallet is not None
    scan.running = False


def auto_lock_actions(window):
    return {action.text(): action for action in window.auto_lock_group.actions()}


def scale_actions(window):
    return {action.text(): action for action in window.scale_group.actions()}


def test_scale_menu_checks_saved_scale(qapp, tmp_path):
    settings_path = str(tmp_path / 'gui.json')
    save_scale(settings_path, 1.5)
    window = MainWindow(WalletFile(str(tmp_path / 'wallet.mcw')), settings_path=settings_path)

    assert scale_actions(window)['150%'].isChecked()
    close_window(qapp, window)


def test_choosing_scale_saves_it(window, monkeypatch):
    messages = []
    monkeypatch.setattr(
        'multicrypto.gui.window.QMessageBox.information', lambda *args: messages.append(args[2])
    )

    scale_actions(window)['200%'].trigger()
    assert load_scale(window.settings_path) == 2
    scale_actions(window)['Auto (system)'].trigger()

    assert load_scale(window.settings_path) is None
    assert scale_actions(window)['Auto (system)'].isChecked()
    assert messages == [SCALE_MESSAGE] * 2


ETH_KEY = '46' * 32
ETH_KEY_ADDRESS = '0x9d8A62f656a8d1615C1294fd71e9CFb3E4855A4F'


def ethereum_address(window, coin_symbol='ETH'):
    [account] = window.wallet.get_group(coin_symbol, 0).accounts
    return window.wallet.account_addresses(account)[0]


def tree_item(tab, kind, item_id):
    return next(
        item
        for item in tab._items()
        if tuple(item.data(0, wallet_tab_module.ITEM_ROLE)) == (kind, item_id)
    )


def test_wallet_tree_shows_ethereum_group_and_balances(window):
    unlock(window)
    tab = window.wallet_tab
    address = ethereum_address(window)
    tab.balances = {address.id: 10**18 + 5}

    tab.refresh()

    group = tree_item(tab, wallet_tab_module.ACCOUNT_GROUP, 'ETH/0')
    assert [group.text(column) for column in range(4)] == [
        'Ethereum #0',
        '',
        'ETH',
        '1.000000000000000005',
    ]
    account = group.child(0)
    assert (account.text(0), account.text(1)) == ('Ethereum', "m/44'/60'/0'")
    item = tree_item(tab, wallet_tab_module.ADDRESS, address.id)
    assert (item.text(1), item.text(2), item.text(3)) == (
        '0/0',
        address.address,
        '1.000000000000000005',
    )
    assert private_key_to_address(window.wallet.private_key(address)) == address.address


def test_import_ethereum_key(window, monkeypatch):
    unlock(window)

    def fill(dialog):
        dialog.label.setText('Imported')
        dialog.coin.setCurrentText('ETH')
        dialog.wif.setText('0x' + ETH_KEY)
        assert dialog.address.text() == ETH_KEY_ADDRESS
        assert not dialog.form.isRowVisible(dialog.address_type)
        assert dialog.form.labelForField(dialog.wif).text() == 'Private key (hex)'
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.ImportWifDialog, 'exec', fill)
    window.wallet_tab.import_wif()

    [imported] = window.wallet.imported_addresses()
    assert (imported.coin, imported.address_type, imported.address) == (
        'ETH',
        'ethereum',
        ETH_KEY_ADDRESS,
    )


def test_import_dialog_shows_address_type_of_bitcoin(window):
    unlock(window)
    dialog = wallet_tab_module.ImportWifDialog(
        window.wallet_tab, lambda *args: None, ['BTC', 'ETH']
    )

    dialog.coin.setCurrentText('ETH')
    dialog.coin.setCurrentText('BTC')

    assert dialog.form.isRowVisible(dialog.address_type)
    assert dialog.form.labelForField(dialog.wif).text() == 'Private key (WIF)'


def test_show_key_of_ethereum_address(window, monkeypatch):
    unlock(window)
    address = ethereum_address(window)
    shown = []
    monkeypatch.setattr(wallet_tab_module, 'secret_line', lambda secret: secret)
    monkeypatch.setattr(
        wallet_tab_module,
        'SecretDialog',
        lambda parent, title, text, secret: shown.append((title, secret)) or Mock(),
    )

    window.wallet_tab._show_key(address, True)

    [(title, secret)] = shown
    assert title == 'Private key (hex) of "Address 0"'
    assert parse_private_key(secret) == window.wallet.private_key(address)


def test_confirm_dialog_shows_warnings_in_red(qapp):
    from multicrypto.gui.dialogs import ConfirmDialog

    dialog = ConfirmDialog(None, 'Confirm', [('Amount', '1'), ('Warning', 'High fee')], 'Send')

    labels = {label.text(): label for label in dialog.findChildren(QLabel)}
    assert 'c62828' in labels['High fee'].styleSheet()
    assert labels['1'].styleSheet() == ''
    dialog.deleteLater()


def test_balance_tab_checks_ethereum_address(qapp, window, monkeypatch):
    unlock(window)
    tab = window.balance_tab
    address = ethereum_address(window, 'TETH')
    checked = []

    def check(args):
        checked.append((args.coin_symbol, args.address, args.node))
        return EthereumAccount(args.address, 10**18 + 5, 3, None)

    monkeypatch.setattr(balance_tab_module, 'check_ethereum_address', check)

    tab.check_address(address)
    wait_until(qapp, lambda: tab.account.text())

    assert checked == [('TETH', address.address, None)]
    assert tab.account.text() == (
        f'Address: {address.address}\n'
        'Balance: 1.000000000000000005 TETH (1000000000000000005 wei)\n'
        'Sent transactions (nonce): 3\n'
        'All transactions: not available'
    )
    assert tab.filters.isHidden() and tab.table.isHidden() and tab.total.isHidden()
    tab.coin.setCurrentText('BTC')
    assert not tab.filters.isHidden() and tab.account.isHidden()


ETH_DESTINATION = '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed'
TETH_NODE = ethereum_coins['TETH']['rpcs'][0]
FEE_HISTORY = {'baseFeePerGas': [hex(GWEI), hex(2 * GWEI)], 'reward': [[hex(GWEI)]]}


def add_node_results(results, node=TETH_NODE):
    for result in results:
        http_mock.add(http_mock.POST, node, json={'jsonrpc': '2.0', 'id': 1, 'result': result})


def test_send_tab_form_of_ethereum(window):
    unlock(window)
    tab = window.send_tab

    tab.select_source(ethereum_address(window, 'TETH'))

    assert tab.sources.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert not tab.form.isRowVisible(tab.fee)
    assert tab.form.isRowVisible(tab.ethereum_fees)
    assert not tab.advanced_form.isRowVisible(tab.minimum)
    assert not tab.advanced_form.isRowVisible(tab.p2p)
    assert not tab.max_button.isHidden()
    tab.coin.setCurrentText('BTC')
    assert tab.sources.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert tab.form.isRowVisible(tab.fee) and not tab.form.isRowVisible(tab.ethereum_fees)
    assert tab.max_button.isHidden()


@http_mock.activate
def test_send_ethereum(qapp, window, monkeypatch):
    unlock(window)
    address = ethereum_address(window, 'TETH')
    add_node_results([hex(11155111), hex(10**18), '0x0', '0x5208', FEE_HISTORY, '0xhash'])
    confirmations, sent = [], []
    monkeypatch.setattr(
        send_tab_module,
        'confirm',
        lambda parent, title, rows, button: confirmations.append(dict(rows)) or True,
    )
    monkeypatch.setattr(
        send_tab_module, 'show_text', lambda parent, title, label, text: sent.append(text)
    )
    tab = window.send_tab

    tab.select_source(address)
    tab.destination.setText(ETH_DESTINATION.lower())
    tab.amount.setText('0.5')
    tab.prepare()
    wait_until(qapp, lambda: sent)

    assert sent == ['0xhash']
    rows = confirmations[0]
    assert (rows['From'], rows['To'], rows['Amount']) == (
        address.address,
        ETH_DESTINATION,
        '0.5 TETH',
    )
    assert rows['Broadcast'] == 'public nodes'
    raw = json.loads(http_mock.calls[-1].request.body)['params'][0]
    transaction, sender = decode_transaction(bytes.fromhex(raw[2:]))
    assert (sender, transaction.chain_id, transaction.value) == (
        address.address,
        11155111,
        5 * 10**17,
    )
    assert transaction.max_fee_per_gas == 5 * GWEI  # 2 * base fee 2 gwei + tip 1 gwei


@http_mock.activate
def test_send_ethereum_with_given_fees_and_own_node(qapp, window, monkeypatch):
    unlock(window)
    address = ethereum_address(window, 'TETH')
    node = 'http://localhost:8545'
    add_node_results([hex(11155111), hex(10**18), '0x0', '0x5208', FEE_HISTORY, '0xhash'], node)
    confirmations = []
    monkeypatch.setattr(
        send_tab_module,
        'confirm',
        lambda parent, title, rows, button: confirmations.append(dict(rows)) or False,
    )
    tab = window.send_tab

    tab.select_source(address)
    tab.destination.setText(ETH_DESTINATION)
    tab.amount.setText('0.1')
    tab.priority_fee.setText('0.5')
    tab.max_fee.setText('1.5')
    tab.nodes.setText(node)
    tab.prepare()
    wait_until(qapp, lambda: confirmations)

    assert confirmations[0]['Max fee per gas'] == '1.5 gwei'
    assert confirmations[0]['Priority fee per gas'] == '0.5 gwei'
    assert confirmations[0]['Broadcast'] == 'own node'
    methods = [json.loads(call.request.body)['method'] for call in http_mock.calls]
    assert 'eth_sendRawTransaction' not in methods  # not confirmed


@http_mock.activate
def test_send_ethereum_max_and_suggest(qapp, window):
    unlock(window)
    tab = window.send_tab
    tab.select_source(ethereum_address(window, 'TETH'))
    tab.destination.setText(ETH_DESTINATION)
    add_node_results([hex(10**18), '0x5208', FEE_HISTORY])

    tab.fill_max()
    wait_until(qapp, lambda: tab.amount.text())

    assert tab.amount.text() == '0.999895'  # 1 - 21000 * 5 gwei
    assert (tab.priority_fee.text(), tab.max_fee.text()) == ('1', '5')
    assert 'stays on the address' in tab.amount_note.text()
    tab.priority_fee.clear()
    tab.max_fee.clear()
    add_node_results([FEE_HISTORY])
    tab.suggest_fees()
    wait_until(qapp, lambda: tab.max_fee.text())
    assert (tab.priority_fee.text(), tab.max_fee.text()) == ('1', '5')


def test_send_ethereum_requires_destination_for_max(window, monkeypatch):
    unlock(window)
    errors = []
    monkeypatch.setattr(window, 'show_error', errors.append)
    tab = window.send_tab
    tab.select_source(ethereum_address(window, 'TETH'))

    tab.fill_max()

    assert str(errors[0]) == 'Enter the address'


def test_scan_dialog_lists_ethereum(window):
    unlock(window)

    dialog = scan_dialog_module.ScanDialog(window)

    assert {'ETH', 'TETH'} <= set(dialog.coins)
    dialog.deleteLater()


def test_ethereum_group_menu_scans_coin(window, monkeypatch):
    unlock(window)
    started = []
    monkeypatch.setattr(window.background_scan, 'start_coin', started.append)

    window.wallet_tab._group_actions('ETH')['Scan for used addresses']()

    assert started == ['ETH']


WEB3_ADDRESS = '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
WEB3_SIGNATURE = (
    '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3'
    '3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c'
)


def test_sign_and_verify_ethereum_message(qapp, window):
    unlock(window)
    address = ethereum_address(window, 'TETH')
    tab = window.sign_tab

    tab.select_address(address)
    tab.sign_message.setPlainText('Zażółć gęślą jaźń')
    tab.sign()
    wait_until(qapp, lambda: tab.signature.text())
    tab.verify_coin.setCurrentText('BTC')
    tab.verify_address.setText(address.address)
    tab.verify_message.setPlainText('Zażółć gęślą jaźń')
    tab.verify_signature.setText(tab.signature.text())
    tab.verify()

    assert len(tab.signature.text()) == 132
    # detected from the wallet address, ETH and TETH have the same addresses (coin type 60)
    assert tab.verify_coin.currentText() == 'ETH'
    assert 'Signature is valid' in tab.verify_result.text()
    tab.verify_coin.setCurrentText('TETH')
    tab.verify_address.setText('')
    tab.verify_address.setText(address.address)
    assert tab.verify_coin.currentText() == 'TETH'  # kept, it has the address


def test_verify_ethereum_message_of_other_address(window):
    unlock(window)
    tab = window.sign_tab
    tab.verify_coin.setCurrentText('BTC')

    tab.verify_address.setText(WEB3_ADDRESS)
    tab.verify_message.setPlainText('I♥SF')
    tab.verify_signature.setText(WEB3_SIGNATURE)
    tab.verify()

    assert tab.verify_coin.currentText() == 'ETH'
    assert 'Signature is valid' in tab.verify_result.text()
    tab.verify_signature.setText('0x1234')
    tab.verify()
    assert 'Signature must have 65 bytes' in tab.verify_result.text()


def test_vanity_search_ethereum_and_add_to_wallet(qapp, window):
    unlock(window)
    tab = window.vanity_tab
    tab.coin.setCurrentText('ETH')
    tab.pattern.setText('0xA')
    tab.workers.setValue(1)

    assert not tab.address_type.isEnabled()
    assert tab.address_type.currentText() == 'ethereum'
    assert 'Addresses start with 0x' in tab.pattern_status.text()
    assert '~16 attempts' in tab.pattern_status.text()
    tab.start()
    wait_until(qapp, lambda: not tab.result_group.isHidden(), seconds=60)

    address = tab.result_address.text()
    assert address.lower().startswith('0xa')
    assert private_key_to_address(parse_private_key(tab.result_key.text())) == address
    tab.result_label.setText('Vanity')
    tab.add_to_wallet()
    [imported] = window.wallet.imported_addresses()
    assert (imported.coin, imported.address) == ('ETH', address)


def test_translate_key_tab_to_ethereum(window):
    unlock(window)
    tab = window.translate_tab
    tab.key.setText('0x' + '00' * 31 + '01')
    tab.integer.setChecked(True)
    tab.key_output_coin.setCurrentText('ETH')

    tab.translate_key()

    assert tab.translated_key.text() == '0x' + '00' * 31 + '01'
    assert tab.key_addresses.item(0, 1).text() == '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'


def test_translate_ethereum_key_to_bitcoin_in_wallet(window, monkeypatch):
    unlock(window)
    address = window.modify_wallet(
        lambda wallet: wallet.add_ethereum_key('Eth', 'ETH', '00' * 31 + '01')
    )

    def accept(dialog):
        dialog.coin.setCurrentText('BTC')
        dialog.address_type.setCurrentText('p2pkh')
        assert dialog.address.text() == '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.TranslateKeyDialog, 'exec', accept)
    window.wallet_tab.translate_key(address)

    btc = [key for key in window.wallet.imported_addresses() if key.coin == 'BTC']
    assert [key.address for key in btc] == ['1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH']


def test_translate_bitcoin_key_to_ethereum_in_wallet(window, monkeypatch):
    unlock(window)
    address = window.modify_wallet(
        lambda wallet: wallet.add_wif(
            'Btc', 'BTC', 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn', 'p2pkh'
        )
    )

    def accept(dialog):
        dialog.coin.setCurrentText('ETH')
        assert not dialog.form.isRowVisible(dialog.address_type)
        assert dialog.address.text() == '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.TranslateKeyDialog, 'exec', accept)
    window.wallet_tab.translate_key(address)

    eth = [key for key in window.wallet.imported_addresses() if key.coin == 'ETH']
    assert [key.address for key in eth] == ['0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf']
