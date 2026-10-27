# GUI z portfelem HD — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `multicrypto-gui` na PySide6 z portfelem HD (BIP-39 + passphrase, BIP-32/44/49/84/86) i importowanymi kluczami WIF w jednym zaszyfrowanym pliku.

**Architecture:** Nowe moduły bez GUI (`bip39.py`, `bip32.py`, `wallet.py` v2, `gui/forms.py`) są w pełni testowane jednostkowo na oficjalnych wektorach. Warstwa Qt (`gui/*`) zastępuje tkinter; wolne operacje (Argon2, PBKDF2, derywacja, sieć) idą przez `Worker` na `QThreadPool`. Testy GUI działają z `QT_QPA_PLATFORM=offscreen`.

**Tech Stack:** Python ≥ 3.10, PySide6-Essentials, PyNaCl, hashlib/hmac/secrets, pytest, ruff, uv.

Spec: `docs/superpowers/specs/2026-10-27-gui-hd-wallet-design.md`. Zastępuje plan `2026-10-26-gui-stage1.md`
(zadania 1–6 tamtego planu — `api.py`, szyfrowanie pliku, `forms.py` — są już na gałęzi `gui` i zostają).

**Doprecyzowania względem specyfikacji:**

- `ExtendedKey.xprv()` (serializacja BIP-32) — potrzebna do testów na wektorach BIP-32 i Trezora.
- `WalletFile.change_password(old, new, wallet)` przyjmuje otwarty portfel (odszyfrowanie bez passphrase
  nie jest potrzebne), stare hasło sprawdzane przez `verify_password`.
- Saldo adresów: `forms.fetch_balances()` (sieć, bez Qt), kolumna Balance w drzewie.
- Źródła w Send: lista adresów (`QListWidget`), nie drzewo.

## Struktura plików

| Plik | Odpowiedzialność |
|------|------------------|
| `pyproject.toml` | extra `gui` = PyNaCl + PySide6-Essentials, dev: przypięte wersje |
| `multicrypto/bip39_english.txt` | lista słów BIP-39 (SHA-256 `2f5eed53…dbda`) |
| `multicrypto/bip39.py` | mnemonik: entropia ↔ słowa, walidacja, seed |
| `multicrypto/bip32.py` | `ExtendedKey`, klucz główny, derywacja, ścieżki, `xprv()` |
| `multicrypto/coins.py` | `slip44` |
| `multicrypto/wallet.py` | model v2: `HDAccount`, `HDAddress`, `ImportedKey`, `WalletAddress`, `Wallet`, `WalletFile` |
| `multicrypto/gui/forms.py` | + passphrase, potwierdzanie słów, opis adresu, salda |
| `multicrypto/gui/worker.py` | `Worker` na `QThreadPool` |
| `multicrypto/gui/dialogs.py` | odblokowanie, hasło, potwierdzenie, sekret z odliczaniem, tekst z kopiowaniem, siatka słów |
| `multicrypto/gui/create_wizard.py` | `CreateWalletWizard` |
| `multicrypto/gui/wallet_tab.py` | drzewo kont / adresów / importowanych kluczy + dialogi kont i importu |
| `multicrypto/gui/balance_tab.py` | UTXO adresu |
| `multicrypto/gui/send_tab.py` | wysyłka |
| `multicrypto/gui/window.py` | `MainWindow` |
| `multicrypto/gui/app.py` | `main()` |
| `tests/conftest.py` | fixture `qapp` (offscreen) |
| `tests/data/bip39_vectors.json` | angielskie wektory Trezora |
| `tests/test_bip39.py`, `tests/test_bip32.py`, `tests/test_wallet.py`, `tests/test_gui_forms.py`, `tests/test_gui_worker.py`, `tests/test_gui.py` | testy |
| `.github/workflows/run_tests.yml`, `README.md` | CI bez xvfb, opis GUI |

Pobrane pliki źródłowe (lista słów, wektory) leżą w scratchpadzie sesji:
`/tmp/claude-1000/-home-tompin-projects-multicrypto/decb0a1e-f0a7-499f-b346-49e5109bb03d/scratchpad/downloads/`
(dalej `$DL`). Jeśli ich nie ma, pobierz ponownie:
`https://raw.githubusercontent.com/bitcoin/bips/master/bip-0039/english.txt`,
`https://raw.githubusercontent.com/trezor/python-mnemonic/master/vectors.json`.

---

### Task 1: Zależności PySide6

**Files:** Modify: `pyproject.toml`, `uv.lock`

- [ ] **Step 1:**

```bash
uv add --optional gui 'PySide6-Essentials>=6.8'
uv add --dev 'pyside6-essentials==6.12.0'
```

- [ ] **Step 2: Qt działa offscreen**

Run: `QT_QPA_PLATFORM=offscreen uv run python -c "from PySide6.QtWidgets import QApplication, QLabel; app = QApplication([]); print(QLabel('zażółć').sizeHint())"`
Expected: wypisany rozmiar, bez błędów.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Add PySide6 as optional gui dependency"
```

---

### Task 2: BIP-39

**Files:**
- Create: `multicrypto/bip39_english.txt`, `multicrypto/bip39.py`, `tests/data/bip39_vectors.json`
- Test: `tests/test_bip39.py`

- [ ] **Step 1: Dane**

```bash
echo "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda  $DL/english.txt" | sha256sum -c
cp $DL/english.txt multicrypto/bip39_english.txt
mkdir -p tests/data
python3 -I -c "import json,sys; json.dump(json.load(open(sys.argv[1]))['english'], open(sys.argv[2], 'w'), indent=1)" $DL/vectors.json tests/data/bip39_vectors.json
```

- [ ] **Step 2: Testy `tests/test_bip39.py`**

```python
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
```

- [ ] **Step 3: Uruchom — FAIL** (`uv run python -m pytest tests/test_bip39.py -q` → brak modułu)

- [ ] **Step 4: Implementacja `multicrypto/bip39.py`**

```python
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
```

- [ ] **Step 5:** Testy przejdą po Task 3 (używają `master_key_from_seed(...).xprv()`); na razie
  `uv run python -m pytest tests/test_bip39.py -q -k "not trezor"` → PASS. Commit razem z Task 3.

---

### Task 3: BIP-32

**Files:** Create: `multicrypto/bip32.py`; Test: `tests/test_bip32.py`

- [ ] **Step 1: Testy `tests/test_bip32.py`** (wektory 1–4 z BIP-32, `H` zamienione na `'`)

```python
import pytest

from multicrypto.bip32 import HARDENED, master_key_from_seed, parse_path

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
```

- [ ] **Step 2: Uruchom — FAIL** (`uv run python -m pytest tests/test_bip32.py -q`)

- [ ] **Step 3: Implementacja `multicrypto/bip32.py`**

```python
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
```

- [ ] **Step 4: Wszystkie testy BIP — PASS**

Run: `uv run python -m pytest tests/test_bip39.py tests/test_bip32.py -q && uv run ruff check . && uv run ruff format --check .`

- [ ] **Step 5: Wordlist w wheelu**

Run: `uv build -q -o /tmp/claude-1000/-home-tompin-projects-multicrypto/decb0a1e-f0a7-499f-b346-49e5109bb03d/scratchpad/dist2 && unzip -l /tmp/claude-1000/-home-tompin-projects-multicrypto/decb0a1e-f0a7-499f-b346-49e5109bb03d/scratchpad/dist2/*.whl | grep bip39_english`
Expected: plik jest w wheelu. Jeśli nie — dodać `source-include`/`data` w `[tool.uv.build-backend]`.

- [ ] **Step 6: Commit**

```bash
git add multicrypto/bip39.py multicrypto/bip39_english.txt multicrypto/bip32.py tests/test_bip39.py tests/test_bip32.py tests/data
git commit -m "Add BIP-39 mnemonics and BIP-32 key derivation"
```

---

### Task 4: SLIP-44 w `coins.py`

**Files:** Modify: `multicrypto/coins.py`; Test: `tests/test_coins.py`

- [ ] **Step 1: Test (dopisz do `tests/test_coins.py`)**

```python
def test_slip44_coin_types():
    assert {symbol: coin.get('slip44') for symbol, coin in coins.items()} == {
        'BTC': 0,
        'BTG': 156,
        'BTCH': None,
        'BTCZ': 177,
        'DASH': 5,
        'DOGE': 3,
        'LTC': 2,
        'SAFE': 19165,
        'TENT': 410,
        'SMART': 224,
        'TBTC': 1,
        'TBCH': 1,
        'TLTC': 1,
        'ZEC': 133,
        'ZCL': 147,
        'ZEIT': None,
        'ZEN': 121,
        'ZERO': 323,
    }
```
(jeśli `tests/test_coins.py` nie importuje `coins`, dodaj `from multicrypto.coins import coins`).

- [ ] **Step 2: FAIL**, potem w `multicrypto/coins.py` dodaj w definicji każdej monety (po `'name'`)
  `'slip44': <numer>` zgodnie z tabelą (BTCH i ZEIT bez klucza), a w komentarzu nad słownikiem
  zdanie: `'slip44' is the coin type from SLIP-44 used in BIP-44 derivation paths, coins without it
  support only imported private keys.`

- [ ] **Step 3: PASS + commit**

```bash
uv run python -m pytest tests/test_coins.py -q && uv run ruff check .
git add multicrypto/coins.py tests/test_coins.py
git commit -m "Add SLIP-44 coin types"
```

---

### Task 5: Model portfela v2 (`wallet.py`)

**Files:** Modify: `multicrypto/wallet.py`; Test: `tests/test_wallet.py` (przepisany)

- [ ] **Step 1: Testy — zastąp całą zawartość `tests/test_wallet.py`**

