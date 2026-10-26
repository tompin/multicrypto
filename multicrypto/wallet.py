"""Wallet keeping private keys encrypted in a single file."""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import cached_property
from typing import Any, Dict, Iterable, List, Optional

from multicrypto.address import (
    convert_private_key_to_coin_address,
    convert_private_key_to_wif_format,
    get_private_key_from_wif_format,
    validate_address_type,
)
from multicrypto.base58 import BASE58_ALPHABET, base58_to_bytes
from multicrypto.coins import coins
from multicrypto.ellipticcurve import secp256k1
from multicrypto.utils import double_sha256


def get_coin(coin_symbol: str) -> Dict[str, Any]:
    if coin_symbol not in coins:
        raise ValueError(f'Unknown coin {coin_symbol}')
    return coins[coin_symbol]


def check_wif_private_key(wif_private_key: str, coin_symbol: str) -> None:
    """Check characters, checksum, coin prefix and range of the private key in WIF format."""
    if not wif_private_key or set(wif_private_key) - set(BASE58_ALPHABET):
        raise ValueError('Private key in WIF format can contain only base58 characters')
    data = base58_to_bytes(wif_private_key)
    payload, checksum = data[:-4], data[-4:]
    if len(data) < 5 or double_sha256(payload).digest()[:4] != checksum:
        raise ValueError('Incorrect checksum of the private key')
    prefix = get_coin(coin_symbol)['secret_prefix_bytes']
    if not payload.startswith(prefix):
        raise ValueError(f'Private key is not in WIF format of {coin_symbol}')
    key_bytes = payload[len(prefix) :]
    if len(key_bytes) == 33 and key_bytes[-1] == 1:  # flag of the compressed public key
        key_bytes = key_bytes[:-1]
    if len(key_bytes) != 32 or not 0 < int.from_bytes(key_bytes, 'big') < secp256k1.n:
        raise ValueError('Incorrect private key')


def check_entry(coin_symbol: str, wif_private_key: str, address_type: str) -> str:
    """Validate wallet entry data and return its address."""
    coin = get_coin(coin_symbol)
    validate_address_type(address_type, coin)
    check_wif_private_key(wif_private_key, coin_symbol)
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    return convert_private_key_to_coin_address(private_key, coin, compressed, address_type)


def generate_wif(coin_symbol: str, private_key: Optional[int] = None) -> str:
    """Return new random private key (or the given one) in WIF format with compressed public key."""
    if private_key is None:
        private_key = secp256k1.gen_private_key()
    return convert_private_key_to_wif_format(
        private_key, get_coin(coin_symbol)['secret_prefix_bytes']
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


@dataclass
class WalletEntry:
    """Private key used with the address of the given type of the coin."""

    label: str
    coin: str
    wif: str = field(repr=False)
    address_type: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created: str = field(default_factory=_now)

    @cached_property
    def address(self) -> str:
        private_key, compressed = get_private_key_from_wif_format(self.wif)
        return convert_private_key_to_coin_address(
            private_key, coins[self.coin], compressed, self.address_type
        )


class Wallet:
    """Decrypted content of the wallet file."""

    def __init__(self, entries: Iterable[WalletEntry] = ()):
        self.entries: List[WalletEntry] = list(entries)

    def get(self, entry_id: str) -> WalletEntry:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        raise KeyError(entry_id)

    def add_wif(
        self, label: str, coin_symbol: str, wif_private_key: str, address_type: str
    ) -> WalletEntry:
        """Add private key in WIF format, raise ValueError when it is incorrect or already added."""
        check_entry(coin_symbol, wif_private_key, address_type)
        for entry in self.entries:
            if (entry.coin, entry.wif, entry.address_type) == (
                coin_symbol,
                wif_private_key,
                address_type,
            ):
                raise ValueError(
                    f'Address {entry.address} is already in the wallet as "{entry.label}"'
                )
        entry = WalletEntry(label, coin_symbol, wif_private_key, address_type)
        self.entries.append(entry)
        return entry

    def remove(self, entry_id: str) -> None:
        self.entries.remove(self.get(entry_id))

    def to_json(self) -> bytes:
        return json.dumps({'entries': [asdict(entry) for entry in self.entries]}).encode()

    @classmethod
    def from_json(cls, data: bytes) -> 'Wallet':
        return cls(WalletEntry(**entry) for entry in json.loads(data)['entries'])
