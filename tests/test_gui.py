import time
from unittest.mock import Mock

import pyqrcode
import pytest
from nacl import pwhash
from tests import http_mock

from multicrypto.address import convert_private_key_to_coin_address, get_private_key_from_wif_format
from multicrypto.api import get_api
from multicrypto.coins import coins

pytest.importorskip('PySide6')

import multicrypto.gui.sweep_tab as sweep_tab_module  # noqa: E402
import multicrypto.gui.wallet_tab as wallet_tab_module  # noqa: E402
from multicrypto.gui.create_wizard import RESTORE_PAGE, SHOW_PAGE, CreateWalletWizard  # noqa: E402
from multicrypto.gui.qr import QUIET_ZONE, QrDialog, qr_image  # noqa: E402
from multicrypto.gui.window import MainWindow  # noqa: E402
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


def test_wizard_confirms_generated_mnemonic(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')
    words = wizard.generated_mnemonic.split()
    for position, field in wizard.confirm_page.answers.items():
        field.setText(words[position - 1])

    assert len(words) == 24
    assert wizard.mode_page.nextId() == SHOW_PAGE
    assert wizard.confirm_page.validatePage()
    assert wizard.values()[1] == wizard.generated_mnemonic


def test_restore_page_shows_mnemonic_errors(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')

    wizard.restore_page.text.setPlainText(' '.join(['abandon'] * 12))

    assert 'checksum' in wizard.restore_page.status.text()


@pytest.fixture
def window(qapp, tmp_path):
    wallet_file = WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )
    window = MainWindow(wallet_file)
    yield window
    window.timer.stop()
    qapp.removeEventFilter(window)


def unlock(window):
    window.show_wallet(window.wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE))


def test_wallet_is_shown_when_unlocked_and_cleared_when_locked(window):
    unlock(window)
    account = window.wallet.accounts[0]

    address = window.modify_wallet(lambda wallet: wallet.new_address(account.id, 'Savings'))

    tree = window.wallet_tab.tree
    assert 'unlocked' in window.status.text()
    assert window.wallet.fingerprint in window.status.text()
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).child(0).text(2) == address.address
    assert window.balance_tab.address_box.count() == 1
    assert window.send_tab.sources.count() == 1

    window.lock()

    assert window.wallet is None
    assert not window.wallet_file.is_unlocked
    assert tree.topLevelItemCount() == 0
    assert window.send_tab.sources.count() == 0
    assert window.balance_tab.address_box.count() == 0
    assert 'locked' in window.status.text()


def test_imported_keys_are_shown_in_separate_group(window):
    unlock(window)

    window.modify_wallet(lambda wallet: wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh'))

    group = window.wallet_tab.tree.topLevelItem(1)
    assert group.text(0).startswith('Imported keys')
    assert group.child(0).text(0) == 'Old'


def test_modify_wallet_reverts_change_when_saving_fails(window, monkeypatch):
    unlock(window)
    account_id = window.wallet.accounts[0].id
    monkeypatch.setattr(window.wallet_file, 'save', Mock(side_effect=OSError('disk full')))

    with pytest.raises(OSError):
        window.modify_wallet(lambda wallet: wallet.new_address(account_id, 'Savings'))

    assert window.wallet.accounts[0].addresses == []


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


def wait_until(qapp, condition):
    deadline = time.monotonic() + 10
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
    tab.fee.setText('1000')
    tab.batch_size.setText('2')
    tab.prepare()
    wait_until(qapp, lambda: shown)

    assert window.tab_widget.currentWidget() is tab
    assert shown == [['tx1', 'tx2']]
    assert confirmations[0]['From'] == confirmations[0]['To'] == address.address
    assert confirmations[0]['Transactions'] == '2'
    assert confirmations[0]['Received'] == '0.00298000 TBTC'
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
        'Address 0 (LTC)',
        'LTC',
        'p2wpkh',
    )
