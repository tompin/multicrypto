import pytest

from multicrypto.bip32 import HARDENED, master_key_from_seed, parse_path

# Test vectors 1-4 from BIP-32
VECTORS = [
    (
        '000102030405060708090a0b0c0d0e0f',
        [
            (
                'm',
                'xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi',
            ),
            (
                "m/0'",
                'xprv9uHRZZhk6KAJC1avXpDAp4MDc3sQKNxDiPvvkX8Br5ngLNv1TxvUxt4cV1rGL5hj6KCesnDYUhd7oWgT11eZG7XnxHrnYeSvkzY7d2bhkJ7',
            ),
            (
                "m/0'/1",
                'xprv9wTYmMFdV23N2TdNG573QoEsfRrWKQgWeibmLntzniatZvR9BmLnvSxqu53Kw1UmYPxLgboyZQaXwTCg8MSY3H2EU4pWcQDnRnrVA1xe8fs',
            ),
            (
                "m/0'/1/2'",
                'xprv9z4pot5VBttmtdRTWfWQmoH1taj2axGVzFqSb8C9xaxKymcFzXBDptWmT7FwuEzG3ryjH4ktypQSAewRiNMjANTtpgP4mLTj34bhnZX7UiM',
            ),
            (
                "m/0'/1/2'/2",
                'xprvA2JDeKCSNNZky6uBCviVfJSKyQ1mDYahRjijr5idH2WwLsEd4Hsb2Tyh8RfQMuPh7f7RtyzTtdrbdqqsunu5Mm3wDvUAKRHSC34sJ7in334',
            ),
            (
                "m/0'/1/2'/2/1000000000",
                'xprvA41z7zogVVwxVSgdKUHDy1SKmdb533PjDz7J6N6mV6uS3ze1ai8FHa8kmHScGpWmj4WggLyQjgPie1rFSruoUihUZREPSL39UNdE3BBDu76',
            ),
        ],
    ),
    (
        'fffcf9f6f3f0edeae7e4e1dedbd8d5d2cfccc9c6c3c0bdbab7b4b1aeaba8a5a29f9c999693908d8a8784817e7b7875726f6c696663605d5a5754514e4b484542',
        [
            (
                'm',
                'xprv9s21ZrQH143K31xYSDQpPDxsXRTUcvj2iNHm5NUtrGiGG5e2DtALGdso3pGz6ssrdK4PFmM8NSpSBHNqPqm55Qn3LqFtT2emdEXVYsCzC2U',
            ),
            (
                'm/0',
                'xprv9vHkqa6EV4sPZHYqZznhT2NPtPCjKuDKGY38FBWLvgaDx45zo9WQRUT3dKYnjwih2yJD9mkrocEZXo1ex8G81dwSM1fwqWpWkeS3v86pgKt',
            ),
            (
                "m/0/2147483647'",
                'xprv9wSp6B7kry3Vj9m1zSnLvN3xH8RdsPP1Mh7fAaR7aRLcQMKTR2vidYEeEg2mUCTAwCd6vnxVrcjfy2kRgVsFawNzmjuHc2YmYRmagcEPdU9',
            ),
            (
                "m/0/2147483647'/1",
                'xprv9zFnWC6h2cLgpmSA46vutJzBcfJ8yaJGg8cX1e5StJh45BBciYTRXSd25UEPVuesF9yog62tGAQtHjXajPPdbRCHuWS6T8XA2ECKADdw4Ef',
            ),
            (
                "m/0/2147483647'/1/2147483646'",
                'xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc',
            ),
            (
                "m/0/2147483647'/1/2147483646'/2",
                'xprvA2nrNbFZABcdryreWet9Ea4LvTJcGsqrMzxHx98MMrotbir7yrKCEXw7nadnHM8Dq38EGfSh6dqA9QWTyefMLEcBYJUuekgW4BYPJcr9E7j',
            ),
        ],
    ),
    (
        '4b381541583be4423346c643850da4b320e46a87ae3d2a4e6da11eba819cd4acba45d239319ac14f863b8d5ab5a0d0c64d2e8a1e7d1457df2e5a3c51c73235be',
        [
            (
                'm',
                'xprv9s21ZrQH143K25QhxbucbDDuQ4naNntJRi4KUfWT7xo4EKsHt2QJDu7KXp1A3u7Bi1j8ph3EGsZ9Xvz9dGuVrtHHs7pXeTzjuxBrCmmhgC6',
            ),
            (
                "m/0'",
                'xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L',
            ),
        ],
    ),
    (
        '3ddd5602285899a946114506157c7997e5444528f3003f6134712147db19b678',
        [
            (
                'm',
                'xprv9s21ZrQH143K48vGoLGRPxgo2JNkJ3J3fqkirQC2zVdk5Dgd5w14S7fRDyHH4dWNHUgkvsvNDCkvAwcSHNAQwhwgNMgZhLtQC63zxwhQmRv',
            ),
            (
                "m/0'",
                'xprv9vB7xEWwNp9kh1wQRfCCQMnZUEG21LpbR9NPCNN1dwhiZkjjeGRnaALmPXCX7SgjFTiCTT6bXes17boXtjq3xLpcDjzEuGLQBM5ohqkao9G',
            ),
            (
                "m/0'/1'",
                'xprv9xJocDuwtYCMNAo3Zw76WENQeAS6WGXQ55RCy7tDJ8oALr4FWkuVoHJeHVAcAqiZLE7Je3vZJHxspZdFHfnBEjHqU5hG1Jaj32dVoS6XLT1',
            ),
        ],
    ),
]


@pytest.mark.parametrize(
    'seed, path, xprv', [(seed, path, xprv) for seed, keys in VECTORS for path, xprv in keys]
)
def test_bip32_vectors(seed, path, xprv):
    assert master_key_from_seed(bytes.fromhex(seed)).derive_path(path).xprv() == xprv


@pytest.mark.parametrize(
    'path, indexes',
    [
        ('m', []),
        ("m/0'/1h/2H/3", [HARDENED, HARDENED + 1, HARDENED + 2, 3]),
        (" m/84'/0'/0'/0/5 ", [HARDENED + 84, HARDENED, HARDENED, 0, 5]),
    ],
)
def test_parse_path(path, indexes):
    assert parse_path(path) == indexes


@pytest.mark.parametrize('path', ['', '0/1', 'm/', 'm/x', 'm/-1', f'm/{HARDENED}', "m/1''", 'm/١'])
def test_parse_path_errors(path):
    with pytest.raises(ValueError, match='path'):
        parse_path(path)


def test_derive_child_rejects_index_out_of_range():
    with pytest.raises(ValueError):
        master_key_from_seed(bytes(16)).derive_child(2**32)


def test_master_key_requires_seed_length():
    with pytest.raises(ValueError, match='Seed must have'):
        master_key_from_seed(bytes(15))


def test_repr_does_not_contain_secrets():
    key = master_key_from_seed(bytes.fromhex(VECTORS[0][0]))

    text = repr(key)

    assert str(key.private_key) not in text
    assert key.chain_code.hex() not in text
