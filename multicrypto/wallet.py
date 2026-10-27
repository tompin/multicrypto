"""Wallet keeping the BIP-39 mnemonic, HD accounts and imported private keys encrypted in a
single file.

The file starts with the header (integers are big-endian)::

    magic (8 bytes) | version (1) | opslimit (8) | memlimit (8) | salt (16) | nonce (24)

followed by the wallet content (JSON) encrypted with XChaCha20-Poly1305. The key is derived from
the password using Argon2id with the parameters and salt from the header. The whole header is
authenticated as additional data, so it cannot be modified without detection.

The BIP-39 passphrase is never saved, only the fingerprint of the master key derived with it, which
is used to detect a mistyped passphrase when the wallet is unlocked.
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
from typing import Any, Dict, Iterable, List, Optional, Tuple

from nacl import bindings, pwhash
from nacl.exceptions import CryptoError

from multicrypto.address import (
    convert_private_key_to_coin_address,
    convert_private_key_to_wif_format,
    get_private_key_from_wif_format,
    validate_address_type,
)
from multicrypto.base58 import BASE58_ALPHABET, base58_to_bytes
from multicrypto.bip32 import HARDENED, ExtendedKey, master_key_from_seed
from multicrypto.bip39 import mnemonic_to_seed, normalize_mnemonic, validate_mnemonic
from multicrypto.coins import P2PKH, P2SH_P2WPKH, P2TR, P2WPKH, coins
from multicrypto.ellipticcurve import secp256k1
from multicrypto.utils import double_sha256

MAGIC = b'MCWALLET'
VERSION = 2
HEADER_FORMAT = '>8sBQQ16s24s'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
KEY_SIZE = bindings.crypto_aead_xchacha20poly1305_ietf_KEYBYTES
NONCE_SIZE = bindings.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES
TAG_SIZE = bindings.crypto_aead_xchacha20poly1305_ietf_ABYTES
DEFAULT_PATH = os.path.join(os.path.expanduser('~'), '.multicrypto', 'wallet.mcw')
DEFAULT_OPSLIMIT = pwhash.argon2id.OPSLIMIT_MODERATE
DEFAULT_MEMLIMIT = pwhash.argon2id.MEMLIMIT_MODERATE
MIN_PASSWORD_LENGTH = 10
PURPOSES = {P2PKH: 44, P2SH_P2WPKH: 49, P2WPKH: 84, P2TR: 86}
RECEIVE_CHAIN = 0

WRONG_PASSWORD = 'Wrong password or damaged wallet file'
UNSUPPORTED_FORMAT = 'Unsupported format of the wallet file'


class WalletError(Exception):
    """Raised when the wallet file cannot be decrypted, created or saved, or it is locked."""


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
    """Validate imported private key data and return its address."""
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


def account_path(coin_symbol: str, address_type: str, account: int) -> str:
    return f"m/{PURPOSES[address_type]}'/{get_coin(coin_symbol)['slip44']}'/{account}'"


def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class HDAddress:
    index: int
    label: str
    created: str = field(default_factory=_now)


@dataclass
class HDAccount:
    """BIP-44 account (BIP-49, BIP-84, BIP-86 for segwit address types) of the coin."""

    label: str
    coin: str
    address_type: str
    account: int
    addresses: List[HDAddress] = field(default_factory=list)
    id: str = field(default_factory=_new_id)

    @property
    def path(self) -> str:
        return account_path(self.coin, self.address_type, self.account)


@dataclass
class ImportedKey:
    """Private key imported in WIF format, which is not derived from the mnemonic."""

    label: str
    coin: str
    wif: str = field(repr=False)
    address_type: str
    id: str = field(default_factory=_new_id)
    created: str = field(default_factory=_now)

    @cached_property
    def address(self) -> str:
        private_key, compressed = get_private_key_from_wif_format(self.wif)
        return convert_private_key_to_coin_address(
            private_key, coins[self.coin], compressed, self.address_type
        )


@dataclass(frozen=True)
class WalletAddress:
    """Address of the wallet: derived from the mnemonic or of the imported private key."""

    id: str
    label: str
    coin: str
    address_type: str
    address: str
    path: Optional[str] = None  # derivation path, None for imported private keys
    account_id: Optional[str] = None
    index: Optional[int] = None


class Wallet:
    """Decrypted content of the wallet file, keys are derived after opening it with passphrase."""

    def __init__(
        self,
        mnemonic: str,
        fingerprint: str,
        accounts: Iterable[HDAccount] = (),
        imported: Iterable[ImportedKey] = (),
    ):
        self.mnemonic = mnemonic
        self.fingerprint = fingerprint
        self.accounts: List[HDAccount] = list(accounts)
        self.imported: List[ImportedKey] = list(imported)
        self._master_key: Optional[ExtendedKey] = None
        self._chain_keys: Dict[str, ExtendedKey] = {}
        self._addresses: Dict[Tuple[str, str, int], str] = {}

    @classmethod
    def create(cls, mnemonic: str, passphrase: str) -> 'Wallet':
        """Create opened wallet without accounts from the mnemonic and the passphrase."""
        validate_mnemonic(mnemonic)
        master_key = master_key_from_seed(mnemonic_to_seed(mnemonic, passphrase))
        wallet = cls(normalize_mnemonic(mnemonic), master_key.fingerprint.hex())
        wallet._master_key = master_key
        return wallet

    @property
    def is_open(self) -> bool:
        return self._master_key is not None

    def open(self, passphrase: str) -> None:
        """Derive the master key, raise WalletError when the passphrase gives another wallet."""
        master_key = master_key_from_seed(mnemonic_to_seed(self.mnemonic, passphrase))
        fingerprint = master_key.fingerprint.hex()
        if fingerprint != self.fingerprint:
            raise WalletError(
                f'This passphrase gives wallet {fingerprint}, but the wallet was created with '
                f'{self.fingerprint}. Check the passphrase.'
            )
        self._master_key = master_key

    def close(self) -> None:
        """Forget the derived keys."""
        self._master_key = None
        self._chain_keys.clear()
        self._addresses.clear()

    def _derive(self, account: HDAccount, index: int) -> ExtendedKey:
        if self._master_key is None:
            raise WalletError('Wallet is locked')
        path = f'{account.path}/{RECEIVE_CHAIN}'
        if path not in self._chain_keys:
            self._chain_keys[path] = self._master_key.derive_path(path)
        return self._chain_keys[path].derive_child(index)

    def _address(self, account: HDAccount, index: int) -> str:
        cache_key = (account.coin, account.path, index)
        if cache_key not in self._addresses:
            private_key = self._derive(account, index).private_key
            self._addresses[cache_key] = convert_private_key_to_coin_address(
                private_key, coins[account.coin], True, account.address_type
            )
        return self._addresses[cache_key]

    def _hd_address(self, account: HDAccount, hd_address: HDAddress) -> WalletAddress:
        return WalletAddress(
            id=f'{account.id}/{hd_address.index}',
            label=hd_address.label,
            coin=account.coin,
            address_type=account.address_type,
            address=self._address(account, hd_address.index),
            path=f'{account.path}/{RECEIVE_CHAIN}/{hd_address.index}',
            account_id=account.id,
            index=hd_address.index,
        )

    @staticmethod
    def _imported_address(key: ImportedKey) -> WalletAddress:
        return WalletAddress(key.id, key.label, key.coin, key.address_type, key.address)

    def next_account_number(self, coin_symbol: str, address_type: str) -> int:
        numbers = [
            account.account
            for account in self.accounts
            if (account.coin, account.address_type) == (coin_symbol, address_type)
        ]
        return max(numbers, default=-1) + 1

    def add_account(
        self, label: str, coin_symbol: str, address_type: str, account: Optional[int] = None
    ) -> HDAccount:
        coin = get_coin(coin_symbol)
        if 'slip44' not in coin:
            raise ValueError(
                f'{coin_symbol} has no SLIP-44 coin type, its keys can be only imported'
            )
        validate_address_type(address_type, coin)
        if account is None:
            account = self.next_account_number(coin_symbol, address_type)
        if not 0 <= account < HARDENED:
            raise ValueError(f'Account number must be from 0 to {HARDENED - 1}')
        for existing in self.accounts:
            if (existing.coin, existing.address_type, existing.account) == (
                coin_symbol,
                address_type,
                account,
            ):
                raise ValueError(
                    f'Account {account} of {coin_symbol} {address_type} is already in the wallet '
                    f'as "{existing.label}"'
                )
        new_account = HDAccount(label, coin_symbol, address_type, account)
        self.accounts.append(new_account)
        return new_account

    def get_account(self, account_id: str) -> HDAccount:
        for account in self.accounts:
            if account.id == account_id:
                return account
        raise KeyError(account_id)

    def new_address(self, account_id: str, label: str = '') -> WalletAddress:
        """Add the next receiving address of the account."""
        account = self.get_account(account_id)
        index = max((address.index for address in account.addresses), default=-1) + 1
        if index >= HARDENED:
            raise ValueError('There are no more addresses in the account')
        hd_address = HDAddress(index, label or f'Address {index}')
        wallet_address = self._hd_address(account, hd_address)  # fails when the wallet is locked
        account.addresses.append(hd_address)
        return wallet_address

    def add_wif(
        self, label: str, coin_symbol: str, wif_private_key: str, address_type: str
    ) -> WalletAddress:
        """Import private key in WIF format, raise ValueError when it is incorrect or present."""
        check_entry(coin_symbol, wif_private_key, address_type)
        for key in self.imported:
            if (key.coin, key.wif, key.address_type) == (
                coin_symbol,
                wif_private_key,
                address_type,
            ):
                raise ValueError(f'Address {key.address} is already in the wallet as "{key.label}"')
        key = ImportedKey(label, coin_symbol, wif_private_key, address_type)
        self.imported.append(key)
        return self._imported_address(key)

    def account_addresses(self, account: HDAccount) -> List[WalletAddress]:
        return [self._hd_address(account, hd_address) for hd_address in account.addresses]

    def imported_addresses(self) -> List[WalletAddress]:
        return [self._imported_address(key) for key in self.imported]

    def addresses(self) -> List[WalletAddress]:
        addresses = []
        for account in self.accounts:
            addresses.extend(self.account_addresses(account))
        return addresses + self.imported_addresses()

    def _locate(self, item_id: str):
        """Return the account, HD address or imported key with the id, the list containing it and
        the account of the HD address."""
        for account in self.accounts:
            if account.id == item_id:
                return account, self.accounts, None
            for hd_address in account.addresses:
                if f'{account.id}/{hd_address.index}' == item_id:
                    return hd_address, account.addresses, account
        for key in self.imported:
            if key.id == item_id:
                return key, self.imported, None
        raise KeyError(item_id)

    def get_address(self, address_id: str) -> WalletAddress:
        item, _, account = self._locate(address_id)
        if isinstance(item, HDAddress):
            return self._hd_address(account, item)
        if isinstance(item, ImportedKey):
            return self._imported_address(item)
        raise KeyError(address_id)

    def rename(self, item_id: str, label: str) -> None:
        self._locate(item_id)[0].label = label

    def remove(self, item_id: str) -> None:
        """Remove the account, HD address (the seed still derives it) or imported key."""
        item, container, _ = self._locate(item_id)
        container[:] = [element for element in container if element is not item]

    def private_key_wif(self, address: WalletAddress) -> str:
        if address.account_id is None:
            return self._locate(address.id)[0].wif
        account = self.get_account(address.account_id)
        return generate_wif(account.coin, self._derive(account, address.index).private_key)

    def to_json(self) -> bytes:
        return json.dumps(
            {
                'seed': {'mnemonic': self.mnemonic, 'fingerprint': self.fingerprint},
                'accounts': [asdict(account) for account in self.accounts],
                'imported': [asdict(key) for key in self.imported],
            }
        ).encode()

    @classmethod
    def from_json(cls, data: bytes) -> 'Wallet':
        content = json.loads(data)
        accounts = [
            HDAccount(
                **{**account, 'addresses': [HDAddress(**item) for item in account['addresses']]}
            )
            for account in content['accounts']
        ]
        imported = [ImportedKey(**key) for key in content['imported']]
        seed = content['seed']
        return cls(seed['mnemonic'], seed['fingerprint'], accounts, imported)


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

    def create(self, password: str, mnemonic: str, passphrase: str) -> Wallet:
        """Create wallet file with the mnemonic and the default Bitcoin account."""
        check_new_password(password)
        if not passphrase:
            raise ValueError('Passphrase cannot be empty')
        wallet = Wallet.create(mnemonic, passphrase)
        wallet.add_account('Bitcoin', 'BTC', P2WPKH)
        if self.exists():
            raise WalletError(f'Wallet file {self.path} already exists')
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), mode=0o700, exist_ok=True)
        self._salt = os.urandom(pwhash.argon2id.SALTBYTES)
        self._key = derive_key(password, self._salt, self.opslimit, self.memlimit)
        self.save(wallet)
        return wallet

    def unlock(self, password: str, passphrase: str) -> Wallet:
        """Decrypt the wallet file and open the wallet with the passphrase."""
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
        wallet.open(passphrase)
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

    def change_password(self, old_password: str, new_password: str, wallet: Wallet) -> None:
        """Encrypt the wallet with new salt and the key derived from the new password."""
        check_new_password(new_password)
        if not self.verify_password(old_password):
            raise WalletError('Wrong password')
        old_salt, old_key = self._salt, self._key
        self._salt = os.urandom(pwhash.argon2id.SALTBYTES)
        self._key = derive_key(new_password, self._salt, self.opslimit, self.memlimit)
        try:
            self.save(wallet)
        except BaseException:
            self._salt, self._key = old_salt, old_key
            raise

    def lock(self) -> None:
        self._salt = None
        self._key = None
