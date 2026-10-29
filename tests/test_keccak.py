import hashlib

import pytest

from multicrypto.keccak import SHA3_PADDING, keccak256, sponge


@pytest.mark.parametrize(
    'data, digest',
    [
        (b'', 'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470'),
        (b'abc', '4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45'),
    ],
)
def test_keccak256(data, digest):
    assert keccak256(data).hex() == digest


@pytest.mark.parametrize('size', [0, 1, 55, 135, 136, 137, 271, 272, 273, 1000])
def test_sponge_with_sha3_padding_is_sha3_256(size):
    # Keccak-256 differs from SHA3-256 only in the padding, so SHA3-256 from hashlib checks
    # the permutation and absorbing of the data in many blocks
    data = bytes(range(256)) * 4
    data = data[:size]

    assert sponge(data, SHA3_PADDING) == hashlib.sha3_256(data).digest()


def test_keccak256_differs_from_sha3_256():
    assert keccak256(b'abc') != hashlib.sha3_256(b'abc').digest()
