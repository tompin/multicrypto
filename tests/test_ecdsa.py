import pytest

from multicrypto.coins import coins
from multicrypto.ecdsa import add_magic_prefix

SIGNED_MESSAGE = b' Signed Message:\n'


def test_add_magic_prefix():
    assert add_magic_prefix('abc', coins['BTC']) == b'\x18Bitcoin Signed Message:\n\x03abc'


def test_add_magic_prefix_encodes_length_of_utf8_bytes_as_varint():
    message = 'ż' * 200  # 400 bytes in UTF-8

    assert add_magic_prefix(message, coins['BTC']) == (
        b'\x18Bitcoin Signed Message:\n' + b'\xfd\x90\x01' + message.encode()
    )


@pytest.mark.parametrize(
    'coin_symbol, name',
    [
        ('BTC', b'Bitcoin'),
        ('TBTC', b'Bitcoin'),
        ('TBCH', b'Bitcoin'),
        ('LTC', b'Litecoin'),
        ('TLTC', b'Litecoin'),
        ('BTG', b'Bitcoin Gold'),
        ('DASH', b'DarkCoin'),
        ('DOGE', b'Dogecoin'),
    ],
)
def test_message_prefix_of_coins(coin_symbol, name):
    prefix = name + SIGNED_MESSAGE

    assert add_magic_prefix('', coins[coin_symbol]) == bytes([len(prefix)]) + prefix + b'\x00'