```python
import os
import stat

import pytest
from nacl import pwhash

from multicrypto.address import convert_private_key_to_wif_format
from multicrypto.ellipticcurve import secp256k1
from multicrypto.wallet import (
    HEADER_SIZE,
    UNSUPPORTED_FORMAT,
    WRONG_PASSWORD,
    ImportedKey,
    Wallet,
    WalletError,
    WalletFile,
    account_path,
    check_entry,
    generate_wif,
)

MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])
PASSWORD = 'correct horse battery'
NEW_PASSWORD = 'new password 123'
PASSPHRASE = 'secret passphrase'
BTC_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'
BTC_P2WPKH_ADDRESS = 'bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q'
TBTC_WIF = 'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo'
TBTC_P2TR_ADDRESS = 'tb1p5z79qpqcp9wf02p2zd5dtz89pxla4qu3zuz5w5hxhz7ds58cce4s9ztvgh'
UNCOMPRESSED_WIF = '5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ'
UNCOMPRESSED_ADDRESS = '1GAehh7TsJAHuUAeKZcXf5CnwuGuGgyX2S'


# Private keys in WIF format


def test_check_entry_returns_address():
    assert check_entry('BTC', BTC_WIF, 'p2wpkh') == BTC_P2WPKH_ADDRESS
    assert check_entry('TBTC', TBTC_WIF, 'p2tr') == TBTC_P2TR_ADDRESS
    assert check_entry('BTC', UNCOMPRESSED_WIF, 'p2pkh') == UNCOMPRESSED_ADDRESS


@pytest.mark.parametrize(
    'coin_symbol, wif, address_type, message',
    [
        ('XXX', BTC_WIF, 'p2pkh', 'Unknown coin XXX'),
        ('BTC', BTC_WIF, 'p2xx', 'Unknown address type'),
        ('ZEC', BTC_WIF, 'p2wpkh', 'is not supported'),
        ('TBTC', BTC_WIF, 'p2pkh', 'not in WIF format of TBTC'),
        ('BTC', BTC_WIF[:-1] + 'h', 'p2pkh', 'Incorrect checksum'),
        ('BTC', '0' + BTC_WIF[1:], 'p2pkh', 'only base58 characters'),
        ('BTC', '', 'p2pkh', 'only base58 characters'),
        ('BTC', convert_private_key_to_wif_format(secp256k1.n, b'\x80'), 'p2pkh', 'Incorrect'),
        ('BTC', UNCOMPRESSED_WIF, 'p2wpkh', 'compressed public key'),
    ],
)
def test_check_entry_rejects_incorrect_data(coin_symbol, wif, address_type, message):
    with pytest.raises(ValueError, match=message):
        check_entry(coin_symbol, wif, address_type)


def test_generate_wif():
    assert generate_wif('BTC', private_key=1) == (
        'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn'
    )
    assert check_entry('TBTC', generate_wif('TBTC'), 'p2tr').startswith('tb1p')


def test_imported_key_repr_does_not_contain_private_key():
    assert BTC_WIF not in repr(ImportedKey('Old', 'BTC', BTC_WIF, 'p2wpkh'))


# HD wallet


def test_fingerprint_of_test_mnemonic():
    assert Wallet.create(MNEMONIC, '').fingerprint == '73c5da0a'


@pytest.mark.parametrize(
    'coin, address_type, index, expected',
    [
        ('BTC', 'p2pkh', 0, '1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA'),  # BIP-44
        ('TBTC', 'p2sh-p2wpkh', 0, '2Mww8dCYPUpKHofjgcXcBCEGmniw9CoaiD2'),  # BIP-49
        ('BTC', 'p2wpkh', 0, 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'),  # BIP-84
        ('BTC', 'p2wpkh', 1, 'bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g'),
        (
            'BTC',
            'p2tr',
            0,
            'bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr',
        ),  # BIP-86
        ('BTC', 'p2tr', 1, 'bc1p4qhjn9zdvkux4e44uhx8tc55attvtyu358kutcqkudyccelu0was9fqzwh'),
    ],
)
def test_bip_test_vectors(coin, address_type, index, expected):
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', coin, address_type)

    addresses = [wallet.new_address(account.id) for _ in range(index + 1)]

    assert addresses[index].address == expected
    assert addresses[index].path == f'{account.path}/0/{index}'


def test_private_key_of_hd_address():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Test', 'TBTC', 'p2sh-p2wpkh')

    address = wallet.new_address(account.id, 'First')

    # BIP-49 test vector
    assert wallet.private_key_wif(address) == 'cULrpoZGXiuC19Uhvykx7NugygA3k86b3hmdCeyvHYQZSxojGyXJ'


def test_account_path():
    assert account_path('BTC', 'p2wpkh', 0) == "m/84'/0'/0'"
    assert account_path('LTC', 'p2pkh', 3) == "m/44'/2'/3'"
    assert account_path('TLTC', 'p2tr', 1) == "m/86'/1'/1'"


def test_add_account_numbers():
    wallet = Wallet.create(MNEMONIC, '')

    first = wallet.add_account('First', 'BTC', 'p2wpkh')
    second = wallet.add_account('Second', 'BTC', 'p2wpkh')
    legacy = wallet.add_account('Legacy', 'BTC', 'p2pkh')

    assert (first.account, second.account, legacy.account) == (0, 1, 0)
    assert wallet.next_account_number('BTC', 'p2wpkh') == 2


@pytest.mark.parametrize(
    'coin, address_type, account, message',
    [
        ('BTCH', 'p2pkh', None, 'no SLIP-44 coin type'),
        ('ZEC', 'p2wpkh', None, 'is not supported'),
        ('BTC', 'p2wpkh', 2**31, 'Account number must be'),
        ('BTC', 'p2wpkh', 0, 'already in the wallet'),
        ('XXX', 'p2pkh', None, 'Unknown coin'),
    ],
)
def test_add_account_errors(coin, address_type, account, message):
    wallet = Wallet.create(MNEMONIC, '')
    wallet.add_account('Existing', 'BTC', 'p2wpkh')

    with pytest.raises(ValueError, match=message):
        wallet.add_account('New', coin, address_type, account)


def test_new_address_labels_and_indexes():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')

    first = wallet.new_address(account.id, 'Exchange')
    second = wallet.new_address(account.id)

    assert (first.label, first.index, second.label, second.index) == ('Exchange', 0, 'Address 1', 1)
    assert wallet.addresses() == [first, second]
    assert wallet.get_address(second.id) == second


def test_imported_keys():
    wallet = Wallet.create(MNEMONIC, '')

    address = wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh')

    assert (address.address, address.path, address.account_id) == (BTC_P2WPKH_ADDRESS, None, None)
    assert wallet.private_key_wif(address) == BTC_WIF
    with pytest.raises(ValueError, match='already in the wallet'):
        wallet.add_wif('Again', 'BTC', BTC_WIF, 'p2wpkh')
    with pytest.raises(ValueError):
        wallet.add_wif('Wrong', 'TBTC', BTC_WIF, 'p2pkh')
    assert wallet.addresses() == [address]


def test_rename_and_remove():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')
    first = wallet.new_address(account.id, 'First')
    second = wallet.new_address(account.id, 'Second')
    imported = wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh')

    wallet.rename(account.id, 'Renamed account')
    wallet.rename(second.id, 'Renamed address')
    wallet.remove(first.id)
    wallet.remove(imported.id)

    assert account.label == 'Renamed account'
    assert [address.label for address in wallet.addresses()] == ['Renamed address']
    wallet.remove(account.id)
    assert wallet.accounts == []
    with pytest.raises(KeyError):
        wallet.remove(account.id)


def test_closed_wallet_cannot_derive_keys():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')

    wallet.close()

    with pytest.raises(WalletError, match='locked'):
        wallet.new_address(account.id)
    assert account.addresses == []


def test_open_checks_fingerprint():
    wallet = Wallet.create(MNEMONIC, PASSPHRASE)
    closed = Wallet.from_json(wallet.to_json())

    with pytest.raises(WalletError, match='This passphrase gives wallet 73c5da0a'):
        closed.open('')
    closed.open(PASSPHRASE)

    assert closed.is_open


def test_json_round_trip_does_not_contain_passphrase():
    wallet = Wallet.create(MNEMONIC, PASSPHRASE)
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')
    wallet.new_address(account.id, 'First')
    wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh')

    data = wallet.to_json()
    restored = Wallet.from_json(data)
    restored.open(PASSPHRASE)

    assert PASSPHRASE.encode() not in data
    assert restored.accounts == wallet.accounts
    assert restored.imported == wallet.imported
    assert restored.addresses() == wallet.addresses()


# Wallet file


@pytest.fixture
def wallet_file(tmp_path):
    return WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )


def read(path):
    with open(path, 'rb') as file:
        return file.read()


def test_create_and_unlock(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    address = wallet.new_address(wallet.accounts[0].id, 'Savings')
    wallet_file.save(wallet)
    wallet_file.lock()

    unlocked = WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)

    assert [(a.label, a.coin, a.address_type) for a in unlocked.accounts] == [
        ('Bitcoin', 'BTC', 'p2wpkh')
    ]
    assert unlocked.addresses() == [address]


def test_file_is_encrypted_and_private(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    wallet.add_wif('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    wallet_file.save(wallet)

    data = read(wallet_file.path)
    assert data.startswith(b'MCWALLET\x02')
    for secret in ('abandon', BTC_WIF, 'Savings', PASSPHRASE):
        assert secret.encode() not in data
    assert stat.S_IMODE(os.stat(wallet_file.path).st_mode) == 0o600
    assert not os.path.exists(wallet_file.path + '.tmp')


@pytest.mark.parametrize(
    'password, mnemonic, passphrase, message',
    [
        ('short', MNEMONIC, PASSPHRASE, 'at least 10 characters'),
        (PASSWORD, MNEMONIC, '', 'Passphrase cannot be empty'),
        (PASSWORD, 'abandon about', PASSPHRASE, 'must have 12'),
    ],
)
def test_create_validates_input(wallet_file, password, mnemonic, passphrase, message):
    with pytest.raises(ValueError, match=message):
        wallet_file.create(password, mnemonic, passphrase)

    assert not wallet_file.exists()


def test_create_does_not_overwrite_existing_file(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    with pytest.raises(WalletError, match='already exists'):
        WalletFile(wallet_file.path).create(PASSWORD, MNEMONIC, PASSPHRASE)


def test_create_makes_private_directory(tmp_path):
    path = tmp_path / 'new' / 'wallet.mcw'

    WalletFile(str(path), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN).create(
        PASSWORD, MNEMONIC, PASSPHRASE
    )

    assert stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700


def test_unlock_with_wrong_password(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    with pytest.raises(WalletError, match=WRONG_PASSWORD):
        WalletFile(wallet_file.path).unlock('wrong password', PASSPHRASE)


def test_unlock_with_wrong_passphrase(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    other_file = WalletFile(wallet_file.path)

    with pytest.raises(WalletError, match=f'created with {wallet.fingerprint}'):
        other_file.unlock(PASSWORD, 'other passphrase')

    assert not other_file.is_unlocked


def test_save_uses_new_nonce(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    first = read(wallet_file.path)

    wallet_file.save(wallet)

    second = read(wallet_file.path)
    assert first[:41] == second[:41]
    assert first[41:HEADER_SIZE] != second[41:HEADER_SIZE]


@pytest.mark.parametrize('offset', [0, 8, 16, 24, 25, 41, HEADER_SIZE, -1])
def test_unlock_detects_modification(wallet_file, offset):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    data = bytearray(read(wallet_file.path))
    data[offset] ^= 1
    with open(wallet_file.path, 'wb') as file:
        file.write(data)

    with pytest.raises(WalletError):
        WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)


def test_unlock_rejects_version_1(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    data = bytearray(read(wallet_file.path))
    data[8] = 1
    with open(wallet_file.path, 'wb') as file:
        file.write(data)

    with pytest.raises(WalletError, match=UNSUPPORTED_FORMAT):
        WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)


def test_unlock_unsupported_file(tmp_path):
    path = tmp_path / 'wallet.mcw'
    path.write_bytes(b'not a wallet')

    with pytest.raises(WalletError, match=UNSUPPORTED_FORMAT):
        WalletFile(str(path)).unlock(PASSWORD, PASSPHRASE)


def test_verify_password(wallet_file):
    wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    assert wallet_file.verify_password(PASSWORD)
    assert not wallet_file.verify_password('wrong password')


def test_change_password(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    salt = read(wallet_file.path)[25:41]

    wallet_file.change_password(PASSWORD, NEW_PASSWORD, wallet)

    assert read(wallet_file.path)[25:41] != salt
    with pytest.raises(WalletError):
        WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)
    unlocked = WalletFile(wallet_file.path).unlock(NEW_PASSWORD, PASSPHRASE)
    assert unlocked.accounts == wallet.accounts


def test_change_password_with_wrong_old_password(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)

    with pytest.raises(WalletError, match='Wrong password'):
        wallet_file.change_password('wrong password', NEW_PASSWORD, wallet)

    assert WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE).accounts == wallet.accounts


def test_locked_wallet_file_cannot_be_saved(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    wallet_file.lock()

    with pytest.raises(WalletError, match='locked'):
        wallet_file.save(wallet)
```

