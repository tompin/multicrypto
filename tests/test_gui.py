import threading
import time
from unittest.mock import Mock

import pyqrcode
import pytest
from nacl import pwhash
from tests import http_mock

from multicrypto.address import convert_private_key_to_coin_address, get_private_key_from_wif_format
from multicrypto.api import get_api
from multicrypto.coins import coins
from multicrypto.scripts import address_to_script

pytest.importorskip('PySide6')

from PySide6.QtWidgets import QLabel  # noqa: E402

import multicrypto.gui.send_tab as send_tab_module  # noqa: E402
from multicrypto.gui.address_picker import WalletAddressPicker  # noqa: E402
import multicrypto.gui.scan_dialog as scan_dialog_module  # noqa: E402
from multicrypto.discovery import Cancelled, DiscoveredAccount  # noqa: E402
import multicrypto.gui.sweep_tab as sweep_tab_module  # noqa: E402
import multicrypto.gui.vanity_tab as vanity_tab_module  # noqa: E402
import multicrypto.gui.wallet_tab as wallet_tab_module  # noqa: E402
from multicrypto.gui.create_wizard import RESTORE_PAGE, SHOW_PAGE, CreateWalletWizard  # noqa: E402
from multicrypto.gui.dialogs import mnemonic_grid  # noqa: E402
from multicrypto.gui.qr import QUIET_ZONE, QrDialog, qr_image  # noqa: E402
from multicrypto.gui.settings import load_scale, save_scale  # noqa: E402
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
    window = MainWindow(wallet_file, settings_path=str(tmp_path / 'gui.json'))
    yield window
    window.timer.stop()
    qapp.removeEventFilter(window)


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
    assert tree.topLevelItemCount() == 6
    assert tree.topLevelItem(0).child(1).child(1).text(2) == address.address
    assert window.balance_tab.picker.box.count() == 5
    assert window.send_tab.sources.count() == 19

    window.lock()

    assert window.wallet is None
    assert not window.wallet_file.is_unlocked
    assert tree.topLevelItemCount() == 0
    assert window.send_tab.sources.count() == 0
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


def test_wallet_is_locked_after_inactivity(window):
    unlock(window)
    window.last_activity -= window.auto_lock_seconds

    window.tick()

    assert window.wallet is None


def test_send_tab_validates_destination(window):
    unlock(window)
    account = window.wallet.accounts[0]
    window.modify_wallet(lambda wallet: wallet.new_address(account.id, 'Savings'))
    window.send_tab.sources.item(0).setSelected(True)

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


def test_taproot_address_cannot_be_selected_for_signing(window):
    unlock(window)
    address = add_address(window, 'BTC', 'p2tr')
    tab = window.sign_tab

    index = tab.sign_address.findData(address.id)

    assert not tab.sign_address.model().item(index).isEnabled()
    assert 'taproot: not supported' in tab.sign_address.itemText(index)


def test_lock_clears_sign_tab(window):
    unlock(window)
    window.sign_tab.sign_message.setPlainText('Secret plan')
    window.sign_tab.signature.setText('signature')

    window.lock()

    assert window.sign_tab.sign_message.toPlainText() == ''
    assert window.sign_tab.signature.text() == ''
    assert window.sign_tab.sign_address.count() == 0


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
    tab.destination_box.setCurrentIndex(tab.destination_box.findData(address.id))
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


def test_lock_clears_sweep_key(window):
    unlock(window)
    window.sweep_tab.wif.setText(EXTERNAL_WIF)

    window.lock()

    assert window.sweep_tab.wif.text() == ''
    assert window.sweep_tab.source_box.count() == 0


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


def test_new_address_needs_address_type(window, monkeypatch):
    unlock(window)
    messages = []
    monkeypatch.setattr(
        wallet_tab_module.QMessageBox, 'information', lambda *args: messages.append(args[2])
    )
    tab = window.wallet_tab
    tab.tree.setCurrentItem(tab.tree.topLevelItem(0))

    tab.new_address()

    assert messages == ['Select an address type first']


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
    assert len(window.wallet.addresses()) == 18


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
    window.last_activity -= window.auto_lock_seconds

    scan._show_progress()
    window.tick()

    assert window.wallet is not None
    scan.running = False


def scale_actions(window):
    return {action.text(): action for action in window.scale_group.actions()}


def test_scale_menu_checks_saved_scale(qapp, tmp_path):
    settings_path = str(tmp_path / 'gui.json')
    save_scale(settings_path, 1.5)
    window = MainWindow(WalletFile(str(tmp_path / 'wallet.mcw')), settings_path=settings_path)

    assert scale_actions(window)['150%'].isChecked()
    window.timer.stop()
    qapp.removeEventFilter(window)


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
