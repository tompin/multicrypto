import pytest
import string

from multicrypto.ripemd160 import ripemd160


ripemd160_string_test_data = [
    # Basic string hashing
    ('', '9c1185a5c5e9fc54612808977ee8f548b2258d31'),
    ('\n', 'c0da025038ed83c687ddc430da9846ecb97f3998'),
    (' ', 'ac53a3aea6835b5ec12054e12d41d392e9d57b72'),
    ('Hello world', 'dbea7bd24eef40a2e79387542e36dd408b77b21a'),
    ('0123456789', 'a1a922b488e74b095c32dd2eb0170654944d1225'),
    ('ąóęłśćżźĄÓŁŃŚĆŹŻĘ', '5d2d2be5726dbc9f0e7d610bc586bcf5fa6edd88'),
    (
        '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&()*+,-./:;<=>?@[]^_`{|}~',
        '55187f1b3140f0a83e4befce2db95bf1efafac57',
    ),  # noqa
    ('a' * 200, '2a5b424394c0fce2665d4e0b077e998d2d62160a'),
    ('xyz' * 1000, '42af7e2dedfaaed455be118926007d6b26e2da2c'),
]


@pytest.mark.parametrize("data, ripemd160_hash_value", ripemd160_string_test_data)
def test_ripemd160(data, ripemd160_hash_value):
    assert ripemd160(data.encode()).hex() == ripemd160_hash_value