- [ ] **Step 2: FAIL** (`uv run python -m pytest tests/test_wallet.py -q` → ImportError `ImportedKey`)

- [ ] **Step 3: Implementacja — zmiany w `multicrypto/wallet.py`**

Docstring modułu — akapit o treści:
```python
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
```

Importy: dodać `from typing import Any, Dict, Iterable, List, Optional, Tuple` oraz
```python
from multicrypto.bip32 import HARDENED, ExtendedKey, master_key_from_seed
from multicrypto.bip39 import mnemonic_to_seed, normalize_mnemonic, validate_mnemonic
from multicrypto.coins import P2PKH, P2SH_P2WPKH, P2TR, P2WPKH, coins
```
Stałe: `VERSION = 2`, a pod `MIN_PASSWORD_LENGTH`:
```python
PURPOSES = {P2PKH: 44, P2SH_P2WPKH: 49, P2WPKH: 84, P2TR: 86}
RECEIVE_CHAIN = 0
```

Zostają bez zmian: `WalletError`, `get_coin`, `check_wif_private_key`, `check_entry`, `generate_wif`,
`_now`, `check_new_password`, `derive_key`. Klasy `WalletEntry` i `Wallet` z etapu 1 **usunąć** i w ich
miejsce wstawić:

```python
def _new_id() -> str:
    return str(uuid.uuid4())


def account_path(coin_symbol: str, address_type: str, account: int) -> str:
    return f"m/{PURPOSES[address_type]}'/{get_coin(coin_symbol)['slip44']}'/{account}'"


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
        """Return the account, HD address or imported key with the id and the list containing it."""
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
```

W `WalletFile` zmienić:

```python
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
        ... (jak dotąd do `content = ...decrypt(...)` włącznie) ...
        wallet = Wallet.from_json(content)
        wallet.open(passphrase)
        self.opslimit, self.memlimit, self._salt, self._key = opslimit, memlimit, salt, key
        return wallet

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
```

- [ ] **Step 4: PASS**

Run: `uv run ruff format multicrypto tests && uv run python -m pytest tests/test_wallet.py -q && uv run ruff check .`
(`tests/test_gui*.py` z etapu 1 mogą teraz nie działać — zostaną przepisane w Task 6–13; do tego czasu
uruchamiaj pełny zestaw z `--ignore=tests/test_gui.py --ignore=tests/test_gui_worker.py`.)

- [ ] **Step 5: Commit**

```bash
git add multicrypto/wallet.py tests/test_wallet.py
git commit -m "Keep BIP-39 mnemonic, HD accounts and imported keys in the wallet file"
```

---

### Task 6: `forms.py` dla portfela HD

**Files:** Modify: `multicrypto/gui/forms.py`; Test: `tests/test_gui_forms.py`

- [ ] **Step 1: Testy** — w `tests/test_gui_forms.py`:
  - import `WalletEntry` → `WalletAddress`; usunąć `entry_description` z importów, dodać
    `address_description`, `check_confirmation_words`, `check_passphrase_confirmation`,
    `choose_word_positions`, `coins_with_slip44`, `fetch_balances`; dodać
    `from tests import http_mock`, `from multicrypto.api import get_api`, `from multicrypto.coins import coins`;
  - `test_check_sources` i `test_entry_description` zastąpić:

```python
SEGWIT_ADDRESS = 'bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q'


def make_address(address_id='a', coin='BTC', address_type='p2wpkh', address=SEGWIT_ADDRESS):
    return WalletAddress(
        address_id, 'Savings', coin, address_type, address, "m/84'/0'/0'/0/0", 'acc', 0
    )


def test_check_sources():
    savings = make_address('a')
    other = make_address('b')
    legacy = make_address('c', address_type='p2pkh')

    assert check_sources([savings, other]) == ('BTC', 'p2wpkh')
    with pytest.raises(ValueError, match='Select at least one'):
        check_sources([])
    with pytest.raises(ValueError, match='same coin and address type'):
        check_sources([savings, legacy])


def test_address_description():
    imported = WalletAddress('i', 'Old', 'ZEN', 'p2pkh', 'znXk')

    assert address_description(make_address()) == (
        f"Savings · BTC p2wpkh · m/84'/0'/0'/0/0 · {SEGWIT_ADDRESS}"
    )
    assert address_description(imported) == 'Old · ZEN p2pkh · imported · znXk'


def test_check_passphrase_confirmation():
    check_passphrase_confirmation('x', 'x')
    with pytest.raises(ValueError, match='cannot be empty'):
        check_passphrase_confirmation('', '')
    with pytest.raises(ValueError, match='do not match'):
        check_passphrase_confirmation('a', 'b')


def test_choose_word_positions():
    positions = choose_word_positions(24)

    assert len(positions) == 3
    assert positions == sorted(set(positions))
    assert all(1 <= position <= 24 for position in positions)


def test_check_confirmation_words():
    mnemonic = 'one two three four'

    check_confirmation_words(mnemonic, {2: ' TWO ', 4: 'four'})
    with pytest.raises(ValueError, match='Word 3 is not correct'):
        check_confirmation_words(mnemonic, {2: 'two', 3: 'tree'})


def test_coins_with_slip44():
    symbols = coins_with_slip44()

    assert {'BTC', 'TBTC', 'LTC'} <= set(symbols)
    assert 'BTCH' not in symbols
    assert symbols == sorted(symbols)


@http_mock.activate
def test_fetch_balances():
    api_url = get_api(coins['BTC']).base_url
    failing_address = 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'
    no_api_coin = next(symbol for symbol, coin in coins.items() if not coin.get('apis'))
    http_mock.add(
        http_mock.GET,
        f'{api_url}/address/{SEGWIT_ADDRESS}/utxo',
        json=[
            {'txid': '11' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 1000},
            {'txid': '22' * 32, 'vout': 1, 'status': {'confirmed': False}, 'value': 2000},
        ],
    )
    http_mock.add(
        http_mock.GET, f'{api_url}/address/{failing_address}/utxo', body='limit', status=429
    )

    balances = fetch_balances(
        [
            make_address('a'),
            make_address('b', address=failing_address),
            make_address('c', coin=no_api_coin, address_type='p2pkh', address='x'),
        ]
    )

    assert balances == {'a': 3000, 'b': 'error: API error: limit', 'c': 'no API'}
```

- [ ] **Step 2: FAIL**, potem **implementacja** w `multicrypto/gui/forms.py`:
  - importy: `import secrets`, `from typing import Dict, List, Optional, Tuple, Union`,
    `from multicrypto.api import InsufficientFundsError, PreparedTransaction, get_utxo_from_address`,
    `from multicrypto.wallet import WalletAddress, WalletError, check_new_password` (bez `WalletEntry`);
  - `check_sources(entries: List[WalletAddress])` — tylko adnotacja typu;
  - `entry_description` zastąpić:

```python
def address_description(address: WalletAddress) -> str:
    location = address.path or 'imported'
    return (
        f'{address.label} · {address.coin} {address.address_type} · {location} · {address.address}'
    )


def coins_with_slip44() -> List[str]:
    return sorted(symbol for symbol, coin in coins.items() if 'slip44' in coin)


def check_passphrase_confirmation(passphrase: str, confirmation: str) -> None:
    if not passphrase:
        raise ValueError('Passphrase cannot be empty')
    if passphrase != confirmation:
        raise ValueError('Passphrases do not match')


def choose_word_positions(word_count: int, count: int = 3) -> List[int]:
    """Random positions (from 1) of the words entered to confirm the written mnemonic."""
    return sorted(secrets.SystemRandom().sample(range(1, word_count + 1), count))


def check_confirmation_words(mnemonic: str, answers: Dict[int, str]) -> None:
    words = mnemonic.split()
    for position, answer in sorted(answers.items()):
        if answer.strip().lower() != words[position - 1]:
            raise ValueError(f'Word {position} is not correct, check the written mnemonic')


def fetch_balances(addresses: List[WalletAddress]) -> Dict[str, Union[int, str]]:
    """Return the sum of unspent outputs (or the error message) for the address ids."""
    balances: Dict[str, Union[int, str]] = {}
    for address in addresses:
        coin = coins[address.coin]
        if not coin.get('apis'):
            balances[address.id] = 'no API'
            continue
        try:
            utxos = get_utxo_from_address(coin, address.address)
        except EXPECTED_ERRORS as error:
            balances[address.id] = f'error: {error}'
        else:
            balances[address.id] = sum(utxo['satoshis'] for utxo in utxos)
    return balances
```

- [ ] **Step 3: PASS + commit**

```bash
uv run ruff format multicrypto tests && uv run python -m pytest tests/test_gui_forms.py -q && uv run ruff check .
git add multicrypto/gui/forms.py tests/test_gui_forms.py
git commit -m "Adapt GUI forms to HD wallet addresses"
```

---

### Task 7: `conftest.py` i `Worker` na Qt

**Files:** Create: `tests/conftest.py`; Modify (przepisane): `multicrypto/gui/worker.py`, `tests/test_gui_worker.py`

- [ ] **Step 1: `tests/conftest.py`**

```python
import os

import pytest


@pytest.fixture(scope='session')
def qapp():
    """Qt application shared by GUI tests, rendered offscreen without display."""
    pytest.importorskip('PySide6')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])
```

- [ ] **Step 2: Testy `tests/test_gui_worker.py`** (całość)

```python
import threading
import time

import pytest

pytest.importorskip('PySide6')

from multicrypto.gui.worker import Worker  # noqa: E402


def wait_until(qapp, condition):
    deadline = time.monotonic() + 5
    while not condition():
        assert time.monotonic() < deadline
        qapp.processEvents()
        time.sleep(0.01)


def test_worker_runs_function_in_background_and_callback_in_gui_thread(qapp):
    worker = Worker()
    results = []

    worker.run(
        lambda: (42, threading.current_thread()),
        lambda result: results.append((result, threading.current_thread())),
        None,
    )
    wait_until(qapp, lambda: results)

    (value, task_thread), callback_thread = results[0]
    assert value == 42
    assert task_thread is not threading.main_thread()
    assert callback_thread is threading.main_thread()


def test_worker_passes_exception_to_error_callback(qapp):
    worker = Worker()
    errors = []

    def fail():
        raise ValueError('bad value')

    worker.run(fail, None, errors.append)
    wait_until(qapp, lambda: errors)

    assert str(errors[0]) == 'bad value'


def test_worker_survives_callback_error(qapp):
    worker = Worker()
    results = []

    def broken_callback(_result):
        raise RuntimeError('callback error')

    worker.run(lambda: 1, broken_callback, None)
    wait_until(qapp, lambda: worker.pending == 0)
    worker.run(lambda: 2, results.append, None)
    wait_until(qapp, lambda: results)

    assert results == [2]
```

- [ ] **Step 3: FAIL**, potem **`multicrypto/gui/worker.py`** (całość)

