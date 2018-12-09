import random

import pytest
from multicrypto.ellipticcurve import secp256k1

from multicrypto.utils import der_encode_signature, reverse_byte_hex, decode_point, encode_point, \
    int_to_varint_hex


def test_der_encode_signature():
    r_hex = '059c71db0d01d284fc4589c03b09947d21b98d7cefae614ac1039b6de0fa28ba'
    s_hex = '6cde9c0649fe2242b1dd90f40615e1bb247280b8f152c0ae9151b9c4d7abaf87'
    r = int(r_hex, 16)
    s = int(s_hex, 16)
    signature = (r, s)

    der_encoded_signature = der_encode_signature(signature)

    expected_signature = '30440220059c71db0d01d284fc4589c03b09947d21b98d7cefae614ac1039b6de0fa28b' \
                         'a02206cde9c0649fe2242b1dd90f40615e1bb247280b8f152c0ae9151b9c4d7abaf87'
    assert der_encoded_signature.hex() == expected_signature
    assert r_hex in der_encoded_signature.hex()
    assert s_hex in der_encoded_signature.hex()


hex_to_reverse_data = [
    ('', ''),
    ('0000', '0000'),
    ('491592c491bc5da61390bb49618719b1af4f1e2ef20e82c18e9f2be1ebadfcb2',
     'b2fcadebe12b9f8ec1820ef22e1e4fafb119876149bb9013a65dbc91c4921549'),
    ('774aca1b9bd505e46d766e4c9246b588d5973684e9d73ed1f866c157d9890f90',
     '900f89d957c166f8d13ed7e9843697d588b546924c6e766de405d59b1bca4a77'),
    ('c43892797f71459b7117da6df58338c6b0a6d60416a7c37a63bb25b6e3fd548e',
     '8e54fde3b625bb637ac3a71604d6a6b0c63883f56dda17719b45717f799238c4'),
    ('00009230203984acf342fd23999efacbd43445384889999f9999aaaabbccccdd',
     'ddccccbbaaaa99999f998948384534d4cbfa9e9923fd42f3ac84392030920000')
]


@pytest.mark.parametrize("hex_str,reversed_hex_str", hex_to_reverse_data)
def test_reverse_byte_hex(hex_str, reversed_hex_str):
    assert reverse_byte_hex(hex_str) == reversed_hex_str


def test_encode_decode_points():
    G = secp256k1.G
    N = secp256k1.n
    random_point = G * random.randint(1, N)
    for i in range(100):
        assert random_point == decode_point(encode_point(
            random_point, compressed=random.choice([True, False]))
        )
        assert random_point == decode_point(encode_point(
            random_point, compressed=random.choice([True, False])).hex()
        )
        random_point *= 10


integer_data = [(0x12, '12'),
                (0x3412, 'fd1234'),
                (0x78563412, 'fe12345678'),
                (0xefcdab9078563412, 'ff1234567890abcdef')]


@pytest.mark.parametrize("integer, varint_hex", integer_data)
def test_int_to_varint_hex(integer, varint_hex):
    assert int_to_varint_hex(integer) == varint_hex
