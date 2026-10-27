from unittest.mock import Mock

import pyqrcode
import pytest
from nacl import pwhash

pytest.importorskip('PySide6')

from multicrypto.gui.create_wizard import RESTORE_PAGE, SHOW_PAGE, CreateWalletWizard  # noqa: E402
from multicrypto.gui.qr import QUIET_ZONE, QrDialog, qr_image  # noqa: E402
from multicrypto.gui.window import MainWindow  # noqa: E402
from multicrypto.wallet import WalletAddress, WalletFile  # noqa: E402

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
