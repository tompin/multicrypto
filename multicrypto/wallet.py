"""Wallet keeping private keys encrypted in a single file.

The file starts with the header (integers are big-endian)::

    magic (8 bytes) | version (1) | opslimit (8) | memlimit (8) | salt (16) | nonce (24)

followed by the wallet content (JSON) encrypted with XChaCha20-Poly1305. The key is derived from
the password using Argon2id with the parameters and salt from the header. The whole header is
authenticated as additional data, so it cannot be modified without detection.
"""

import json
import os
import struct
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from functools import cached_property
from hmac import compare_digest
from typing import Any, Dict, Iterable, List, Optional

from nacl import bindings, pwhash
from nacl.exceptions import CryptoError

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

MAGIC = b'MCWALLET'
VERSION = 1
HEADER_FORMAT = '>8sBQQ16s24s'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
KEY_SIZE = bindings.crypto_aead_xchacha20poly1305_ietf_KEYBYTES
NONCE_SIZE = bindings.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES
TAG_SIZE = bindings.crypto_aead_xchacha20poly1305_ietf_ABYTES
DEFAULT_PATH = os.path.join(os.path.expanduser('~'), '.multicrypto', 'wallet.mcw')
DEFAULT_OPSLIMIT = pwhash.argon2id.OPSLIMIT_MODERATE
DEFAULT_MEMLIMIT = pwhash.argon2id.MEMLIMIT_MODERATE
MIN_PASSWORD_LENGTH = 10

WRONG_PASSWORD = 'Wrong password or damaged wallet file'
UNSUPPORTED_FORMAT = 'Unsupported format of the wallet file'


class WalletError(Exception):
    """Raised when the wallet file cannot be decrypted, created or saved."""


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


def check_new_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f'Password must have at least {MIN_PASSWORD_LENGTH} characters')


def derive_key(password: str, salt: bytes, opslimit: int, memlimit: int) -> bytes:
    """Derive the encryption key from the password, which is normalized, so the same password
    entered in different ways (e.g. composed or decomposed accented letters) gives the same key."""
    password_bytes = unicodedata.normalize('NFKC', password).encode()
    return pwhash.argon2id.kdf(KEY_SIZE, password_bytes, salt, opslimit=opslimit, memlimit=memlimit)


class WalletFile:
    """Encrypted wallet file, the key derived from the password is kept until it is locked."""

    def __init__(
        self,
        path: str = DEFAULT_PATH,
        opslimit: int = DEFAULT_OPSLIMIT,
        memlimit: int = DEFAULT_MEMLIMIT,
    ):
        self.path = path
        self.opslimit = opslimit
        self.memlimit = memlimit
        self._salt: Optional[bytes] = None
        self._key: Optional[bytes] = None

    @property
    def is_unlocked(self) -> bool:
        return self._key is not None

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def create(self, password: str) -> Wallet:
        """Create new empty wallet file encrypted with the key derived from the password."""
        check_new_password(password)
        if self.exists():
            raise WalletError(f'Wallet file {self.path} already exists')
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), mode=0o700, exist_ok=True)
        self._salt = os.urandom(pwhash.argon2id.SALTBYTES)
        self._key = derive_key(password, self._salt, self.opslimit, self.memlimit)
        wallet = Wallet()
        self.save(wallet)
        return wallet

    def unlock(self, password: str) -> Wallet:
        """Decrypt the wallet file, raise WalletError when the password is wrong."""
        with open(self.path, 'rb') as file:
            data = file.read()
        if len(data) < HEADER_SIZE + TAG_SIZE:
            raise WalletError(UNSUPPORTED_FORMAT)
        header = data[:HEADER_SIZE]
        magic, version, opslimit, memlimit, salt, nonce = struct.unpack(HEADER_FORMAT, header)
        if (
            magic != MAGIC
            or version != VERSION
            or not pwhash.argon2id.OPSLIMIT_MIN <= opslimit <= pwhash.argon2id.OPSLIMIT_MAX
            or not pwhash.argon2id.MEMLIMIT_MIN <= memlimit <= pwhash.argon2id.MEMLIMIT_SENSITIVE
        ):
            raise WalletError(UNSUPPORTED_FORMAT)
        key = derive_key(password, salt, opslimit, memlimit)
        try:
            content = bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(
                data[HEADER_SIZE:], header, nonce, key
            )
        except CryptoError:
            raise WalletError(WRONG_PASSWORD) from None
        wallet = Wallet.from_json(content)
        self.opslimit, self.memlimit, self._salt, self._key = opslimit, memlimit, salt, key
        return wallet

    def verify_password(self, password: str) -> bool:
        """Check the password of the unlocked wallet, e.g. before showing a private key."""
        if self._key is None:
            raise WalletError('Wallet is locked')
        key = derive_key(password, self._salt, self.opslimit, self.memlimit)
        return compare_digest(key, self._key)

    def save(self, wallet: Wallet) -> None:
        """Encrypt the wallet using new nonce and atomically replace the wallet file."""
        if self._key is None:
            raise WalletError('Wallet is locked')
        nonce = os.urandom(NONCE_SIZE)
        header = struct.pack(
            HEADER_FORMAT, MAGIC, VERSION, self.opslimit, self.memlimit, self._salt, nonce
        )
        ciphertext = bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(
            wallet.to_json(), header, nonce, self._key
        )
        temporary_path = f'{self.path}.tmp'
        if os.path.exists(temporary_path):
            os.remove(temporary_path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0)
        descriptor = os.open(temporary_path, flags, 0o600)
        try:
            with os.fdopen(descriptor, 'wb') as file:
                file.write(header + ciphertext)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self.path)
        except BaseException:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)
            raise

    def change_password(self, old_password: str, new_password: str) -> Wallet:
        """Encrypt the wallet with new salt and the key derived from the new password."""
        check_new_password(new_password)
        wallet = self.unlock(old_password)
        old_salt, old_key = self._salt, self._key
        self._salt = os.urandom(pwhash.argon2id.SALTBYTES)
        self._key = derive_key(new_password, self._salt, self.opslimit, self.memlimit)
        try:
            self.save(wallet)
        except BaseException:
            self._salt, self._key = old_salt, old_key
            raise
        return wallet

    def lock(self) -> None:
        self._salt = None
        self._key = None
