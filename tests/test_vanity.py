import pytest

from multicrypto.vanity import expected_attempts, pattern_hint, validate_vanity_pattern


@pytest.mark.parametrize(
    'coin_symbol, address_type, pattern, expected',
    [
        ('BTC', 'p2pkh', '1Ab', '1Ab'),
        ('BTC', 'p2sh-p2wpkh', '3Ab', '3Ab'),
        ('BTC', 'p2wpkh', 'BC1QXY', 'bc1qxy'),
        ('TBTC', 'p2wpkh', 'tb1qxy', 'tb1qxy'),
        ('ZEC', 'p2pkh', 't1Zx', 't1Zx'),
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
        ('ZEC', 'p2pkh', 't1Zx', 58**2),
    ],
)
def test_expected_attempts(coin_symbol, address_type, pattern, attempts):
    assert expected_attempts(pattern, coin_symbol, address_type) == attempts


def test_pattern_hint():
    assert pattern_hint('BTC', 'p2wpkh') == 'Addresses start with bc1q'
    assert pattern_hint('BTC', 'p2pkh') == 'Addresses are from 1111… to 1QLb…'
