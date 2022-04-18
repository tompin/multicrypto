import os
import random
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from multicrypto.address import get_address_range
from multicrypto.base58 import base58
from multicrypto.coins import coins
from multicrypto.commands.genaddress import generate_address, main
from multicrypto.consts import OP_EQUAL, OP_16, OP_ADD, OP_15


class SetMock:
    def __init__(self, iterations=5000000):
        self.current = 0
        self.iterations = iterations

    def is_set(self):
        self.current += 1
        if self.current > self.iterations:
            return True
        return False

    def set(self):
        self.current = self.iterations


def get_prefix_in_range(address_prefix_bytes):
    start_address, end_address = get_address_range(address_prefix_bytes)
    prefix = start_address[:1]
    length = 2
    for i in range(length):
        while True:
            new_prefix = prefix + random.choice(base58)
            if (
                start_address <= new_prefix or start_address[: i + 2] == new_prefix
            ) and new_prefix <= end_address:
                prefix = new_prefix
                break
    return prefix


random_test_data = [
    (coin_settings, get_prefix_in_range(coin_settings['address_prefix_bytes']))
    for coin_settings in coins.values()
]


@pytest.mark.parametrize("coin_settings,pattern", random_test_data)
def test_random_generate_address(tmpdir, coin_settings, pattern):
    out_dir = tmpdir.strpath
    address, private_key = generate_address(
        worker_num=0,
        coin_settings=coin_settings,
        pattern=pattern,
        compressed=True,
        segwit=False,
        out_dir=out_dir,
        found=SetMock(),
        quit=SetMock(),
    )

    assert address[: len(pattern)] == pattern
    assert os.path.isfile(os.path.join(out_dir, address + '.png'))
    assert os.path.isfile(os.path.join(out_dir, address + '_private_key.png'))


@patch.object(sys, 'argv', ['', '-s', 'TBTC', '-i', (OP_15 + OP_ADD + OP_16 + OP_EQUAL).hex()])
@patch('sys.stdout', new_callable=StringIO)
def test_custom_p2sh_address_success(sys_stdout):
    main()

    res = '2NBqJfmzsEbbT1YFyCjdU4KYXQajLffLBLM\n'

    assert sys_stdout.getvalue() == res