```python
"""Running slow operations (key derivation, network requests) outside of the GUI thread."""

import logging
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

logger = logging.getLogger(__name__)


class _Signals(QObject):
    finished = Signal(object, object)  # callback, value


class _Task(QRunnable):
    def __init__(self, func, on_success, on_error, signals: _Signals):
        super().__init__()
        self.func = func
        self.on_success = on_success
        self.on_error = on_error
        self.signals = signals

    def run(self):
        try:
            result = self.func()
        except Exception as error:  # passed to on_error in the GUI thread
            self.signals.finished.emit(self.on_error, error)
        else:
            self.signals.finished.emit(self.on_success, result)


class Worker(QObject):
    """Run functions in the thread pool and call the callbacks in the GUI thread, since widgets
    must not be used from other threads."""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.pending = 0
        self._signals = _Signals(self)
        self._signals.finished.connect(self._finish)

    def run(
        self,
        func: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self.pending += 1
        QThreadPool.globalInstance().start(_Task(func, on_success, on_error, self._signals))

    @Slot(object, object)
    def _finish(self, callback, value):
        self.pending -= 1
        try:
            callback(value)
        except Exception:
            logger.exception('Error in the callback of the background task')
```

- [ ] **Step 4: PASS + commit**

```bash
uv run python -m pytest tests/test_gui_worker.py -q && uv run ruff check .
git add tests/conftest.py tests/test_gui_worker.py multicrypto/gui/worker.py
git commit -m "Run GUI background tasks in Qt thread pool"
```

---

### Task 8: Dialogi Qt

**Files:** Modify (przepisany): `multicrypto/gui/dialogs.py`

- [ ] **Step 1: Implementacja** (testowana w Task 9 i 13)

```python
"""Dialogs of the GUI."""

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from multicrypto.gui.forms import check_password_confirmation

SECRET_DISPLAY_SECONDS = 30


def password_field() -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setMinimumWidth(320)
    return field


def monospace_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    return label


def mnemonic_grid(mnemonic: str, columns: int = 4) -> QWidget:
    """Numbered words of the mnemonic in columns, which cannot be selected or copied."""
    widget = QWidget()
    grid = QGridLayout(widget)
    words = mnemonic.split()
    rows = (len(words) + columns - 1) // columns
    for position, word in enumerate(words):
        label = monospace_label(f'{position + 1:2}. {word}')
        label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        grid.addWidget(label, position % rows, position // rows)
    return widget


def secret_line(secret: str) -> QLineEdit:
    field = QLineEdit(secret)
    field.setReadOnly(True)
    field.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    field.setMinimumWidth(field.fontMetrics().horizontalAdvance(secret) + 24)
    return field


class UnlockDialog(QDialog):
    """Ask for the password of the wallet file and the BIP-39 passphrase."""

    def __init__(self, parent: Optional[QWidget], path: str):
        super().__init__(parent)
        self.setWindowTitle('Unlock wallet')
        self.password = password_field()
        self.passphrase = password_field()
        form = QFormLayout(self)
        form.addRow(QLabel(f'Wallet {path}'))
        form.addRow('Password', self.password)
        form.addRow('Passphrase', self.passphrase)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self):
        if not self.password.text() or not self.passphrase.text():
            QMessageBox.warning(self, 'Unlock wallet', 'Enter the password and the passphrase')
            return
        super().accept()

    def values(self) -> Tuple[str, str]:
        return self.password.text(), self.passphrase.text()


class PasswordDialog(QDialog):
    """Ask for the password, the new password has to be entered twice."""

    def __init__(self, parent: Optional[QWidget], title: str, prompt: str, new_password=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.new_password = new_password
        self.password = password_field()
        self.confirmation = password_field()
        form = QFormLayout(self)
        form.addRow(QLabel(prompt))
        form.addRow('Password', self.password)
        if new_password:
            form.addRow('Repeat password', self.confirmation)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def accept(self):
        try:
            if self.new_password:
                check_password_confirmation(self.password.text(), self.confirmation.text())
            elif not self.password.text():
                raise ValueError('Enter the password')
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()


def ask_password(
    parent: Optional[QWidget], title: str, prompt: str, new_password: bool = False
) -> Optional[str]:
    dialog = PasswordDialog(parent, title, prompt, new_password)
    return dialog.password.text() if dialog.exec() else None


class ConfirmDialog(QDialog):
    """Show the rows and ask for confirmation. Cancel is the default button, so Enter does not
    confirm the action by accident."""

    def __init__(self, parent, title: str, rows: List[Tuple[str, str]], confirm_text: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        grid = QGridLayout()
        for row, (name, value) in enumerate(rows):
            name_label = QLabel(f'<b>{name}:</b>')
            value_label = QLabel(value)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(name_label, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(value_label, row, 1)
        confirm_button = QPushButton(confirm_text)
        confirm_button.setAutoDefault(False)
        confirm_button.clicked.connect(self.accept)
        cancel_button = QPushButton('Cancel')
        cancel_button.setDefault(True)
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(confirm_button)
        buttons.addWidget(cancel_button)
        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addLayout(buttons)
        cancel_button.setFocus()


def confirm(parent, title: str, rows: List[Tuple[str, str]], confirm_text: str) -> bool:
    return bool(ConfirmDialog(parent, title, rows, confirm_text).exec())


class SecretDialog(QDialog):
    """Show the secret (private key, mnemonic), the dialog closes after the given time."""

    def __init__(
        self, parent, title: str, text: str, secret: QWidget, seconds=SECRET_DISPLAY_SECONDS
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.remaining = seconds
        self.countdown = QLabel()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(text))
        layout.addWidget(secret)
        layout.addWidget(self.countdown)
        layout.addWidget(buttons)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._show_countdown()

    def _show_countdown(self):
        self.countdown.setText(f'The window closes in {self.remaining} seconds')

    def _tick(self):
        self.remaining -= 1
        if self.remaining <= 0:
            self.reject()
        else:
            self._show_countdown()


def show_text(parent, title: str, label: str, text: str) -> None:
    """Show the text (e.g. transaction id) with the button copying it to the clipboard."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    copy_button = QPushButton('Copy')
    copy_button.clicked.connect(lambda: QApplication.clipboard().setText(text))
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(label))
    layout.addWidget(secret_line(text))
    layout.addWidget(buttons)
    dialog.exec()
```

- [ ] **Step 2: Lint + import + commit**

```bash
uv run ruff format multicrypto && uv run ruff check . && QT_QPA_PLATFORM=offscreen uv run python -c "import multicrypto.gui.dialogs"
git add multicrypto/gui/dialogs.py
git commit -m "Rewrite GUI dialogs with Qt"
```

---

### Task 9: Kreator tworzenia portfela

**Files:** Create: `multicrypto/gui/create_wizard.py`; Test: `tests/test_gui.py` (nowy plik, smoke testy dopisywane w Task 13)

- [ ] **Step 1: Testy — `tests/test_gui.py` (początek pliku)**

```python
import pytest

pytest.importorskip('PySide6')

from multicrypto.gui.create_wizard import RESTORE_PAGE, SHOW_PAGE, CreateWalletWizard  # noqa: E402

PASSWORD = 'correct horse battery'
PASSPHRASE = 'secret passphrase'
MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])


def test_wizard_restores_mnemonic(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')
    wizard.password_page.password.setText(PASSWORD)
    wizard.password_page.confirmation.setText(PASSWORD)
    wizard.mode_page.restore.setChecked(True)
    wizard.restore_page.text.setPlainText(MNEMONIC.upper())
    wizard.passphrase_page.passphrase.setText(PASSPHRASE)
    wizard.passphrase_page.confirmation.setText(PASSPHRASE)

    assert wizard.password_page.validatePage()
    assert wizard.mode_page.nextId() == RESTORE_PAGE
    assert wizard.restore_page.status.text() == 'Mnemonic is correct'
    assert wizard.restore_page.validatePage()
    assert wizard.passphrase_page.validatePage()
    assert wizard.values() == (PASSWORD, MNEMONIC, PASSPHRASE)


def test_wizard_confirms_generated_mnemonic(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')
    words = wizard.generated_mnemonic.split()
    for position, field in wizard.confirm_page.answers.items():
        field.setText(words[position - 1])

    assert len(words) == 24
    assert wizard.mode_page.nextId() == SHOW_PAGE
    assert wizard.confirm_page.validatePage()
    assert wizard.values()[1] == wizard.generated_mnemonic


def test_restore_page_shows_mnemonic_errors(qapp):
    wizard = CreateWalletWizard(None, 'wallet.mcw')

    wizard.restore_page.text.setPlainText(' '.join(['abandon'] * 12))

    assert 'checksum' in wizard.restore_page.status.text()
```

- [ ] **Step 2: FAIL**, potem **`multicrypto/gui/create_wizard.py`**

```python
"""Wizard creating the wallet: file password, new or restored mnemonic and BIP-39 passphrase."""

from typing import Tuple

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from multicrypto.bip39 import generate_mnemonic, normalize_mnemonic, validate_mnemonic
from multicrypto.gui.dialogs import mnemonic_grid, password_field
from multicrypto.gui.forms import (
    check_confirmation_words,
    check_passphrase_confirmation,
    check_password_confirmation,
    choose_word_positions,
)
from multicrypto.wallet import MIN_PASSWORD_LENGTH

PASSWORD_PAGE, MODE_PAGE, SHOW_PAGE, CONFIRM_PAGE, RESTORE_PAGE, PASSPHRASE_PAGE = range(6)


class _Page(QWizardPage):
    def __init__(self, title: str, subtitle: str):
        super().__init__()
        self.setTitle(title)
        self.setSubTitle(subtitle)

    def check(self, check, *args) -> bool:
        try:
            check(*args)
        except ValueError as error:
            QMessageBox.warning(self, self.title(), str(error))
            return False
        return True


class PasswordPage(_Page):
    def __init__(self, path: str):
        super().__init__(
            'Wallet file password',
            f'The password encrypts the wallet file {path}. '
            f'It must have at least {MIN_PASSWORD_LENGTH} characters.',
        )
        self.password = password_field()
        self.confirmation = password_field()
        form = QFormLayout(self)
        form.addRow('Password', self.password)
        form.addRow('Repeat password', self.confirmation)

    def validatePage(self):
        return self.check(
            check_password_confirmation, self.password.text(), self.confirmation.text()
        )


class ModePage(_Page):
    def __init__(self):
        super().__init__('Seed', 'Generate a new mnemonic or restore the wallet from yours.')
        self.generate = QRadioButton('Generate a new 24 words mnemonic')
        self.restore = QRadioButton('Restore from mnemonic')
        self.generate.setChecked(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.generate)
        layout.addWidget(self.restore)

    def nextId(self):
        return SHOW_PAGE if self.generate.isChecked() else RESTORE_PAGE


class ShowMnemonicPage(_Page):
    def __init__(self, mnemonic: str):
        super().__init__(
            'Write down the mnemonic',
            'Write the words on paper in this order and keep them safe. Together with the '
            'passphrase they restore all keys of the wallet. The words cannot be copied.',
        )
        layout = QVBoxLayout(self)
        layout.addWidget(mnemonic_grid(mnemonic))

    def nextId(self):
        return CONFIRM_PAGE


class ConfirmWordsPage(_Page):
    def __init__(self, mnemonic: str):
        super().__init__(
            'Confirm the mnemonic', 'Enter the words with the given numbers from your paper.'
        )
        self.mnemonic = mnemonic
        self.answers = {}
        form = QFormLayout(self)
        for position in choose_word_positions(len(mnemonic.split())):
            self.answers[position] = QLineEdit()
            form.addRow(f'Word {position}', self.answers[position])

    def validatePage(self):
        answers = {position: field.text() for position, field in self.answers.items()}
        return self.check(check_confirmation_words, self.mnemonic, answers)

    def nextId(self):
        return PASSPHRASE_PAGE


class RestorePage(_Page):
    def __init__(self):
        super().__init__(
            'Restore from mnemonic', 'Enter 12, 15, 18, 21 or 24 words separated with spaces.'
        )
        self.text = QPlainTextEdit()
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        layout.addWidget(self.status)
        self.text.textChanged.connect(self._update_status)

    def _update_status(self):
        if not self.text.toPlainText().strip():
            self.status.setText('')
            return
        try:
            validate_mnemonic(self.text.toPlainText())
        except ValueError as error:
            self.status.setText(str(error))
        else:
            self.status.setText('Mnemonic is correct')

    def mnemonic(self) -> str:
        return normalize_mnemonic(self.text.toPlainText())

    def validatePage(self):
        return self.check(validate_mnemonic, self.text.toPlainText())

    def nextId(self):
        return PASSPHRASE_PAGE


class PassphrasePage(_Page):
    def __init__(self):
        super().__init__(
            'BIP-39 passphrase',
            'The passphrase is never saved, you will enter it every time you unlock the wallet. '
            'Without it the mnemonic does not restore the wallet, so write it down and keep it '
            'separately from the mnemonic.',
        )
        self.passphrase = password_field()
        self.confirmation = password_field()
        form = QFormLayout(self)
        form.addRow('Passphrase', self.passphrase)
        form.addRow('Repeat passphrase', self.confirmation)

    def validatePage(self):
        return self.check(
            check_passphrase_confirmation, self.passphrase.text(), self.confirmation.text()
        )

    def nextId(self):
        return -1


class CreateWalletWizard(QWizard):
    def __init__(self, parent, path: str):
        super().__init__(parent)
        self.setWindowTitle('New wallet')
        self.generated_mnemonic = generate_mnemonic()
        self.password_page = PasswordPage(path)
        self.mode_page = ModePage()
        self.show_page = ShowMnemonicPage(self.generated_mnemonic)
        self.confirm_page = ConfirmWordsPage(self.generated_mnemonic)
        self.restore_page = RestorePage()
        self.passphrase_page = PassphrasePage()
        for page_id, page in (
            (PASSWORD_PAGE, self.password_page),
            (MODE_PAGE, self.mode_page),
            (SHOW_PAGE, self.show_page),
            (CONFIRM_PAGE, self.confirm_page),
            (RESTORE_PAGE, self.restore_page),
            (PASSPHRASE_PAGE, self.passphrase_page),
        ):
            self.setPage(page_id, page)
        self.setStartId(PASSWORD_PAGE)

    def values(self) -> Tuple[str, str, str]:
        """Return the password of the file, the mnemonic and the passphrase."""
        if self.mode_page.generate.isChecked():
            mnemonic = self.generated_mnemonic
        else:
            mnemonic = self.restore_page.mnemonic()
        return self.password_page.password.text(), mnemonic, self.passphrase_page.passphrase.text()
```

