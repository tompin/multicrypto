import pytest

from multicrypto.rlp import decode, encode

LOREM = b'Lorem ipsum dolor sit amet, consectetur adipisicing elit'

# Examples from https://ethereum.org/developers/docs/data-structures-and-encoding/rlp/
VECTORS = [
    (b'dog', '83646f67'),
    ([b'cat', b'dog'], 'c88363617483646f67'),
    (b'', '80'),
    ([], 'c0'),
    (b'\x00', '00'),
    (b'\x0f', '0f'),
    (b'\x04\x00', '820400'),
    ([[], [[]], [[], [[]]]], 'c7c0c1c0c3c0c1c0'),
    (LOREM, 'b838' + LOREM.hex()),
    ([LOREM] * 2, 'f874' + ('b838' + LOREM.hex()) * 2),
]


@pytest.mark.parametrize('item, encoded', VECTORS)
def test_encode(item, encoded):
    assert encode(item).hex() == encoded


@pytest.mark.parametrize('item, encoded', VECTORS)
def test_decode(item, encoded):
    assert decode(bytes.fromhex(encoded)) == item


@pytest.mark.parametrize(
    'value, encoded', [(0, '80'), (15, '0f'), (127, '7f'), (128, '8180'), (1024, '820400')]
)
def test_encode_integers_as_big_endian_bytes_without_leading_zeros(value, encoded):
    assert encode(value).hex() == encoded


def test_encode_long_string():
    data = b'a' * 1024

    assert encode(data) == b'\xb9\x04\x00' + data
    assert decode(encode(data)) == data


def test_encode_rejects_negative_integers():
    with pytest.raises(ValueError, match='negative'):
        encode(-1)


@pytest.mark.parametrize(
    'encoded, message',
    [
        ('', 'empty'),
        ('83646f', 'too short'),
        ('83646f6700', 'after the end'),
        ('8100', 'single byte'),
        ('b80a' + '00' * 10, 'long form'),
        ('c3836f', 'too short'),
    ],
)
def test_decode_rejects_incorrect_data(encoded, message):
    with pytest.raises(ValueError, match=message):
        decode(bytes.fromhex(encoded))
