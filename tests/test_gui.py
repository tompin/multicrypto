import pytest

pytest.importorskip('PySide6')

from multicrypto.gui.create_wizard import RESTORE_PAGE, SHOW_PAGE, CreateWalletWizard  # noqa: E402

PASSWORD = 'correct horse battery'
PASSPHRASE = 'secret passphrase'
MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])


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