- [ ] **Step 3: PASS + commit**

```bash
uv run ruff format multicrypto tests && uv run python -m pytest tests/test_gui.py -q && uv run ruff check .
git add multicrypto/gui/create_wizard.py tests/test_gui.py
git commit -m "Add wizard creating HD wallet"
```

---

### Task 10: Zakładka Wallet

**Files:** Modify (przepisany): `multicrypto/gui/wallet_tab.py`

`app` (`MainWindow`, Task 13) udostępnia: `wallet`, `wallet_file`, `worker`, `modify_wallet(change)`,
`show_error(error)`, `select_tab(tab)`, `balance_tab.check_address(address)`,
`send_tab.select_source(address)`. Każda zakładka ma `refresh()` i `clear()`.

- [ ] **Step 1: Implementacja**

```python
"""Wallet tab: HD accounts with their addresses and imported private keys."""

from typing import Dict, Optional, Union

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from multicrypto.bip32 import HARDENED
from multicrypto.coins import coins, get_address_types
from multicrypto.gui.dialogs import SecretDialog, ask_password, password_field, secret_line
from multicrypto.gui.forms import EXPECTED_ERRORS, coins_with_slip44, fetch_balances, format_amount
from multicrypto.wallet import WalletAddress, account_path, check_entry

ITEM_ROLE = Qt.ItemDataRole.UserRole
ACCOUNT, ADDRESS, GROUP = 'account', 'address', 'group'


class _CoinTypeForm(QDialog):
    """Dialog with coin and address type fields, the address types depend on the coin."""

    def __init__(self, parent, title: str, symbols, submit):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.submit = submit
        self.label = QLineEdit()
        self.coin = QComboBox()
        self.coin.addItems(symbols)
        self.coin.setCurrentText('BTC')
        self.address_type = QComboBox()
        self.form = QFormLayout(self)
        self.form.addRow('Label', self.label)
        self.form.addRow('Coin', self.coin)
        self.form.addRow('Address type', self.address_type)
        self.coin.currentTextChanged.connect(self._coin_changed)
        self.address_type.currentTextChanged.connect(self.update_preview)

    def add_buttons(self):
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.form.addRow(buttons)
        self._coin_changed()

    def _coin_changed(self):
        current = self.address_type.currentText()
        address_types = get_address_types(coins[self.coin.currentText()])
        self.address_type.blockSignals(True)
        self.address_type.clear()
        self.address_type.addItems(address_types)
        if current in address_types:
            self.address_type.setCurrentText(current)
        self.address_type.blockSignals(False)
        self.update_preview()

    def update_preview(self):
        raise NotImplementedError

    def submitted_values(self):
        raise NotImplementedError

    def accept(self):
        try:
            self.submit(*self.submitted_values())
        except EXPECTED_ERRORS as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()


class NewAccountDialog(_CoinTypeForm):
    def __init__(self, parent, wallet, submit):
        super().__init__(parent, 'New account', coins_with_slip44(), submit)
        self.wallet = wallet
        self.account = QSpinBox()
        self.account.setRange(0, HARDENED - 1)
        self.path = QLabel()
        self.form.addRow('Account number', self.account)
        self.form.addRow('Path', self.path)
        self.account.valueChanged.connect(self._show_path)
        self.add_buttons()

    def update_preview(self):
        coin, address_type = self.coin.currentText(), self.address_type.currentText()
        if address_type:
            self.account.setValue(self.wallet.next_account_number(coin, address_type))
            self._show_path()

    def _show_path(self):
        self.path.setText(
            account_path(
                self.coin.currentText(), self.address_type.currentText(), self.account.value()
            )
        )

    def submitted_values(self):
        coin, address_type = self.coin.currentText(), self.address_type.currentText()
        label = self.label.text().strip() or f'{coin} {address_type} #{self.account.value()}'
        return label, coin, address_type, self.account.value()


class ImportWifDialog(_CoinTypeForm):
    def __init__(self, parent, submit):
        super().__init__(parent, 'Import private key', sorted(coins), submit)
        self.wif = password_field()
        self.address = QLabel()
        self.form.addRow('Private key (WIF)', self.wif)
        self.form.addRow('Address', self.address)
        self.wif.textChanged.connect(self.update_preview)
        self.add_buttons()

    def update_preview(self):
        wif = self.wif.text().strip()
        if not wif:
            self.address.setText('')
            return
        try:
            address = check_entry(self.coin.currentText(), wif, self.address_type.currentText())
        except ValueError as error:
            self.address.setText(f'({error})')
        else:
            self.address.setText(address)

    def submitted_values(self):
        label = self.label.text().strip()
        if not label:
            raise ValueError('Enter the label')
        return (
            label,
            self.coin.currentText(),
            self.wif.text().strip(),
            self.address_type.currentText(),
        )


class WalletTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.balances: Dict[str, Union[int, str]] = {}
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['Label', 'Path', 'Address', 'Balance'])
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_menu)
        buttons = QHBoxLayout()
        for text, slot in (
            ('New account...', self.new_account),
            ('New address...', self.new_address),
            ('Import WIF...', self.import_wif),
            ('Copy address', self.copy_address),
            ('Show key...', self.show_key),
            ('Rename...', self.rename),
            ('Remove...', self.remove),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda _checked=False, slot=slot: slot())
            buttons.addWidget(button)
        buttons.addStretch()
        self.refresh_button = QPushButton('Refresh balances')
        self.refresh_button.clicked.connect(lambda _checked=False: self.refresh_balances())
        buttons.addWidget(self.refresh_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.addLayout(buttons)

    def refresh(self):
        selected = self._selected()
        self.tree.clear()
        wallet = self.app.wallet
        for account in wallet.accounts:
            account_item = QTreeWidgetItem(
                self.tree,
                [account.label, account.path, f'{account.coin} {account.address_type}', ''],
            )
            account_item.setData(0, ITEM_ROLE, (ACCOUNT, account.id))
            for address in wallet.account_addresses(account):
                self._add_address_item(account_item, address, f'0/{address.index}')
        if wallet.imported:
            group = QTreeWidgetItem(self.tree, ['Imported keys (not in mnemonic backup)'])
            group.setData(0, ITEM_ROLE, (GROUP, ''))
            for address in wallet.imported_addresses():
                self._add_address_item(group, address, f'{address.coin} {address.address_type}')
        self.tree.expandAll()
        if selected:
            self._select(selected)

    def _add_address_item(self, parent: QTreeWidgetItem, address: WalletAddress, path: str):
        item = QTreeWidgetItem(
            parent, [address.label, path, address.address, self._balance_text(address.id)]
        )
        item.setData(0, ITEM_ROLE, (ADDRESS, address.id))
        item.setTextAlignment(3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def _balance_text(self, address_id: str) -> str:
        balance = self.balances.get(address_id)
        if balance is None:
            return ''
        return format_amount(balance) if isinstance(balance, int) else balance

    def clear(self):
        self.tree.clear()
        self.balances.clear()

    def _selected(self):
        item = self.tree.currentItem()
        return tuple(item.data(0, ITEM_ROLE)) if item else None

    def _select(self, selected):
        for item in self._items():
            if tuple(item.data(0, ITEM_ROLE)) == tuple(selected):
                self.tree.setCurrentItem(item)
                return

    def _items(self):
        for index in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(index)
            yield top
            for child_index in range(top.childCount()):
                yield top.child(child_index)

    def selected_address(self) -> Optional[WalletAddress]:
        selected = self._selected()
        if not selected or selected[0] != ADDRESS:
            QMessageBox.information(self, 'Wallet', 'Select an address first')
            return None
        return self.app.wallet.get_address(selected[1])

    def _selected_account_id(self) -> Optional[str]:
        selected = self._selected()
        if selected and selected[0] == ACCOUNT:
            return selected[1]
        if selected and selected[0] == ADDRESS:
            return self.app.wallet.get_address(selected[1]).account_id
        if len(self.app.wallet.accounts) == 1:
            return self.app.wallet.accounts[0].id
        return None

    def _modify(self, change):
        try:
            return self.app.modify_wallet(change)
        except EXPECTED_ERRORS as error:
            self.app.show_error(error)
            return None

    def new_account(self):
        def submit(label, coin, address_type, account):
            self.app.modify_wallet(
                lambda wallet: wallet.add_account(label, coin, address_type, account)
            )

        NewAccountDialog(self, self.app.wallet, submit).exec()

    def new_address(self):
        account_id = self._selected_account_id()
        if account_id is None:
            QMessageBox.information(self, 'New address', 'Select an account first')
            return
        label, ok = QInputDialog.getText(self, 'New address', 'Label (optional)')
        if ok:
            address = self._modify(lambda wallet: wallet.new_address(account_id, label.strip()))
            if address:
                self._select((ADDRESS, address.id))

    def import_wif(self):
        def submit(label, coin, wif, address_type):
            self.app.modify_wallet(lambda wallet: wallet.add_wif(label, coin, wif, address_type))

        ImportWifDialog(self, submit).exec()

    def copy_address(self):
        address = self.selected_address()
        if address:
            QApplication.clipboard().setText(address.address)

    def show_key(self):
        address = self.selected_address()
        if not address:
            return
        password = ask_password(
            self,
            'Show private key',
            f'Enter the wallet password to show the key of "{address.label}"',
        )
        if password is None:
            return
        self.app.worker.run(
            lambda: self.app.wallet_file.verify_password(password),
            lambda correct: self._show_key(address, correct),
            self.app.show_error,
        )

    def _show_key(self, address: WalletAddress, correct: bool):
        if not correct:
            QMessageBox.warning(self, 'Show private key', 'Wrong password')
            return
        if self.app.wallet is None:
            return
        SecretDialog(
            self,
            f'Private key of "{address.label}"',
            f'{address.coin} {address.address_type} {address.address}',
            secret_line(self.app.wallet.private_key_wif(address)),
        ).exec()

    def rename(self):
        selected = self._selected()
        if not selected or selected[0] == GROUP:
            QMessageBox.information(self, 'Rename', 'Select an account or an address first')
            return
        label, ok = QInputDialog.getText(
            self, 'Rename', 'Label', QLineEdit.EchoMode.Normal, self.tree.currentItem().text(0)
        )
        if ok and label.strip():
            self._modify(lambda wallet: wallet.rename(selected[1], label.strip()))

    def remove(self):
        selected = self._selected()
        if not selected or selected[0] == GROUP:
            QMessageBox.information(self, 'Remove', 'Select an account or an address first')
            return
        kind, item_id = selected
        label = self.tree.currentItem().text(0)
        if kind == ACCOUNT:
            warning = 'The account and its addresses will be removed from the list. The mnemonic still restores them.'
        elif self.app.wallet.get_address(item_id).account_id:
            warning = 'The address will be removed from the list. The mnemonic still restores it.'
        else:
            warning = (
                'The imported private key will be permanently deleted from the wallet file. '
                'It is not in the mnemonic backup, make sure you have its backup.'
            )
        answer = QMessageBox.question(
            self,
            'Remove',
            f'Remove "{label}"?\n\n{warning}',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._modify(lambda wallet: wallet.remove(item_id))

    def refresh_balances(self):
        addresses = self.app.wallet.addresses()
        self.refresh_button.setEnabled(False)
        self.app.worker.run(lambda: fetch_balances(addresses), self._show_balances, self._failed)

    def _show_balances(self, balances):
        self.refresh_button.setEnabled(True)
        if self.app.wallet is None:
            return
        self.balances = balances
        self.refresh()

    def _failed(self, error):
        self.refresh_button.setEnabled(True)
        self.app.show_error(error)

    def _show_menu(self, position):
        item = self.tree.itemAt(position)
        if not item or item.data(0, ITEM_ROLE)[0] != ADDRESS:
            return
        self.tree.setCurrentItem(item)
        address = self.app.wallet.get_address(item.data(0, ITEM_ROLE)[1])
        menu = QMenu(self)
        menu.addAction('Copy address', self.copy_address)
        menu.addAction('Check UTXO', lambda: self.app.balance_tab.check_address(address))
        menu.addAction('Send from this address', lambda: self.app.send_tab.select_source(address))
        menu.addAction('Rename...', self.rename)
        menu.addAction('Show key...', self.show_key)
        menu.exec(self.tree.viewport().mapToGlobal(position))
```

