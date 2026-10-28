import json
import os
import stat

import pytest
from nacl import pwhash

from multicrypto.address import convert_private_key_to_wif_format
from multicrypto.coins import coins
from multicrypto.ellipticcurve import secp256k1
from multicrypto.wallet import (
    CHANGE_CHAIN,
    HEADER_SIZE,
    RECEIVE_CHAIN,
    UNSUPPORTED_FORMAT,
    WRONG_PASSWORD,
    ImportedKey,
    Wallet,
    WalletError,
    WalletFile,
    account_path,
    check_entry,
    generate_wif,
    group_address_types,
    group_label,
)

MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])
PASSWORD = 'correct horse battery'
NEW_PASSWORD = 'new password 123'
PASSPHRASE = 'secret passphrase'
BTC_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'
BTC_P2WPKH_ADDRESS = 'bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q'
TBTC_WIF = 'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo'
TBTC_P2TR_ADDRESS = 'tb1p5z79qpqcp9wf02p2zd5dtz89pxla4qu3zuz5w5hxhz7ds58cce4s9ztvgh'
UNCOMPRESSED_WIF = '5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ'
UNCOMPRESSED_ADDRESS = '1GAehh7TsJAHuUAeKZcXf5CnwuGuGgyX2S'


# Private keys in WIF format


def test_check_entry_returns_address():
    assert check_entry('BTC', BTC_WIF, 'p2wpkh') == BTC_P2WPKH_ADDRESS
    assert check_entry('TBTC', TBTC_WIF, 'p2tr') == TBTC_P2TR_ADDRESS
    assert check_entry('BTC', UNCOMPRESSED_WIF, 'p2pkh') == UNCOMPRESSED_ADDRESS


@pytest.mark.parametrize(
    'coin_symbol, wif, address_type, message',
    [
        ('XXX', BTC_WIF, 'p2pkh', 'Unknown coin XXX'),
        ('BTC', BTC_WIF, 'p2xx', 'Unknown address type'),
        ('DOGE', BTC_WIF, 'p2wpkh', 'is not supported'),
        ('TBTC', BTC_WIF, 'p2pkh', 'not in WIF format of TBTC'),
        ('BTC', BTC_WIF[:-1] + 'h', 'p2pkh', 'Incorrect checksum'),
        ('BTC', '0' + BTC_WIF[1:], 'p2pkh', 'only base58 characters'),
        ('BTC', '', 'p2pkh', 'only base58 characters'),
        ('BTC', convert_private_key_to_wif_format(secp256k1.n, b'\x80'), 'p2pkh', 'Incorrect'),
        ('BTC', UNCOMPRESSED_WIF, 'p2wpkh', 'compressed public key'),
    ],
)
def test_check_entry_rejects_incorrect_data(coin_symbol, wif, address_type, message):
    with pytest.raises(ValueError, match=message):
        check_entry(coin_symbol, wif, address_type)


def test_generate_wif():
    assert generate_wif('BTC', private_key=1) == (
        'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn'
    )
    assert check_entry('TBTC', generate_wif('TBTC'), 'p2tr').startswith('tb1p')


def test_imported_key_repr_does_not_contain_private_key():
    assert BTC_WIF not in repr(ImportedKey('Old', 'BTC', BTC_WIF, 'p2wpkh'))


# HD wallet


def test_fingerprint_of_test_mnemonic():
    assert Wallet.create(MNEMONIC, '').fingerprint == '73c5da0a'


