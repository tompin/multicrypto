import os
import stat
import unicodedata

import pytest
from nacl import pwhash

from multicrypto.address import convert_private_key_to_wif_format
from multicrypto.ellipticcurve import secp256k1
from multicrypto.wallet import (
    HEADER_SIZE,
    UNSUPPORTED_FORMAT,
    WRONG_PASSWORD,
    Wallet,
    WalletEntry,
    WalletError,
    WalletFile,
    check_entry,
    generate_wif,
)

BTC_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'
BTC_P2WPKH_ADDRESS = 'bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q'
TBTC_WIF = 'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo'
TBTC_P2TR_ADDRESS = 'tb1p5z79qpqcp9wf02p2zd5dtz89pxla4qu3zuz5w5hxhz7ds58cce4s9ztvgh'
UNCOMPRESSED_WIF = '5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ'
UNCOMPRESSED_ADDRESS = '1GAehh7TsJAHuUAeKZcXf5CnwuGuGgyX2S'


def test_check_entry_returns_address():
    assert check_entry('BTC', BTC_WIF, 'p2wpkh') == BTC_P2WPKH_ADDRESS
    assert check_entry('TBTC', TBTC_WIF, 'p2tr') == TBTC_P2TR_ADDRESS
    assert check_entry('BTC', UNCOMPRESSED_WIF, 'p2pkh') == UNCOMPRESSED_ADDRESS