- [ ] **Step 2:** `uv run ruff format multicrypto && uv run ruff check . && QT_QPA_PLATFORM=offscreen uv run python -c "import multicrypto.gui.wallet_tab"` → bez błędów (zbyt długie linie łamie `ruff format`, długie stringi podziel ręcznie).

- [ ] **Step 3: Commit** — `git add multicrypto/gui/wallet_tab.py && git commit -m "Rewrite GUI wallet tab for HD accounts with Qt"`

---

### Task 11: Zakładka Balance

**Files:** Modify (przepisany): `multicrypto/gui/balance_tab.py`

- [ ] **Step 1: Implementacja**

```python
"""Balance tab: unspent outputs of the wallet address or any other address (checkaddress)."""

from argparse import Namespace
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from multicrypto.commands.checkaddress import check_address
from multicrypto.gui.forms import (
    address_description,
    coins_with_api,
    format_amount,
    parse_address,
    parse_thresholds,
)
from multicrypto.wallet import WalletAddress

COLUMNS = ['Transaction id', 'Confirmations', 'Satoshis', 'Amount']


class BalanceTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.addresses: List[WalletAddress] = []
        self.wallet_source = QRadioButton('Wallet address')
        self.wallet_source.setChecked(True)
        self.other_source = QRadioButton('Other address')
        self.address_box = QComboBox()
        self.address_box.activated.connect(lambda _index: self.wallet_source.setChecked(True))
        self.coin = QComboBox()
        self.coin.addItems(coins_with_api())
        self.coin.setCurrentText('BTC')
        self.address = QLineEdit()
        self.address.textEdited.connect(lambda _text: self.other_source.setChecked(True))
        self.minimum = QLineEdit()
        self.maximum = QLineEdit()
        self.limit = QLineEdit()
        for field in (self.minimum, self.maximum):
            field.setPlaceholderText('satoshis')
        self.check_button = QPushButton('Check')
        self.check_button.clicked.connect(lambda _checked=False: self.check())
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.total = QLabel()
        source = QGridLayout()
        source.addWidget(self.wallet_source, 0, 0)
        source.addWidget(self.address_box, 0, 1, 1, 2)
        source.addWidget(self.other_source, 1, 0)
        source.addWidget(self.coin, 1, 1)
        source.addWidget(self.address, 1, 2)
        source.setColumnStretch(2, 1)
        filters = QHBoxLayout()
        for text, field in (
            ('Minimum input', self.minimum),
            ('Maximum input', self.maximum),
            ('Limit of inputs', self.limit),
        ):
            filters.addWidget(QLabel(text))
            filters.addWidget(field)
        filters.addStretch()
        filters.addWidget(self.check_button)
        layout = QVBoxLayout(self)
        layout.addLayout(source)
        layout.addLayout(filters)
        layout.addWidget(self.table)
        layout.addWidget(self.total, alignment=Qt.AlignmentFlag.AlignRight)

    def refresh(self):
        selected = self.address_box.currentData()
        self.addresses = self.app.wallet.addresses()
        self.address_box.clear()
        for address in self.addresses:
            self.address_box.addItem(address_description(address), address.id)
        index = self.address_box.findData(selected)
        if index >= 0:
            self.address_box.setCurrentIndex(index)

    def clear(self):
        self.addresses = []
        self.address_box.clear()
        self.table.setRowCount(0)
        self.total.setText('')

    def check_address(self, address: WalletAddress):
        self.address_box.setCurrentIndex(self.address_box.findData(address.id))
        self.wallet_source.setChecked(True)
        self.app.select_tab(self)
        self.check()

    def _get_address(self):
        if self.wallet_source.isChecked():
            index = self.address_box.currentIndex()
            if index < 0:
                raise ValueError('Select the wallet address')
            address = self.addresses[index]
            return address.coin, address.address
        coin_symbol = self.coin.currentText()
        return coin_symbol, parse_address(self.address.text(), coin_symbol)

    def check(self):
        try:
            coin_symbol, address = self._get_address()
            minimum, maximum, limit = parse_thresholds(
                self.minimum.text(), self.maximum.text(), self.limit.text()
            )
        except ValueError as error:
            self.app.show_error(error)
            return
        args = Namespace(
            coin_symbol=coin_symbol,
            address=address,
            minimum_input_threshold=minimum,
            maximum_input_threshold=maximum,
            limit_inputs=limit,
        )
        self.check_button.setEnabled(False)
        self.app.worker.run(
            lambda: check_address(args), lambda utxos: self._show(utxos, coin_symbol), self._failed
        )

    def _show(self, utxos, coin_symbol: str):
        self.check_button.setEnabled(True)
        self.table.setRowCount(len(utxos))
        for row, utxo in enumerate(utxos):
            values = (
                utxo['txid'],
                str(utxo['confirmations']),
                str(utxo['satoshis']),
                format_amount(utxo['satoshis']),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)
        total = sum(utxo['satoshis'] for utxo in utxos)
        self.total.setText(
            f'{len(utxos)} inputs, total {format_amount(total)} {coin_symbol} ({total} satoshis)'
        )

    def _failed(self, error):
        self.check_button.setEnabled(True)
        self.app.show_error(error)
```

- [ ] **Step 2:** lint + import (jak w Task 10). **Step 3:** `git commit -m "Rewrite GUI balance tab with Qt"`

---

### Task 12: Zakładka Send

**Files:** Modify (przepisany): `multicrypto/gui/send_tab.py`

- [ ] **Step 1: Implementacja**

