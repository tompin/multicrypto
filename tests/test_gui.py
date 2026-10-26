from unittest.mock import Mock

import pytest
from nacl import pwhash

tkinter = pytest.importorskip('tkinter')

from multicrypto.gui.forms import entry_description  # noqa: E402
from multicrypto.gui.window import MainWindow  # noqa: E402
from multicrypto.wallet import WalletFile  # noqa: E402

PASSWORD = 'correct horse battery'
BTC_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'


@pytest.fixture
def root():
    try:
        root = tkinter.Tk()
    except tkinter.TclError:
        pytest.skip('No display available')
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def window(root, tmp_path):
    wallet_file = WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )
    return MainWindow(root, wallet_file)


def test_wallet_is_shown_when_unlocked_and_cleared_when_locked(window):
    window.show_wallet(window.wallet_file.create(PASSWORD))
    assert 'unlocked' in window.status.get()

    entry = window.modify_wallet(lambda wallet: wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh'))
    for tab in window.tabs:
        window.notebook.select(tab.frame)

    assert window.wallet_tab.tree.get_children() == (entry.id,)
    assert window.send_tab.sources.get_children() == (entry.id,)
    assert window.balance_tab.entry_box.get() == entry_description(entry)

    window.lock()

    assert window.wallet is None
    assert not window.wallet_file.is_unlocked
    assert window.wallet_tab.tree.get_children() == ()
    assert window.send_tab.sources.get_children() == ()
    assert window.balance_tab.entry_box.get() == ''


def test_modify_wallet_reverts_change_when_saving_fails(window, monkeypatch):
    window.show_wallet(window.wallet_file.create(PASSWORD))
    monkeypatch.setattr(window.wallet_file, 'save', Mock(side_effect=OSError('disk full')))

    with pytest.raises(OSError):
        window.modify_wallet(lambda wallet: wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh'))

    assert window.wallet.entries == []


def test_wallet_is_locked_after_inactivity(window):
    window.show_wallet(window.wallet_file.create(PASSWORD))
    window.last_activity -= window.auto_lock_seconds

    window.tick()

    assert window.wallet is None
    assert 'locked' in window.status.get()