@pytest.mark.parametrize(
    'coin_symbol, wif, address_type, message',
    [
        ('XXX', BTC_WIF, 'p2pkh', 'Unknown coin XXX'),
        ('BTC', BTC_WIF, 'p2xx', 'Unknown address type'),
        ('ZEC', BTC_WIF, 'p2wpkh', 'is not supported'),
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
    wif = generate_wif('TBTC')
    assert check_entry('TBTC', wif, 'p2tr').startswith('tb1p')
    assert generate_wif('TBTC') != wif


def test_wallet_add_wif():
    wallet = Wallet()

    entry = wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')

    assert wallet.entries == [entry]
    assert entry.address == BTC_P2WPKH_ADDRESS
    assert wallet.get(entry.id) is entry


def test_wallet_rejects_duplicate():
    wallet = Wallet()
    wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')

    with pytest.raises(ValueError, match='already in the wallet'):
        wallet.add_wif('Other', 'BTC', BTC_WIF, 'p2wpkh')
    wallet.add_wif('Legacy', 'BTC', BTC_WIF, 'p2pkh')  # other address type is other entry

    assert [entry.label for entry in wallet.entries] == ['Savings', 'Legacy']


def test_wallet_add_wif_validates_entry():
    wallet = Wallet()

    with pytest.raises(ValueError):
        wallet.add_wif('Savings', 'TBTC', BTC_WIF, 'p2pkh')

    assert wallet.entries == []


def test_wallet_remove():
    wallet = Wallet()
    entry = wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')

    wallet.remove(entry.id)

    assert wallet.entries == []
    with pytest.raises(KeyError):
        wallet.remove(entry.id)


def test_wallet_entry_repr_does_not_contain_private_key():
    assert BTC_WIF not in repr(WalletEntry('Savings', 'BTC', BTC_WIF, 'p2wpkh'))


def test_wallet_json_round_trip():
    wallet = Wallet()
    wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    wallet.add_wif('Testnet', 'TBTC', TBTC_WIF, 'p2tr')

    assert Wallet.from_json(wallet.to_json()).entries == wallet.entries


PASSWORD = 'correct horse battery'
NEW_PASSWORD = 'new password 123'


@pytest.fixture
def wallet_file(tmp_path):
    return WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )


def read(path):
    with open(path, 'rb') as file:
        return file.read()


def test_create_save_and_unlock(wallet_file):
    wallet = wallet_file.create(PASSWORD)
    wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    wallet_file.save(wallet)
    wallet_file.lock()

    assert not wallet_file.is_unlocked
    # parameters of the key derivation are read from the file
    assert WalletFile(wallet_file.path).unlock(PASSWORD).entries == wallet.entries


def test_file_is_encrypted_and_private(wallet_file):
    wallet = wallet_file.create(PASSWORD)
    wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    wallet_file.save(wallet)

    data = read(wallet_file.path)
    assert data.startswith(b'MCWALLET\x01')
    assert BTC_WIF.encode() not in data
    assert b'Savings' not in data
    assert stat.S_IMODE(os.stat(wallet_file.path).st_mode) == 0o600
    assert not os.path.exists(wallet_file.path + '.tmp')


def test_create_does_not_overwrite_existing_file(wallet_file):
    wallet_file.create(PASSWORD)

    with pytest.raises(WalletError, match='already exists'):
        WalletFile(wallet_file.path).create(PASSWORD)


def test_create_requires_long_password(wallet_file):
    with pytest.raises(ValueError, match='at least 10 characters'):
        wallet_file.create('short')

    assert not wallet_file.exists()


def test_create_makes_private_directory(tmp_path):
    path = tmp_path / 'new' / 'wallet.mcw'

    WalletFile(str(path), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN).create(
        PASSWORD
    )

    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700


def test_unlock_with_wrong_password(wallet_file):
    wallet_file.create(PASSWORD)

    with pytest.raises(WalletError, match=WRONG_PASSWORD):
        WalletFile(wallet_file.path).unlock('wrong password')


def test_password_is_normalized(wallet_file):
    wallet_file.create(unicodedata.normalize('NFC', 'zażółć gęślą jaźń'))

    wallet = WalletFile(wallet_file.path).unlock(unicodedata.normalize('NFD', 'zażółć gęślą jaźń'))

    assert wallet.entries == []


def test_save_uses_new_nonce(wallet_file):
    wallet = wallet_file.create(PASSWORD)
    first = read(wallet_file.path)

    wallet_file.save(wallet)

    second = read(wallet_file.path)
    assert first[:41] == second[:41]  # magic, version, parameters and salt
    assert first[41:HEADER_SIZE] != second[41:HEADER_SIZE]


@pytest.mark.parametrize('offset', [0, 8, 16, 24, 25, 41, HEADER_SIZE, -1])
def test_unlock_detects_modification(wallet_file, offset):
    wallet_file.create(PASSWORD)
    data = bytearray(read(wallet_file.path))
    data[offset] ^= 1
    with open(wallet_file.path, 'wb') as file:
        file.write(data)

    with pytest.raises(WalletError):
        WalletFile(wallet_file.path).unlock(PASSWORD)


def test_unlock_unsupported_file(tmp_path):
    path = tmp_path / 'wallet.mcw'
    path.write_bytes(b'not a wallet')

    with pytest.raises(WalletError, match=UNSUPPORTED_FORMAT):
        WalletFile(str(path)).unlock(PASSWORD)


def test_verify_password(wallet_file):
    wallet_file.create(PASSWORD)

    assert wallet_file.verify_password(PASSWORD)
    assert not wallet_file.verify_password('wrong password')


def test_change_password(wallet_file):
    wallet = wallet_file.create(PASSWORD)
    wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    wallet_file.save(wallet)
    salt = read(wallet_file.path)[25:41]

    wallet_file.change_password(PASSWORD, NEW_PASSWORD)

    assert read(wallet_file.path)[25:41] != salt
    with pytest.raises(WalletError):
        WalletFile(wallet_file.path).unlock(PASSWORD)
    assert WalletFile(wallet_file.path).unlock(NEW_PASSWORD).entries == wallet.entries
    wallet_file.save(wallet)  # the new key is used for next saves
    assert WalletFile(wallet_file.path).unlock(NEW_PASSWORD).entries == wallet.entries


def test_change_password_with_wrong_old_password(wallet_file):
    wallet_file.create(PASSWORD)

    with pytest.raises(WalletError):
        wallet_file.change_password('wrong password', NEW_PASSWORD)

    assert WalletFile(wallet_file.path).unlock(PASSWORD).entries == []


def test_locked_wallet_cannot_be_saved(wallet_file):
    wallet = wallet_file.create(PASSWORD)
    wallet_file.lock()

    with pytest.raises(WalletError, match='locked'):
        wallet_file.save(wallet)