```python
"""Send tab: preparing, confirming and broadcasting transactions (sendcrypto)."""

import json
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from multicrypto.api import broadcast_prepared, prepare_from_private_keys
from multicrypto.coins import coins
from multicrypto.gui.dialogs import confirm, show_text
from multicrypto.gui.forms import (
    address_description,
    check_sources,
    describe_transaction,
    extract_txid,
    parse_address,
    parse_amount,
    parse_int,
    parse_nodes,
    parse_thresholds,
)
from multicrypto.network import broadcast_transaction
from multicrypto.wallet import WalletAddress

DEFAULT_FEE = 10000
ID_ROLE = Qt.ItemDataRole.UserRole


class SendTab(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.sources = QListWidget()
        self.sources.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.destination = QLineEdit()
        self.destination_status = QLabel()
        self.amount = QLineEdit()
        self.amount.setPlaceholderText('in coin units, e.g. 0.001')
        self.fee = QLineEdit(str(DEFAULT_FEE))
        self.minimum = QLineEdit()
        self.maximum = QLineEdit()
        self.limit = QLineEdit()
        self.p2p = QCheckBox('Send directly to the peer-to-peer network')
        self.nodes = QLineEdit()
        self.nodes.setPlaceholderText('optional, host[:port] separated with commas')
        self.prepare_button = QPushButton('Prepare transaction...')
        self.prepare_button.clicked.connect(lambda _checked=False: self.prepare())
        form = QFormLayout()
        form.addRow('To address', self.destination)
        form.addRow('', self.destination_status)
        form.addRow('Amount', self.amount)
        form.addRow('Fee (satoshis)', self.fee)
        advanced = QGroupBox('Advanced')
        advanced_form = QFormLayout(advanced)
        advanced_form.addRow('Minimum input (satoshis)', self.minimum)
        advanced_form.addRow('Maximum input (satoshis)', self.maximum)
        advanced_form.addRow('Limit of inputs', self.limit)
        advanced_form.addRow(self.p2p)
        advanced_form.addRow('Nodes', self.nodes)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('From (one or more addresses with the same coin and address type)'))
        layout.addWidget(self.sources)
        layout.addLayout(form)
        layout.addWidget(advanced)
        layout.addWidget(self.prepare_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.destination.textChanged.connect(self._validate_destination)
        self.sources.itemSelectionChanged.connect(self._validate_destination)

    def refresh(self):
        selected = {item.data(ID_ROLE) for item in self.sources.selectedItems()}
        self.sources.clear()
        for address in self.app.wallet.addresses():
            item = QListWidgetItem(address_description(address), self.sources)
            item.setData(ID_ROLE, address.id)
            item.setSelected(address.id in selected)

    def clear(self):
        self.sources.clear()
        self.destination.clear()
        self.amount.clear()

    def select_source(self, address: WalletAddress):
        for index in range(self.sources.count()):
            item = self.sources.item(index)
            item.setSelected(item.data(ID_ROLE) == address.id)
        self.app.select_tab(self)

    def _selected_addresses(self) -> List[WalletAddress]:
        return [
            self.app.wallet.get_address(item.data(ID_ROLE)) for item in self.sources.selectedItems()
        ]

    def _validate_destination(self):
        text = self.destination.text()
        if not text.strip() or self.app.wallet is None:
            self.destination_status.setText('')
            return
        try:
            coin_symbol, _ = check_sources(self._selected_addresses())
            parse_address(text, coin_symbol)
        except ValueError as error:
            self.destination_status.setText(f'<span style="color: #c62828">{error}</span>')
        else:
            self.destination_status.setText(
                f'<span style="color: #2e7d32">Correct {coin_symbol} address</span>'
            )

    def prepare(self):
        try:
            addresses = self._selected_addresses()
            coin_symbol, address_type = check_sources(addresses)
            coin = coins[coin_symbol]
            if not coin.get('apis'):
                raise ValueError(f'No API has been defined for the coin {coin_symbol}')
            destination = parse_address(self.destination.text(), coin_symbol)
            satoshis = parse_amount(self.amount.text())
            fee = parse_int(self.fee.text(), 'Fee', minimum=0)
            minimum, maximum, limit = parse_thresholds(
                self.minimum.text(), self.maximum.text(), self.limit.text()
            )
            broadcast, target = self._get_broadcast(coin, coin_symbol)
        except ValueError as error:
            self.app.show_error(error)
            return
        wif_private_keys = [self.app.wallet.private_key_wif(address) for address in addresses]
        source_addresses = [address.address for address in addresses]

        def prepare_transaction():
            return prepare_from_private_keys(
                coin=coin,
                wif_private_keys=wif_private_keys,
                input_addresses=None,
                unlocking_scripts=None,
                destination_address=destination,
                satoshis=satoshis,
                fee=fee,
                minimum_input_threshold=minimum,
                maximum_input_threshold=maximum,
                limit_inputs=limit,
                address_type=address_type,
            )

        self.prepare_button.setEnabled(False)
        self.app.worker.run(
            prepare_transaction,
            lambda prepared: self._confirm(
                coin, coin_symbol, prepared, source_addresses, broadcast, target
            ),
            self._failed,
        )

    def _get_broadcast(self, coin, coin_symbol: str):
        """Return function broadcasting the transaction (None for the API) and its description."""
        if not self.p2p.isChecked() and not self.nodes.text().strip():
            return None, 'block explorer API'
        if 'network' not in coin:
            raise ValueError(f'No peer-to-peer network has been defined for the coin {coin_symbol}')
        nodes = parse_nodes(self.nodes.text(), coin['network']['port'])

        def broadcast(raw_transaction):
            return json.dumps({'txid': broadcast_transaction(coin, raw_transaction, nodes)})

        return broadcast, 'peer-to-peer network'

    def _confirm(self, coin, coin_symbol, prepared, source_addresses, broadcast, target):
        self.prepare_button.setEnabled(True)
        rows = describe_transaction(prepared, coin_symbol, source_addresses, target)
        if not confirm(self, 'Confirm transaction', rows, 'Send'):
            return
        self.prepare_button.setEnabled(False)
        self.app.worker.run(
            lambda: extract_txid(broadcast_prepared(coin, prepared, broadcast)),
            self._sent,
            self._failed,
        )

    def _sent(self, txid: str):
        self.prepare_button.setEnabled(True)
        self.amount.clear()
        show_text(self, 'Transaction sent', 'Transaction id', txid)

    def _failed(self, error):
        self.prepare_button.setEnabled(True)
        self.app.show_error(error)
```

- [ ] **Step 2:** lint + import. **Step 3:** `git commit -m "Rewrite GUI send tab with Qt"`

---

### Task 13: Okno główne, `app.py`, smoke testy

**Files:** Modify (przepisane): `multicrypto/gui/window.py`, `multicrypto/gui/app.py`; Test: `tests/test_gui.py` (dopisane)

- [ ] **Step 1: Testy — dopisz do `tests/test_gui.py`**

Import na górze (pod istniejącym): 
```python
from unittest.mock import Mock  # noqa: E402

from nacl import pwhash  # noqa: E402

from multicrypto.gui.window import MainWindow  # noqa: E402
from multicrypto.wallet import WalletFile  # noqa: E402

BTC_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'
```
Na końcu:
```python
@pytest.fixture
def window(qapp, tmp_path):
    wallet_file = WalletFile(
        str(tmp_path / 'wallet.mcw'), pwhash.argon2id.OPSLIMIT_MIN, pwhash.argon2id.MEMLIMIT_MIN
    )
    window = MainWindow(wallet_file)
    yield window
    window.timer.stop()
    qapp.removeEventFilter(window)


def unlock(window):
    window.show_wallet(window.wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE))


def test_wallet_is_shown_when_unlocked_and_cleared_when_locked(window):
    unlock(window)
    account = window.wallet.accounts[0]

    address = window.modify_wallet(lambda wallet: wallet.new_address(account.id, 'Savings'))

    tree = window.wallet_tab.tree
    assert 'unlocked' in window.status.text()
    assert window.wallet.fingerprint in window.status.text()
    assert tree.topLevelItemCount() == 1
    assert tree.topLevelItem(0).child(0).text(2) == address.address
    assert window.balance_tab.address_box.count() == 1
    assert window.send_tab.sources.count() == 1

    window.lock()

    assert window.wallet is None
    assert not window.wallet_file.is_unlocked
    assert tree.topLevelItemCount() == 0
    assert window.send_tab.sources.count() == 0
    assert window.balance_tab.address_box.count() == 0
    assert 'locked' in window.status.text()


def test_imported_keys_are_shown_in_separate_group(window):
    unlock(window)

    window.modify_wallet(lambda wallet: wallet.add_wif('Old', 'BTC', BTC_WIF, 'p2wpkh'))

    group = window.wallet_tab.tree.topLevelItem(1)
    assert group.text(0).startswith('Imported keys')
    assert group.child(0).text(0) == 'Old'


def test_modify_wallet_reverts_change_when_saving_fails(window, monkeypatch):
    unlock(window)
    account_id = window.wallet.accounts[0].id
    monkeypatch.setattr(window.wallet_file, 'save', Mock(side_effect=OSError('disk full')))

    with pytest.raises(OSError):
        window.modify_wallet(lambda wallet: wallet.new_address(account_id, 'Savings'))

    assert window.wallet.accounts[0].addresses == []


def test_wallet_is_locked_after_inactivity(window):
    unlock(window)
    window.last_activity -= window.auto_lock_seconds

    window.tick()

    assert window.wallet is None


def test_send_tab_validates_destination(window):
    unlock(window)
    account = window.wallet.accounts[0]
    window.modify_wallet(lambda wallet: wallet.new_address(account.id, 'Savings'))
    window.send_tab.sources.item(0).setSelected(True)

    window.send_tab.destination.setText('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu')
    assert 'Correct BTC address' in window.send_tab.destination_status.text()

    window.send_tab.destination.setText('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyx')
    assert 'Incorrect bech32 address' in window.send_tab.destination_status.text()
```

- [ ] **Step 2: FAIL**, potem **`multicrypto/gui/window.py`**