@pytest.mark.parametrize(
    'coin, address_type, index, expected',
    [
        ('BTC', 'p2pkh', 0, '1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA'),  # BIP-44
        ('TBTC', 'p2sh-p2wpkh', 0, '2Mww8dCYPUpKHofjgcXcBCEGmniw9CoaiD2'),  # BIP-49
        ('BTC', 'p2wpkh', 0, 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'),  # BIP-84
        ('BTC', 'p2wpkh', 1, 'bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g'),
        (
            'BTC',
            'p2tr',
            0,
            'bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr',
        ),  # BIP-86
        ('BTC', 'p2tr', 1, 'bc1p4qhjn9zdvkux4e44uhx8tc55attvtyu358kutcqkudyccelu0was9fqzwh'),
    ],
)
def test_bip_test_vectors(coin, address_type, index, expected):
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', coin, address_type)

    addresses = [wallet.new_address(account.id) for _ in range(index + 1)]

    assert addresses[index].address == expected
    assert addresses[index].path == f'{account.path}/0/{index}'


def test_private_key_of_hd_address():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', 'TBTC', 'p2sh-p2wpkh')

    address = wallet.new_address(account.id, 'First')

    # BIP-49 test vector
    assert wallet.private_key_wif(address) == 'cULrpoZGXiuC19Uhvykx7NugygA3k86b3hmdCeyvHYQZSxojGyXJ'


def test_account_path():
    assert account_path('BTC', 'p2wpkh', 0) == "m/84'/0'/0'"
    assert account_path('LTC', 'p2pkh', 3) == "m/44'/2'/3'"
    assert account_path('TLTC', 'p2tr', 1) == "m/86'/1'/1'"


def test_add_account_numbers():
    wallet = Wallet.create(MNEMONIC, '')

    first = wallet.add_account('First', 'BTC', 'p2wpkh')
    second = wallet.add_account('Second', 'BTC', 'p2wpkh')
    legacy = wallet.add_account('Legacy', 'BTC', 'p2pkh')

    assert (first.account, second.account, legacy.account) == (0, 1, 0)
    assert wallet.next_account_number('BTC', 'p2wpkh') == 2


@pytest.mark.parametrize(
    'coin, address_type, account, message',
    [
        ('DOGE', 'p2wpkh', None, 'is not supported'),
        ('BTC', 'p2wpkh', 2**31, 'Account number must be'),
        ('BTC', 'p2wpkh', 0, 'already in the wallet'),
        ('XXX', 'p2pkh', None, 'Unknown coin'),
    ],
)
def test_add_account_errors(coin, address_type, account, message):
    wallet = Wallet.create(MNEMONIC, '')
    wallet.add_account('Existing', 'BTC', 'p2wpkh')

    with pytest.raises(ValueError, match=message):
        wallet.add_account('New', coin, address_type, account)


def test_add_account_requires_slip44(monkeypatch):
    monkeypatch.delitem(coins['DOGE'], 'slip44')
    wallet = Wallet.create(MNEMONIC, '')

    with pytest.raises(ValueError, match='no SLIP-44 coin type'):
        wallet.add_account('New', 'DOGE', 'p2pkh')


def test_group_address_types_and_label():
    assert group_address_types('BTC') == ['p2tr', 'p2wpkh', 'p2sh-p2wpkh', 'p2pkh']
    assert group_address_types('DOGE') == ['p2pkh']
    assert group_label('BTC', 0) == 'Bitcoin #0'
    assert group_label('TBTC', 2) == 'Bitcoin Testnet #2'


def test_account_groups():
    wallet = Wallet.create(MNEMONIC, '')
    legacy = wallet.add_account('Savings', 'BTC', 'p2pkh', 0)
    native = wallet.add_account('Savings', 'BTC', 'p2wpkh', 0)
    doge = wallet.add_account('Doge', 'DOGE', 'p2pkh', 0)
    taproot = wallet.add_account('Other', 'BTC', 'p2tr', 1)
    nested = wallet.add_account('Different', 'BTC', 'p2sh-p2wpkh', 1)

    groups = wallet.account_groups()

    assert [(g.coin, g.number, g.label, g.accounts) for g in groups] == [
        ('BTC', 0, 'Savings', [native, legacy]),
        ('DOGE', 0, 'Doge', [doge]),
        ('BTC', 1, 'Bitcoin #1', [taproot, nested]),
    ]
    assert wallet.get_group('BTC', 1) == groups[2]
    with pytest.raises(KeyError):
        wallet.get_group('LTC', 0)
    assert wallet.next_group_number('BTC') == 2
    assert wallet.next_group_number('LTC') == 0


def test_new_address_labels_and_indexes():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')

    first = wallet.new_address(account.id, 'Exchange')
    second = wallet.new_address(account.id)

    assert (first.label, first.index, second.label, second.index) == ('Exchange', 0, 'Address 1', 1)
    assert wallet.addresses() == [first, second]
    assert wallet.get_address(second.id) == second


def test_imported_keys():
    wallet = Wallet.create(MNEMONIC, '')

    address = wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh')

    assert (address.address, address.path, address.account_id) == (BTC_P2WPKH_ADDRESS, None, None)
    assert wallet.private_key_wif(address) == BTC_WIF
    with pytest.raises(ValueError, match='already in the wallet'):
        wallet.add_wif('Again', 'BTC', BTC_WIF, 'p2wpkh')
    with pytest.raises(ValueError):
        wallet.add_wif('Wrong', 'TBTC', BTC_WIF, 'p2pkh')
    assert wallet.addresses() == [address]


def test_rename_and_remove():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')
    first = wallet.new_address(account.id, 'First')
    second = wallet.new_address(account.id, 'Second')
    imported = wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh')

    wallet.rename(account.id, 'Renamed account')
    wallet.rename(second.id, 'Renamed address')
    wallet.remove(first.id)
    wallet.remove(imported.id)

    assert account.label == 'Renamed account'
    assert [address.label for address in wallet.addresses()] == ['Renamed address']
    wallet.remove(account.id)
    assert wallet.accounts == []
    with pytest.raises(KeyError):
        wallet.remove(account.id)


def test_closed_wallet_cannot_derive_keys():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')

    wallet.close()

    with pytest.raises(WalletError, match='locked'):
        wallet.new_address(account.id)
    assert account.addresses == []


def test_open_checks_fingerprint():
    wallet = Wallet.create(MNEMONIC, PASSPHRASE)
    closed = Wallet.from_json(wallet.to_json())

    with pytest.raises(WalletError, match='This passphrase gives wallet 73c5da0a'):
        closed.open('')
    closed.open(PASSPHRASE)

    assert closed.is_open


def test_json_round_trip_does_not_contain_passphrase():
    wallet = Wallet.create(MNEMONIC, PASSPHRASE)
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')
    wallet.new_address(account.id, 'First')
    wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh')

    data = wallet.to_json()
    restored = Wallet.from_json(data)
    restored.open(PASSPHRASE)

    assert PASSPHRASE.encode() not in data
    assert restored.accounts == wallet.accounts
    assert restored.imported == wallet.imported
    assert restored.addresses() == wallet.addresses()


# Wallet file


@pytest.fixture
def wallet_file(tmp_path):
    return WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )


