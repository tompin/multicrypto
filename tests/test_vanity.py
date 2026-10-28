import time

import pytest

from multicrypto.address import (
    convert_private_key_to_coin_address,
    get_private_key_from_wif_format,
)
from multicrypto.coins import coins
from multicrypto.vanity import (
    VanitySearch,
    expected_attempts,
    find_address,
    pattern_hint,
    validate_vanity_pattern,
)


@pytest.mark.parametrize(
    'coin_symbol, address_type, pattern, expected',
    [
        ('BTC', 'p2pkh', '1Ab', '1Ab'),
        ('BTC', 'p2sh-p2wpkh', '3Ab', '3Ab'),
        ('BTC', 'p2wpkh', 'BC1QXY', 'bc1qxy'),
        ('TBTC', 'p2wpkh', 'tb1qxy', 'tb1qxy'),
        ('DOGE', 'p2pkh', 'DAb', 'DAb'),
    ],
)
def test_validate_vanity_pattern(coin_symbol, address_type, pattern, expected):
    assert validate_vanity_pattern(pattern, coin_symbol, address_type) == expected


@pytest.mark.parametrize(
    'coin_symbol, address_type, pattern, error',
    [
        ('BTC', 'p2pkh', '2Ab', 'Impossible prefix'),
        ('BTC', 'p2pkh', '1Ab0', 'not allowed characters: 0'),
        ('BTC', 'p2wpkh', 'bc1pxy', 'must start with bc1q'),
        ('BTC', 'p2wpkh', 'bc1qab', 'Character b is not used in bech32 addresses'),
        ('DOGE', 'p2wpkh', 'doge', 'not supported for dogecoin'),
        ('BTC', 'p2tr', 'bc1p', 'Vanity addresses of type p2tr are not supported'),
    ],
)
def test_validate_vanity_pattern_errors(coin_symbol, address_type, pattern, error):
    with pytest.raises(ValueError, match=error):
        validate_vanity_pattern(pattern, coin_symbol, address_type)


@pytest.mark.parametrize(
    'coin_symbol, address_type, pattern, attempts',
    [
        ('BTC', 'p2pkh', '1Ab', 58**2),
        ('BTC', 'p2pkh', '1', 1),
        ('BTC', 'p2sh-p2wpkh', '3A', 58),
        ('BTC', 'p2wpkh', 'bc1qxy', 32**2),
        ('DOGE', 'p2pkh', 'DAb', 58**2),
    ],
)
def test_expected_attempts(coin_symbol, address_type, pattern, attempts):
    assert expected_attempts(pattern, coin_symbol, address_type) == attempts


def test_pattern_hint():
    assert pattern_hint('BTC', 'p2wpkh') == 'Addresses start with bc1q'
    assert pattern_hint('BTC', 'p2pkh') == 'Addresses are from 1111… to 1QLb…'


class StopAfter:
    """Stop event set after the given number of checks."""

    def __init__(self, checks):
        self.checks = checks

    def is_set(self):
        self.checks -= 1
        return self.checks < 0


def wif_address(coin_symbol, wif, address_type):
    private_key, compressed = get_private_key_from_wif_format(wif)
    return convert_private_key_to_coin_address(
        private_key, coins[coin_symbol], compressed, address_type
    )


@pytest.mark.parametrize(
    'coin_symbol, address_type, pattern',
    [
        ('BTC', 'p2pkh', '1A'),
        ('BTC', 'p2sh-p2wpkh', '3A'),
        ('BTC', 'p2wpkh', 'bc1qq'),
        ('DOGE', 'p2pkh', 'DA'),
    ],
)
def test_find_address(coin_symbol, address_type, pattern):
    address, wif = find_address(coin_symbol, address_type, pattern, True, StopAfter(10**6))

    assert address.startswith(pattern)
    assert wif_address(coin_symbol, wif, address_type) == address


def test_find_address_uncompressed_p2pkh():
    address, wif = find_address('BTC', 'p2pkh', '1A', False, StopAfter(10**6))

    assert wif.startswith('5')
    assert wif_address('BTC', wif, 'p2pkh') == address


def test_find_address_stops():
    assert find_address('BTC', 'p2wpkh', 'bc1qqqqqqqqqqq', True, StopAfter(2)) is None


def wait_for_result(search, seconds=60):
    deadline = time.monotonic() + seconds
    while search.result() is None:
        assert not search.failed
        assert time.monotonic() < deadline
        time.sleep(0.05)
    return search.result()


@pytest.mark.parametrize(
    'coin_symbol, address_type, pattern',
    [('BTC', 'p2pkh', '1A'), ('TBTC', 'p2wpkh', 'tb1qq')],
)
def test_vanity_search_in_process(coin_symbol, address_type, pattern):
    search = VanitySearch(coin_symbol, address_type, pattern, workers=1)
    search.start()
    try:
        address, wif = wait_for_result(search)
    finally:
        search.stop()

    assert address.startswith(pattern)
    assert wif_address(coin_symbol, wif, address_type) == address
    assert not search.running


def test_vanity_search_stop():
    search = VanitySearch('BTC', 'p2wpkh', 'bc1qqqqqqqqqqq', workers=2)
    search.start()
    deadline = time.monotonic() + 60
    while search.attempts == 0:
        assert time.monotonic() < deadline
        time.sleep(0.05)

    search.stop()

    assert search.result() is None
    assert not search.running
    assert not search.failed


def test_vanity_search_validates_input():
    with pytest.raises(ValueError, match='Impossible prefix'):
        VanitySearch('BTC', 'p2pkh', '2A', workers=1)
    with pytest.raises(ValueError, match='require compressed public key'):
        VanitySearch('BTC', 'p2wpkh', 'bc1q', workers=1, compressed=False)