```python
"""Main window: wallet file handling, tabs and automatic locking."""

import copy
import os
import time
from typing import Optional

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from multicrypto.gui.balance_tab import BalanceTab
from multicrypto.gui.create_wizard import CreateWalletWizard
from multicrypto.gui.dialogs import SecretDialog, UnlockDialog, ask_password, mnemonic_grid
from multicrypto.gui.forms import describe_error
from multicrypto.gui.send_tab import SendTab
from multicrypto.gui.wallet_tab import WalletTab
from multicrypto.gui.worker import Worker
from multicrypto.wallet import MIN_PASSWORD_LENGTH, Wallet, WalletFile

AUTO_LOCK_SECONDS = 5 * 60
WALLET_FILE_FILTER = 'multicrypto wallet (*.mcw);;All files (*)'
ACTIVITY_EVENTS = (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove)


def _opened(wallet: Wallet) -> Wallet:
    """Derive the addresses in background, so showing the wallet doesn't block the GUI."""
    wallet.addresses()
    return wallet


class MainWindow(QMainWindow):
    def __init__(self, wallet_file: WalletFile, auto_lock_seconds: int = AUTO_LOCK_SECONDS):
        super().__init__()
        self.wallet_file = wallet_file
        self.auto_lock_seconds = auto_lock_seconds
        self.wallet: Optional[Wallet] = None
        self.last_activity = time.monotonic()
        self.worker = Worker(self)
        self.setWindowTitle('multicrypto')
        self.resize(1150, 700)
        self.wallet_tab = WalletTab(self)
        self.balance_tab = BalanceTab(self)
        self.send_tab = SendTab(self)
        self.tabs = (self.wallet_tab, self.balance_tab, self.send_tab)
        self.tab_widget = QTabWidget()
        for tab, title in zip(self.tabs, ('Wallet', 'Balance', 'Send'), strict=True):
            self.tab_widget.addTab(tab, title)
        self.locked_message = QLabel()
        self.locked_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.unlock_button = QPushButton('Unlock...')
        self.locked_screen = QWidget()
        locked_layout = QVBoxLayout(self.locked_screen)
        locked_layout.addStretch()
        locked_layout.addWidget(self.locked_message)
        for button, slot in (
            (self.unlock_button, self.unlock),
            (QPushButton('Create new wallet...'), self.new_wallet),
            (QPushButton('Open wallet file...'), self.open_wallet),
        ):
            button.clicked.connect(lambda _checked=False, slot=slot: slot())
            locked_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        locked_layout.addStretch()
        self.stack = QStackedWidget()
        self.stack.addWidget(self.locked_screen)
        self.stack.addWidget(self.tab_widget)
        self.setCentralWidget(self.stack)
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        self._create_menu()
        QApplication.instance().installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self._show_locked()

    def _create_menu(self):
        file_menu = self.menuBar().addMenu('&File')
        for text, slot in (
            ('New wallet...', self.new_wallet),
            ('Open wallet...', self.open_wallet),
            ('Change password...', self.change_password),
            ('Show mnemonic...', self.show_mnemonic),
            ('Lock', self.lock),
            ('Quit', self.close),
        ):
            action = file_menu.addAction(text)
            action.triggered.connect(lambda _checked=False, slot=slot: slot())

    def eventFilter(self, watched, event):
        if event.type() in ACTIVITY_EVENTS:
            self.last_activity = time.monotonic()
        return False

    def closeEvent(self, event):
        self.lock()
        super().closeEvent(event)

    def start(self):
        """Ask for the password when the wallet file exists."""
        if self.wallet_file.exists():
            self.unlock()

    def select_tab(self, tab: QWidget):
        self.tab_widget.setCurrentWidget(tab)

    def tick(self):
        """Update the status and lock the wallet after inactivity, called every second."""
        if self.wallet is not None:
            self._update_unlocked_status()

    def _update_unlocked_status(self):
        remaining = self.auto_lock_seconds - (time.monotonic() - self.last_activity)
        if remaining <= 0:
            self.lock()
            return
        minutes, seconds = divmod(int(remaining), 60)
        self.status.setText(
            f'{self.wallet_file.path} · fingerprint {self.wallet.fingerprint} · unlocked · '
            f'locks in {minutes}:{seconds:02d}'
        )

    def _show_locked(self):
        if self.wallet_file.exists():
            self.locked_message.setText(f'Wallet {self.wallet_file.path} is locked')
            self.unlock_button.setEnabled(True)
        else:
            self.locked_message.setText(
                f'Wallet file {self.wallet_file.path} does not exist.\n'
                'Create a new wallet or open another wallet file.'
            )
            self.unlock_button.setEnabled(False)
        self.status.setText(f'{self.wallet_file.path} · locked')
        self.stack.setCurrentWidget(self.locked_screen)

    def show_wallet(self, wallet: Wallet):
        self.wallet = wallet
        self.last_activity = time.monotonic()
        self.stack.setCurrentWidget(self.tab_widget)
        for tab in self.tabs:
            tab.refresh()
        self._update_unlocked_status()

    def lock(self):
        if self.wallet is not None:
            self.wallet.close()
        self.wallet = None
        self.wallet_file.lock()
        for tab in self.tabs:
            tab.clear()
        self._show_locked()

    def _derive_keys(self, message: str, func, on_success):
        """Run operation deriving keys from the password and the passphrase in background."""
        self.status.setText(message)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        def succeeded(result):
            QApplication.restoreOverrideCursor()
            on_success(result)

        def failed(error):
            QApplication.restoreOverrideCursor()
            if self.wallet is None:
                self._show_locked()
            else:
                self._update_unlocked_status()
            self.show_error(error)

        self.worker.run(func, succeeded, failed)

    def unlock(self):
        dialog = UnlockDialog(self, self.wallet_file.path)
        if not dialog.exec():
            return
        password, passphrase = dialog.values()
        wallet_file = self.wallet_file
        self._derive_keys(
            'Unlocking...',
            lambda: _opened(wallet_file.unlock(password, passphrase)),
            self.show_wallet,
        )

    def new_wallet(self):
        path = self.wallet_file.path
        if self.wallet_file.exists():
            path, _ = QFileDialog.getSaveFileName(
                self,
                'New wallet file',
                os.path.join(os.path.dirname(os.path.abspath(path)), 'wallet.mcw'),
                WALLET_FILE_FILTER,
            )
            if not path:
                return
        wizard = CreateWalletWizard(self, path)
        if not wizard.exec():
            return
        password, mnemonic, passphrase = wizard.values()
        self.lock()
        wallet_file = self.wallet_file = WalletFile(path)
        self._derive_keys(
            'Creating wallet...',
            lambda: _opened(wallet_file.create(password, mnemonic, passphrase)),
            self._created,
        )

    def _created(self, wallet: Wallet):
        self.show_wallet(wallet)
        QMessageBox.information(
            self,
            'New wallet',
            f'The wallet {self.wallet_file.path} has been created, its fingerprint is '
            f'{wallet.fingerprint}.',
        )

    def open_wallet(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            'Open wallet file',
            os.path.dirname(os.path.abspath(self.wallet_file.path)),
            WALLET_FILE_FILTER,
        )
        if not path:
            return
        self.lock()
        self.wallet_file = WalletFile(path)
        self._show_locked()
        self.unlock()

    def change_password(self):
        if self.wallet is None:
            return
        old_password = ask_password(self, 'Change password', 'Current password')
        if old_password is None:
            return
        new_password = ask_password(
            self,
            'Change password',
            f'New password (at least {MIN_PASSWORD_LENGTH} characters)',
            new_password=True,
        )
        if new_password is None:
            return
        wallet_file, wallet = self.wallet_file, self.wallet
        self._derive_keys(
            'Changing password...',
            lambda: wallet_file.change_password(old_password, new_password, wallet),
            lambda _result: self._password_changed(),
        )

    def _password_changed(self):
        self._update_unlocked_status()
        QMessageBox.information(self, 'Change password', 'The password has been changed')

    def show_mnemonic(self):
        if self.wallet is None:
            return
        password = ask_password(self, 'Show mnemonic', 'Enter the wallet password')
        if password is None:
            return
        self.worker.run(
            lambda: self.wallet_file.verify_password(password),
            self._show_mnemonic,
            self.show_error,
        )

    def _show_mnemonic(self, correct: bool):
        if not correct:
            QMessageBox.warning(self, 'Show mnemonic', 'Wrong password')
            return
        if self.wallet is None:
            return
        SecretDialog(
            self,
            'Mnemonic',
            'The passphrase is not shown, the mnemonic restores the wallet only with it.',
            mnemonic_grid(self.wallet.mnemonic),
        ).exec()

    def modify_wallet(self, change):
        """Apply the change to the wallet and save it, the change is reverted when saving fails."""
        snapshot = copy.deepcopy((self.wallet.accounts, self.wallet.imported))
        result = change(self.wallet)
        try:
            self.wallet_file.save(self.wallet)
        except BaseException:
            self.wallet.accounts, self.wallet.imported = snapshot
            raise
        for tab in self.tabs:
            tab.refresh()
        return result

    def show_error(self, error: BaseException):
        QMessageBox.critical(self, 'Error', describe_error(error))
```

- [ ] **Step 3: `multicrypto/gui/app.py`**

```python
"""Entry point of the multicrypto-gui command."""

import argparse
import logging
import sys

from multicrypto.validators import check_positive


def get_args():
    parser = argparse.ArgumentParser(
        description='Graphical user interface of multicrypto with HD wallet (BIP-39 mnemonic '
        'with passphrase) kept in encrypted wallet file'
    )
    parser.add_argument(
        '-w',
        '--wallet',
        type=str,
        required=False,
        default=None,
        help='Path of the wallet file, default is ~/.multicrypto/wallet.mcw',
    )
    parser.add_argument(
        '-l',
        '--auto_lock',
        type=check_positive,
        required=False,
        default=5,
        help='Lock the wallet after given number of minutes of inactivity. Default 5 minutes',
    )
    return parser.parse_args()


def main():
    args = get_args()
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        from multicrypto.gui.window import MainWindow
        from multicrypto.wallet import DEFAULT_PATH, WalletFile
    except ModuleNotFoundError as error:
        if error.name and error.name.split('.')[0] in ('nacl', 'PySide6'):
            sys.exit(
                'multicrypto-gui requires optional dependencies, install them with: '
                'pip install "multicrypto[gui]"'
            )
        raise
    app = QApplication(sys.argv[:1])
    app.setStyle('Fusion')
    window = MainWindow(WalletFile(args.wallet or DEFAULT_PATH), args.auto_lock * 60)
    window.show()
    QTimer.singleShot(0, window.start)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: PASS — całość**

Run: `uv run ruff format . && uv run ruff check . && uv run python -m pytest -q`
Expected: wszystkie PASS, testy GUI nie są SKIP (`-rs` nie pokazuje pominięć).

- [ ] **Step 5: Zrzuty ekranu (weryfikacja wizualna)** — skrypt w scratchpadzie tworzy okno offscreen
  z portfelem testowym („abandon … about”, passphrase testowe), dodaje adresy, importowany klucz, i zapisuje
  `QWidget.grab().save(...)` dla: ekranu blokady, każdej zakładki, `ConfirmDialog`, `CreateWalletWizard`
  (strona słów), `SecretDialog` z mnemonikiem. Obejrzeć PNG-i; poprawić układ, jeśli coś się nie mieści.

- [ ] **Step 6: Commit**

```bash
git add multicrypto/gui/window.py multicrypto/gui/app.py tests/test_gui.py
git commit -m "Rewrite GUI main window with Qt for HD wallet"
```

---

### Task 14: CI i README

**Files:** Modify: `.github/workflows/run_tests.yml`, `README.md`

- [ ] **Step 1: CI** — przed krokiem „Install dependencies” dodać:

```yaml
      - name: Install system libraries used by Qt
        run: sudo apt-get update && sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3
```
oraz w kroku „Run tests” usunąć `xvfb-run -a ` (testy ustawiają `QT_QPA_PLATFORM=offscreen` same).

- [ ] **Step 2: README** — w liście komend punkt 9 i akapit instalacji zamienić na:

```markdown
 9. `multicrypto-gui` - graphical user interface with HD wallet (BIP-39 mnemonic with passphrase)

The GUI requires optional dependencies PyNaCl and PySide6:
```bash
pip install "multicrypto[gui]"
```
```

a sekcję „9. Graphical user interface” na:

```markdown
9. Graphical user interface:
```bash
multicrypto-gui --wallet=<WALLET FILE> --auto_lock=<MINUTES>
```
The wallet is a BIP-39 mnemonic protected with a passphrase, keys are derived according to BIP-32
with BIP-44 (p2pkh), BIP-49 (p2sh-p2wpkh), BIP-84 (p2wpkh) and BIP-86 (p2tr) paths and SLIP-44 coin
types, so the addresses can be restored in other wallets (e.g. Electrum, Sparrow). The mnemonic,
accounts, address labels and imported private keys are kept in a single file (by default
`~/.multicrypto/wallet.mcw`) encrypted with XChaCha20-Poly1305 using the key derived from the
password with Argon2id. The passphrase is never saved: it is entered every time the wallet is
unlocked, and the fingerprint of the master key detects a mistyped passphrase. Tabs:
- **Wallet** - accounts with receiving addresses created on demand, imported private keys (they are
  not covered by the mnemonic backup), address balances, showing private keys and the mnemonic
  (after entering the password again),
- **Balance** - unspent outputs of the wallet address or any other address (like `checkaddress`),
- **Send** - send funds from one or more wallet addresses (like `sendcrypto`), the transaction is
  shown for confirmation before it is broadcast, the change goes back to the source address.

The wallet is locked after 5 minutes of inactivity (`--auto_lock`). Python cannot reliably remove
data from memory, so the keys of the unlocked wallet stay in memory of the process until it is
locked. Keep the mnemonic and the passphrase written down separately - the funds cannot be
recovered without both of them.
```

- [ ] **Step 3: Commit** — `git add .github README.md && git commit -m "Run Qt GUI tests offscreen in CI and describe HD wallet in README"`

---

### Task 15: Weryfikacja końcowa

- [ ] `uv run ruff check . && uv run ruff format --check .`
- [ ] `uv run python -m pytest -q -rs` — wszystko PASS, brak SKIP testów GUI.
- [ ] `uv build` → wheel zawiera `multicrypto/bip39_english.txt`, `multicrypto/bip32.py`, `multicrypto/gui/create_wizard.py`; METADATA: `Requires-Dist: pyside6-essentials>=6.8; extra == 'gui'`.
- [ ] `uv run multicrypto-gui --help`; brak PySide6 → czytelny komunikat
  (`uv run python -c "import sys; sys.modules['PySide6'] = None; sys.argv = ['x']; from multicrypto.gui.app import main; main()"`).
- [ ] `grep -rn tkinter multicrypto tests` — brak wystąpień.
- [ ] Ręcznie (użytkownik): `uv run multicrypto-gui --wallet /tmp/test.mcw` — kreator, odblokowanie, zły passphrase,
  TBTC/TLTC p2wpkh i p2tr: nowe adresy, zasilenie z `testnet_wallet.json` (sendcrypto), wysyłka z GUI;
  zgodność adresów ze Sparrow/Electrum dla tego samego mnemonika i passphrase.
