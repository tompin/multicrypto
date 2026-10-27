import os
import random
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from multicrypto.address import (
    convert_private_key_to_coin_address,
    get_address_range,
    get_private_key_from_wif_format,
)
from multicrypto.base58 import BASE58_ALPHABET
from multicrypto.coins import coins
from multicrypto.commands.genaddress import main
from multicrypto.consts import OP_EQUAL, OP_16, OP_ADD, OP_15
from multicrypto.vanity import find_address


class StopAfter:
    def __init__(self, checks):
        self.checks = checks

    def is_set(self):
        self.checks -= 1
        return self.checks < 0


def get_prefix_in_range(address_prefix_bytes):
    start_address, end_address = get_address_range(address_prefix_bytes)
    prefix = start_address[:1]
    length = 2
    for i in range(length):
        while True:
            new_prefix = prefix + random.choice(BASE58_ALPHABET)
            if (
                start_address <= new_prefix or start_address[: i + 2] == new_prefix
            ) and new_prefix <= end_address:
                prefix = new_prefix
                break
    return prefix


random_test_data = [
    (coin_symbol, get_prefix_in_range(coin['address_prefix_bytes']))
    for coin_symbol, coin in coins.items()
]


@pytest.mark.parametrize('coin_symbol, pattern', random_test_data)
def test_random_find_address(coin_symbol, pattern):
    address, wif = find_address(coin_symbol, 'p2pkh', pattern, True, StopAfter(10**6))

    private_key, compressed = get_private_key_from_wif_format(wif)
    assert address[: len(pattern)] == pattern
    assert (
        convert_private_key_to_coin_address(private_key, coins[coin_symbol], compressed) == address
    )


@patch('sys.stdout', new_callable=StringIO)
def test_genaddress_saves_qr_codes(sys_stdout, tmpdir):
    out_dir = tmpdir.strpath
    with patch.object(sys, 'argv', ['', '-s', 'BTC', '-p', '1A', '-d', out_dir]):
        main()

    address = sys_stdout.getvalue().split('Address: ')[1].split('\n')[0]
    assert address.startswith('1A')
    assert os.path.isfile(os.path.join(out_dir, address + '.png'))
    assert os.path.isfile(os.path.join(out_dir, address + '_private_key.png'))


@patch.object(sys, 'argv', ['', '-s', 'BTC', '-p', 'bc1qq', '-t', 'p2wpkh', '-c', '2'])
@patch('sys.stdout', new_callable=StringIO)
def test_genaddress_p2wpkh(sys_stdout):
    main()

    output = sys_stdout.getvalue()
    assert 'using 2 workers' in output
    assert '\nAddress: bc1qq' in output
    assert '\nPrivate key: ' in output


@patch.object(sys, 'argv', ['', '-s', 'TBTC', '-i', (OP_15 + OP_ADD + OP_16 + OP_EQUAL).hex()])
@patch('sys.stdout', new_callable=StringIO)
def test_custom_p2sh_address_success(sys_stdout):
    main()

    res = '2NBqJfmzsEbbT1YFyCjdU4KYXQajLffLBLM\n'

    assert sys_stdout.getvalue() == res


@patch.object(sys, 'argv', ['', '-s', 'ZEC', '-p', 't3', '-w'])
@patch('sys.stdout', new_callable=StringIO)
def test_segwit_address_not_supported(sys_stdout, caplog):
    main()

    assert 'Address type p2sh-p2wpkh is not supported for zcash' in caplog.text
    assert 'Address:' not in sys_stdout.getvalue()
