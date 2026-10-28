from base64 import b64decode, b64encode

import pytest

from multicrypto.address import (
    convert_private_key_to_coin_address,
    convert_private_key_to_wif_format,
)
from multicrypto.coins import coins
from multicrypto.ecdsa import add_magic_prefix, sign_message, verify_signature

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
        ('LTC', b'Litecoin'),
        ('TLTC', b'Litecoin'),
        ('DASH', b'DarkCoin'),
        ('DOGE', b'Dogecoin'),
    ],
)
def test_message_prefix_of_coins(coin_symbol, name):
    prefix = name + SIGNED_MESSAGE

    assert add_magic_prefix('', coins[coin_symbol]) == bytes([len(prefix)]) + prefix + b'\x00'


L4_WIF = 'L4rK1yDtCWekvXuE6oXD9jCYfFNV2cWRpVuPLBcCU2z8TrisoyY1'
L4_UNCOMPRESSED_WIF = '5KYZdUEo39z3FPrtuX2QbbwGnNP5zTd7yyr2SC1j299sBCnWjss'
MESSAGE = 'This is an example of a signed message.'
# signature from bitcoinjs-message README without the first character (header)
SIGNATURE_BODY = (
    '9L5yLFjti0QTHhPyFrZCT1V/MMnBtXKmoiKDZ78NDBjERki6ZTQZdSMCtkgoNmp17By9ItJr8o7ChX0XxY91nk='
)
ADDRESSES = {
    'p2pkh': '1F3sAm6ZtwLAUnj7d38pGFxtP3RVEvtsbV',
    'p2sh-p2wpkh': '3DnW8JGpPViEZdpqat8qky1zc26EKbXnmM',
    'p2wpkh': 'bc1qngw83fg8dz0k749cg7k3emc7v98wy0c74dlrkd',
}
HEADER_CHARACTERS = {'p2pkh': 'H', 'p2sh-p2wpkh': 'I', 'p2wpkh': 'J'}
FIRST_HEADERS = {'p2pkh': 31, 'p2sh-p2wpkh': 35, 'p2wpkh': 39}


@pytest.mark.parametrize('address_type', ADDRESSES)
def test_verify_bip137_vectors(address_type):
    signature = HEADER_CHARACTERS[address_type] + SIGNATURE_BODY

    assert verify_signature(coins['BTC'], MESSAGE, signature, ADDRESSES[address_type])


@pytest.mark.parametrize('address_type', ['p2sh-p2wpkh', 'p2wpkh'])
def test_verify_segwit_address_signed_with_p2pkh_header(address_type):
    # Electrum and Trezor sign messages of segwit addresses with P2PKH header
    assert verify_signature(coins['BTC'], MESSAGE, 'H' + SIGNATURE_BODY, ADDRESSES[address_type])


def test_verify_rejects_other_message_or_address():
    signature = 'J' + SIGNATURE_BODY

    assert not verify_signature(coins['BTC'], MESSAGE + '!', signature, ADDRESSES['p2wpkh'])
    assert not verify_signature(
        coins['BTC'], MESSAGE, signature, 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'
    )


def test_verify_old_ascii_signature():
    assert verify_signature(
        coins['BTC'],
        'Hello World!',
        'H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=',
        '1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi',
    )


def with_header(header):
    return b64encode(bytes([header]) + b64decode('H' + SIGNATURE_BODY)[1:]).decode()


@pytest.mark.parametrize(
    'signature, error',
    [
        ('not base64!', 'not correct base64'),
        ('SGVsbG8=', 'must have 65 bytes'),
        (with_header(26), 'Incorrect first byte of the signature: 26'),
        (with_header(43), 'Incorrect first byte of the signature: 43'),
    ],
)
def test_verify_incorrect_signature_format(signature, error):
    with pytest.raises(ValueError, match=error):
        verify_signature(coins['BTC'], MESSAGE, signature, ADDRESSES['p2pkh'])


@pytest.mark.parametrize(
    'coin_symbol, address_type',
    [
        ('BTC', 'p2pkh'),
        ('BTC', 'p2sh-p2wpkh'),
        ('BTC', 'p2wpkh'),
        ('LTC', 'p2wpkh'),
        ('TBTC', 'p2sh-p2wpkh'),
        ('DOGE', 'p2pkh'),
        ('DASH', 'p2pkh'),
    ],
)
@pytest.mark.parametrize('message', ['Hello World!', 'Zażółć gęślą jaźń', 'x' * 300])
def test_sign_and_verify(coin_symbol, address_type, message):
    coin = coins[coin_symbol]
    private_key = 0x1234567890ABCDEF1234567890ABCDEF
    wif = convert_private_key_to_wif_format(private_key, coin['secret_prefix_bytes'])
    address = convert_private_key_to_coin_address(private_key, coin, True, address_type)

    signature = sign_message(coin, message, wif, address_type).decode()

    assert b64decode(signature)[0] - FIRST_HEADERS[address_type] in range(4)
    assert verify_signature(coin, message, signature, address)


def test_sign_with_uncompressed_key():
    signature = sign_message(coins['BTC'], MESSAGE, L4_UNCOMPRESSED_WIF).decode()

    assert b64decode(signature)[0] in range(27, 31)
    assert verify_signature(coins['BTC'], MESSAGE, signature, '1HZwkjkeaoZfTSaJxDw6aKkxp45agDiEzN')
    # uncompressed key has no segwit addresses
    assert not verify_signature(coins['BTC'], MESSAGE, signature, ADDRESSES['p2wpkh'])


@pytest.mark.parametrize(
    'coin_symbol, wif, address_type, error',
    [
        ('BTC', L4_WIF, 'p2tr', 'Taproot addresses cannot sign messages'),
        ('BTC', L4_UNCOMPRESSED_WIF, 'p2wpkh', 'require compressed public key'),
        ('DOGE', L4_WIF, 'p2wpkh', 'not supported for dogecoin'),
    ],
)
def test_sign_errors(coin_symbol, wif, address_type, error):
    with pytest.raises(ValueError, match=error):
        sign_message(coins[coin_symbol], MESSAGE, wif, address_type)
