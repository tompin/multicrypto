"""Hierarchical deterministic wallets (BIP-32): derivation of private keys on secp256k1."""

import hashlib
import hmac
from dataclasses import dataclass, field
from functools import cached_property
from typing import List

from multicrypto.base58 import bytes_to_base58
from multicrypto.ellipticcurve import secp256k1
from multicrypto.utils import double_sha256, encode_point, hash160

HARDENED = 0x80000000
XPRV_VERSION = bytes.fromhex('0488ade4')


@dataclass(frozen=True)
class ExtendedKey:
    """Extended private key: the private key with the chain code and its position in the tree."""

    private_key: int = field(repr=False)
    chain_code: bytes = field(repr=False)
    depth: int = 0
    parent_fingerprint: bytes = bytes(4)
    child_number: int = 0

    @cached_property
    def public_key_bytes(self) -> bytes:
        return encode_point(secp256k1.G * self.private_key, compressed=True)

    @property
    def fingerprint(self) -> bytes:
        return hash160(self.public_key_bytes)[:4]

    def derive_child(self, index: int) -> 'ExtendedKey':
        """Derive child key, indexes from HARDENED (2^31) give hardened keys."""
        if not 0 <= index < 2**32:
            raise ValueError(f'Child index {index} out of range')
        while True:
            if index >= HARDENED:
                data = b'\x00' + self.private_key.to_bytes(32, 'big')
            else:
                data = self.public_key_bytes
            digest = hmac.new(
                self.chain_code, data + index.to_bytes(4, 'big'), hashlib.sha512
            ).digest()
            tweak = int.from_bytes(digest[:32], 'big')
            child_key = (tweak + self.private_key) % secp256k1.n
            if tweak < secp256k1.n and child_key:
                return ExtendedKey(child_key, digest[32:], self.depth + 1, self.fingerprint, index)
            # invalid key (probability below 2^-127), BIP-32 says to use the next index
            index += 1

    def derive_path(self, path: str) -> 'ExtendedKey':
        key = self
        for index in parse_path(path):
            key = key.derive_child(index)
        return key

    def xprv(self) -> str:
        """Serialize the key in the mainnet xprv format."""
        data = (
            XPRV_VERSION
            + bytes([self.depth])
            + self.parent_fingerprint
            + self.child_number.to_bytes(4, 'big')
            + self.chain_code
            + b'\x00'
            + self.private_key.to_bytes(32, 'big')
        )
        return bytes_to_base58(data + double_sha256(data).digest()[:4])


def master_key_from_seed(seed: bytes) -> ExtendedKey:
    if not 16 <= len(seed) <= 64:
        raise ValueError('Seed must have from 128 to 512 bits')
    digest = hmac.new(b'Bitcoin seed', seed, hashlib.sha512).digest()
    private_key = int.from_bytes(digest[:32], 'big')
    if not 0 < private_key < secp256k1.n:
        raise ValueError('Seed gives invalid master key, use another seed')
    return ExtendedKey(private_key, digest[32:])


def parse_path(path: str) -> List[int]:
    """Convert derivation path, e.g. m/84'/0'/0'/0/5 (' or h means hardened), to indexes."""
    parts = path.strip().split('/')
    if parts[0] != 'm':
        raise ValueError(f'Derivation path must start with m: {path}')
    indexes = []
    for part in parts[1:]:
        hardened = part.endswith(("'", 'h', 'H'))
        number = part[:-1] if hardened else part
        if not (number.isascii() and number.isdigit()) or int(number) >= HARDENED:
            raise ValueError(f'Incorrect derivation path {path}')
        indexes.append(int(number) + (HARDENED if hardened else 0))
    return indexes
