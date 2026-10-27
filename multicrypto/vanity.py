"""Searching for vanity addresses, which start with the given pattern, in many processes."""

import os

from multicrypto.address import get_address_range, validate_address_type, validate_pattern
from multicrypto.bech32 import CHARSET
from multicrypto.coins import P2PKH, P2SH_P2WPKH, P2WPKH, coins

VANITY_ADDRESS_TYPES = (P2PKH, P2SH_P2WPKH, P2WPKH)


def _bech32_start(coin) -> str:
    return f'{coin["bech32_hrp"]}1q'


def _base58_range(coin_symbol: str, address_type: str):
    key = 'script_prefix_bytes' if address_type == P2SH_P2WPKH else 'address_prefix_bytes'
    return get_address_range(coins[coin_symbol][key])


def validate_vanity_pattern(pattern: str, coin_symbol: str, address_type: str) -> str:
    """Check that an address of the type can start with the pattern, return the pattern
    (lowercase for bech32 addresses)."""
    if address_type not in VANITY_ADDRESS_TYPES:
        raise ValueError(
            f'Vanity addresses of type {address_type} are not supported, '
            f'choose one of {", ".join(VANITY_ADDRESS_TYPES)}'
        )
    coin = coins[coin_symbol]
    validate_address_type(address_type, coin)
    if address_type != P2WPKH:
        validate_pattern(pattern, coin_symbol, address_type == P2SH_P2WPKH)
        return pattern
    pattern = pattern.lower()
    start = _bech32_start(coin)
    if not pattern.startswith(start):
        raise ValueError(f'Pattern must start with {start}')
    for character in pattern[len(start) :]:
        if character not in CHARSET:
            raise ValueError(
                f'Character {character} is not used in bech32 addresses '
                f'(the characters are {"".join(sorted(CHARSET))})'
            )
    return pattern


def expected_attempts(pattern: str, coin_symbol: str, address_type: str) -> int:
    """Average number of addresses checked before one starts with the pattern."""
    if address_type == P2WPKH:
        return 32 ** max(0, len(pattern) - len(_bech32_start(coins[coin_symbol])))
    fixed = len(os.path.commonprefix(_base58_range(coin_symbol, address_type)))
    return 58 ** max(0, len(pattern) - fixed)


def pattern_hint(coin_symbol: str, address_type: str) -> str:
    if address_type == P2WPKH:
        return f'Addresses start with {_bech32_start(coins[coin_symbol])}'
    start_address, end_address = _base58_range(coin_symbol, address_type)
    return f'Addresses are from {start_address[:4]}… to {end_address[:4]}…'
