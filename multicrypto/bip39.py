"""Mnemonic code for generating deterministic keys (BIP-39), only the English wordlist."""

import hashlib
import secrets
import unicodedata
from functools import lru_cache
from importlib import resources
from typing import Dict, Tuple

PBKDF2_ROUNDS = 2048
WORD_COUNTS = (12, 15, 18, 21, 24)


@lru_cache(maxsize=None)
def get_wordlist() -> Tuple[str, ...]:
    words = resources.files('multicrypto').joinpath('bip39_english.txt').read_text().split()
    if len(words) != 2048:
        raise RuntimeError('BIP-39 wordlist must have 2048 words')
    return tuple(words)


@lru_cache(maxsize=None)
def get_word_indexes() -> Dict[str, int]:
    return {word: index for index, word in enumerate(get_wordlist())}


def normalize_mnemonic(mnemonic: str) -> str:
    return ' '.join(unicodedata.normalize('NFKD', mnemonic).lower().split())


def _checksum(entropy: bytes) -> int:
    checksum_bits = len(entropy) // 4
    return hashlib.sha256(entropy).digest()[0] >> (8 - checksum_bits)


def entropy_to_mnemonic(entropy: bytes) -> str:
    if len(entropy) not in (16, 20, 24, 28, 32):
        raise ValueError('Entropy must have 128, 160, 192, 224 or 256 bits')
    checksum_bits = len(entropy) // 4
    value = (int.from_bytes(entropy, 'big') << checksum_bits) | _checksum(entropy)
    word_count = (len(entropy) * 8 + checksum_bits) // 11
    words = get_wordlist()
    return ' '.join(words[(value >> (11 * i)) & 2047] for i in reversed(range(word_count)))


def generate_mnemonic(strength: int = 256) -> str:
    """Return new mnemonic with the given number of bits of entropy (24 words by default)."""
    return entropy_to_mnemonic(secrets.token_bytes(strength // 8))


def validate_mnemonic(mnemonic: str) -> None:
    """Check the words and the checksum, raise ValueError describing the problem."""
    words = normalize_mnemonic(mnemonic).split()
    if len(words) not in WORD_COUNTS:
        raise ValueError(f'Mnemonic must have 12, 15, 18, 21 or 24 words, not {len(words)}')
    indexes = get_word_indexes()
    value = 0
    for position, word in enumerate(words, start=1):
        if word not in indexes:
            raise ValueError(f'Word {position} "{word}" is not in the BIP-39 English wordlist')
        value = (value << 11) | indexes[word]
    checksum_bits = len(words) // 3
    entropy = (value >> checksum_bits).to_bytes(len(words) * 4 // 3, 'big')
    if _checksum(entropy) != value & ((1 << checksum_bits) - 1):
        raise ValueError('Incorrect mnemonic checksum, check the words and their order')


def mnemonic_to_seed(mnemonic: str, passphrase: str = '') -> bytes:
    salt = 'mnemonic' + unicodedata.normalize('NFKD', passphrase)
    return hashlib.pbkdf2_hmac(
        'sha512', normalize_mnemonic(mnemonic).encode(), salt.encode(), PBKDF2_ROUNDS
    )