def read(path):
    with open(path, 'rb') as file:
        return file.read()


def test_create_and_unlock(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    address = wallet.new_address(wallet.accounts[0].id, 'Savings')
    wallet_file.save(wallet)
    wallet_file.lock()

    unlocked = WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)

    assert [(a.label, a.coin, a.address_type) for a in unlocked.accounts] == [
        ('Bitcoin', 'BTC', 'p2wpkh')
    ]
    assert unlocked.addresses() == [address]


def test_file_is_encrypted_and_private(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    wallet_file.save(wallet)

    data = read(wallet_file.path)
    assert data.startswith(b'MCWALLET\x02')
    for secret in ('abandon', BTC_WIF, 'Savings', PASSPHRASE):
        assert secret.encode() not in data
    assert stat.S_IMODE(os.stat(wallet_file.path).st_mode) == 0o600
    assert not os.path.exists(wallet_file.path + '.tmp')


@pytest.mark.parametrize(
    'password, mnemonic, passphrase, message',
    [
        ('short', MNEMONIC, PASSPHRASE, 'at least 10 characters'),
        (PASSWORD, 'abandon about', PASSPHRASE, 'must have 12'),
    ],
)
def test_create_validates_input(wallet_file, password, mnemonic, passphrase, message):
    with pytest.raises(ValueError, match=message):
        wallet_file.create(password, mnemonic, passphrase)

    assert not wallet_file.exists()


def test_create_does_not_overwrite_existing_file(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    with pytest.raises(WalletError, match='already exists'):
        WalletFile(wallet_file.path).create(PASSWORD, MNEMONIC, PASSPHRASE)


def test_create_makes_private_directory(tmp_path):
    path = tmp_path / 'new' / 'wallet.mcw'

    WalletFile(str(path), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN).create(
        PASSWORD, MNEMONIC, PASSPHRASE
    )

    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700


def test_unlock_with_wrong_password(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    with pytest.raises(WalletError, match=WRONG_PASSWORD):
        WalletFile(wallet_file.path).unlock('wrong password', PASSPHRASE)


def test_unlock_with_wrong_passphrase(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    other_file = WalletFile(wallet_file.path)

    with pytest.raises(WalletError, match=f'created with {wallet.fingerprint}'):
        other_file.unlock(PASSWORD, 'other passphrase')

    assert not other_file.is_unlocked


def test_wallet_without_passphrase(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, '')

    unlocked = WalletFile(wallet_file.path).unlock(PASSWORD)

    assert wallet.fingerprint == unlocked.fingerprint == '73c5da0a'


def test_decrypt_returns_closed_wallet(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, '')
    other_file = WalletFile(wallet_file.path)

    wallet = other_file.decrypt(PASSWORD)

    assert other_file.is_unlocked
    assert not wallet.is_open
    assert wallet.open_without_passphrase()
    assert wallet.is_open


def test_wallet_with_passphrase_is_not_opened_without_it(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    wallet = WalletFile(wallet_file.path).decrypt(PASSWORD)

    assert not wallet.open_without_passphrase()
    assert not wallet.is_open


def test_save_uses_new_nonce(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    first = read(wallet_file.path)

    wallet_file.save(wallet)

    second = read(wallet_file.path)
    assert first[:41] == second[:41]
    assert first[41:HEADER_SIZE] != second[41:HEADER_SIZE]


@pytest.mark.parametrize('offset', [0, 8, 16, 24, 25, 41, HEADER_SIZE, -1])
def test_unlock_detects_modification(wallet_file, offset):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    data = bytearray(read(wallet_file.path))
    data[offset] ^= 1
    with open(wallet_file.path, 'wb') as file:
        file.write(data)

    with pytest.raises(WalletError):
        WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)


def test_unlock_rejects_version_1(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    data = bytearray(read(wallet_file.path))
    data[8] = 1
    with open(wallet_file.path, 'wb') as file:
        file.write(data)

    with pytest.raises(WalletError, match=UNSUPPORTED_FORMAT):
        WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)


def test_unlock_unsupported_file(tmp_path):
    path = tmp_path / 'wallet.mcw'
    path.write_bytes(b'not a wallet')

    with pytest.raises(WalletError, match=UNSUPPORTED_FORMAT):
        WalletFile(str(path)).unlock(PASSWORD, PASSPHRASE)


def test_verify_password(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    assert wallet_file.verify_password(PASSWORD)
    assert not wallet_file.verify_password('wrong password')


def test_change_password(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    salt = read(wallet_file.path)[25:41]

    wallet_file.change_password(PASSWORD, NEW_PASSWORD, wallet)

    assert read(wallet_file.path)[25:41] != salt
    with pytest.raises(WalletError):
        WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)
    unlocked = WalletFile(wallet_file.path).unlock(NEW_PASSWORD, PASSPHRASE)
    assert unlocked.accounts == wallet.accounts


def test_change_password_with_wrong_old_password(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    with pytest.raises(WalletError, match='Wrong password'):
        wallet_file.change_password('wrong password', NEW_PASSWORD, wallet)

    assert WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE).accounts == wallet.accounts


def test_locked_wallet_file_cannot_be_saved(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    wallet_file.lock()

    with pytest.raises(WalletError, match='locked'):
        wallet_file.save(wallet)


def test_change_address_of_bip84_vector():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', 'BTC', 'p2wpkh')

    change = wallet.next_change_address(account.id)

    assert change.address == 'bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el'
    assert change.path == "m/84'/0'/0'/1/0"
    assert (change.chain, change.index, change.label) == (CHANGE_CHAIN, 0, 'Change 0')
    assert account.addresses == []  # not saved until it is added


def test_add_change_address():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', 'BTC', 'p2wpkh')
    change = wallet.next_change_address(account.id)

    added = wallet.add_address(account.id, CHANGE_CHAIN, 0)
    receiving = wallet.new_address(account.id)

    assert added == change
    assert wallet.add_address(account.id, CHANGE_CHAIN, 0) == change  # not duplicated
    assert len(account.addresses) == 2
    assert receiving.path == "m/84'/0'/0'/0/0"
    assert wallet.next_change_address(account.id).index == 1
    assert wallet.get_address(change.id) == change
    assert check_entry('BTC', wallet.private_key_wif(change), 'p2wpkh') == change.address
    assert [address.chain for address in wallet.account_addresses(account)] == [
        RECEIVE_CHAIN,
        CHANGE_CHAIN,
    ]


def test_address_at_does_not_add_address():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', 'BTC', 'p2wpkh')

    assert wallet.address_at(account, CHANGE_CHAIN, 0) == (
        'bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el'
    )
    assert account.addresses == []


def test_wallet_without_chain_field_is_loaded():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', 'BTC', 'p2wpkh')
    wallet.new_address(account.id)
    data = json.loads(wallet.to_json())
    del data['accounts'][0]['addresses'][0]['chain']

    loaded = Wallet.from_json(json.dumps(data).encode())

    assert loaded.accounts[0].addresses[0].chain == RECEIVE_CHAIN
