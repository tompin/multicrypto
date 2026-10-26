import pytest

from multicrypto.address import convert_private_key_to_wif_format
from multicrypto.ellipticcurve import secp256k1
from multicrypto.wallet import Wallet, WalletEntry, check_entry, generate_wif

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
