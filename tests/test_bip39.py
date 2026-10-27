import json
import unicodedata
from pathlib import Path

import pytest

from multicrypto.bip32 import master_key_from_seed
from multicrypto.bip39 import (
    entropy_to_mnemonic,
    generate_mnemonic,
    get_wordlist,
    mnemonic_to_seed,
    normalize_mnemonic,
    validate_mnemonic,
)

VECTORS = json.loads((Path(__file__).parent / 'data' / 'bip39_vectors.json').read_text())
MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])


@pytest.mark.parametrize('entropy, mnemonic, seed, xprv', VECTORS)
def test_trezor_vectors(entropy, mnemonic, seed, xprv):
    assert entropy_to_mnemonic(bytes.fromhex(entropy)) == mnemonic
    validate_mnemonic(mnemonic)
    assert mnemonic_to_seed(mnemonic, 'TREZOR').hex() == seed
    assert master_key_from_seed(bytes.fromhex(seed)).xprv() == xprv


def test_wordlist():
    words = get_wordlist()
    assert len(words) == 2048
    assert (words[0], words[-1]) == ('abandon', 'zoo')


def test_generate_mnemonic():
    mnemonic = generate_mnemonic()

    assert len(mnemonic.split()) == 24
    validate_mnemonic(mnemonic)
    assert generate_mnemonic() != mnemonic
    assert len(generate_mnemonic(128).split()) == 12


def test_entropy_must_have_valid_length():
    with pytest.raises(ValueError, match='Entropy must have'):
        entropy_to_mnemonic(bytes(15))


@pytest.mark.parametrize(
    'mnemonic, message',
    [
        (' '.join(['abandon'] * 12), 'checksum'),
        (' '.join(['abandon'] * 11), 'must have 12, 15, 18, 21 or 24 words, not 11'),
        (' '.join(['abandon'] * 10 + ['abandonn', 'about']), 'Word 11 "abandonn"'),
        ('', 'not 0'),
    ],
)
def test_validate_mnemonic_errors(mnemonic, message):
    with pytest.raises(ValueError, match=message):
        validate_mnemonic(mnemonic)


def test_mnemonic_is_normalized():
    messy = '  ABANDON' + ' abandon' * 10 + '\n about '

    assert normalize_mnemonic(messy) == MNEMONIC
    validate_mnemonic(messy)
    assert mnemonic_to_seed(messy, 'TREZOR') == mnemonic_to_seed(MNEMONIC, 'TREZOR')


def test_passphrase_is_normalized():
    composed = unicodedata.normalize('NFC', 'zażółć')
    decomposed = unicodedata.normalize('NFD', 'zażółć')

    assert mnemonic_to_seed(MNEMONIC, composed) == mnemonic_to_seed(MNEMONIC, decomposed)
    assert mnemonic_to_seed(MNEMONIC, composed) != mnemonic_to_seed(MNEMONIC, '')
