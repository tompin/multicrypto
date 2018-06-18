import random

import pytest

from multicrypto.address import get_address_range
from multicrypto.base58 import base58
from multicrypto.coins import coins
from multicrypto.commands.genaddress import generate_address


class SetMock:
    def __init__(self, iterations=50000000):
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
    length = 3
    for i in range(length):
        while True:
            new_prefix = prefix + random.choice(base58)
            if (start_address <= new_prefix or start_address[:i + 2] == new_prefix) \
                    and new_prefix <= end_address:
                prefix = new_prefix
                break
    return prefix


random_test_data = [(coin_settings, get_prefix_in_range(coin_settings['address_prefix_bytes']))
                    for coin_settings in coins.values()]


@pytest.mark.parametrize("coin_settings,pattern", random_test_data)
def test_random_generate_address(coin_settings, pattern):
    address = generate_address(
        worker_num=0,
        coin_settings=coin_settings,
        pattern=pattern,
        compressed=True,
        segwit=False,
        found=SetMock(),
        quit=SetMock())

    assert address[:len(pattern)] == pattern
