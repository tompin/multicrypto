# GUI z portfelem HD (BIP-39 + BIP-32) — projekt

Data: 2026-10-27. Zastępuje: `2026-10-26-gui-design.md` (pojedyncze klucze WIF, tkinter).

## Cel

Graficzny interfejs (PySide6) do komend multicrypto, zbudowany wokół portfela HD: klucze pochodzą
z mnemonika BIP-39 zabezpieczonego passphrase, wyprowadzane są według BIP-32/44/49/84/86. Mnemonik
jest zapisywany na dysk wyłącznie zaszyfrowany, w jednym pliku; passphrase nigdy nie trafia na dysk.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Biblioteka GUI | PySide6 (`PySide6-Essentials`), LGPL; tkinter usunięty |
| Szyfrowanie pliku | PyNaCl: XChaCha20-Poly1305 + Argon2id (bez zmian względem etapu 1) |
| Passphrase BIP-39 | wpisywane przy każdym odblokowaniu, nigdy zapisywane; w pliku tylko fingerprint klucza głównego |
| BIP-39 / BIP-32 | własna implementacja na bibliotece standardowej (`hashlib`, `hmac`, `secrets`) i secp256k1 projektu |
| Importowane WIF | wspierane obok seeda, w osobnej sekcji „Imported keys” |
| Adresy HD | konta (moneta + typ + numer konta), adresy odbiorcze tworzone na żądanie, reszta wraca na adres źródłowy |
| Mnemonik | generowany 24 słowa; import 12/15/18/21/24 słów; tylko angielska lista słów |
| Passphrase | wymagane (niepuste), przy tworzeniu wpisywane dwukrotnie |
| Format pliku | wersja 2; wersja 1 (etap 1, niewydany) odrzucana jako nieobsługiwana, bez migracji |
| Teksty GUI | po angielsku, jak README i CLI |

Pozostaje z etapu 1: szyfrowanie i zapis atomowy pliku, ścisła walidacja WIF, `gui/forms.py`,
podział `prepare` / `broadcast` w `multicrypto/api.py`.

## Etapy

| Etap | Zakres |
|------|--------|
| 1 (ten dokument) | portfel HD + importowane WIF, Balance (`checkaddress`), Send (`sendcrypto`) |
| 2 | Sweep (`sweepaddress`), Podpisz / Weryfikuj, kod QR adresu |
| 3 | Translacja adresów i kluczy, Vanity (`genaddress`) |

Poza zakresem: pełne skanowanie HD z gap limit i łańcuchem reszty, zmiana passphrase istniejącego
portfela, eksport xpub, P2SH z ręcznymi skryptami, inne listy słów niż angielska.

## Moduły

```
multicrypto/
  bip39.py            # mnemonik: generowanie, walidacja (słowa, liczba, suma kontrolna), seed
  bip39_english.txt   # oficjalna lista 2048 słów BIP-39
  bip32.py            # klucz główny z seeda, derywacja, parsowanie ścieżki, fingerprint
  coins.py            # + 'slip44' dla monet z numerem w rejestrze SLIP-44
  wallet.py           # model v2: seed + konta HD + importowane WIF, plik zaszyfrowany
  api.py              # bez zmian (PreparedTransaction, prepare_*, broadcast_prepared)
  gui/
    __init__.py
    app.py            # main() komendy multicrypto-gui, komunikaty o brakujących zależnościach
    forms.py          # parsowanie i walidacja formularzy (bez Qt)
    worker.py         # QThreadPool + QRunnable, wynik sygnałem do wątku GUI
    dialogs.py        # hasło/odblokowanie, potwierdzenie, pokazanie sekretu, tekst z kopiowaniem
    create_wizard.py  # QWizard tworzenia / odtwarzania portfela
    wallet_tab.py     # drzewo kont i adresów, importowane klucze, akcje
    balance_tab.py    # UTXO adresu (checkaddress)
    send_tab.py       # wysyłka z podglądem i potwierdzeniem (sendcrypto)
    window.py         # QMainWindow: menu, ekran blokady, zakładki, auto-blokada
```

`pyproject.toml`: extra `gui = ["PyNaCl>=1.5", "PySide6-Essentials>=6.8"]`, w grupie `dev` przypięte
wersje obu, skrypt `multicrypto-gui = "multicrypto.gui.app:main"`. `bip39_english.txt` musi trafić do
wheela (sprawdzić `uv build`).

### `bip39.py`

- `generate_mnemonic(strength=256) -> str` — entropia z `secrets.token_bytes`.
- `entropy_to_mnemonic(entropy: bytes) -> str` (do wektorów testowych).
- `validate_mnemonic(mnemonic) -> None` — `ValueError` z opisem: nieznane słowo z numerem pozycji,
  zła liczba słów, zła suma kontrolna.
- `mnemonic_to_seed(mnemonic, passphrase) -> bytes` — `pbkdf2_hmac('sha512', NFKD(mnemonic),
  b'mnemonic' + NFKD(passphrase), 2048)`; mnemonik normalizowany (małe litery, pojedyncze spacje).

### `bip32.py`

- `ExtendedKey` (dataclass, frozen): `private_key: int`, `chain_code: bytes`, `depth`,
  `parent_fingerprint`, `child_number`; `public_key` (punkt), `fingerprint` (4 B hash160
  skompresowanego klucza publicznego), `derive_child(index)`, `derive_path(path)`.
- `master_key_from_seed(seed) -> ExtendedKey` (HMAC-SHA512 z kluczem `b'Bitcoin seed'`).
- `parse_path("m/84'/0'/0'/0/5") -> List[int]` (`'` lub `h` = hardened); `ValueError` dla złych ścieżek.
- `HARDENED = 0x80000000`; obsługa przypadku nieprawidłowego klucza potomnego (IL ≥ n lub klucz 0)
  przez przejście do następnego indeksu zgodnie z BIP-32.
- `repr` nie zawiera klucza prywatnego.

### Ścieżki i SLIP-44

`m/purpose'/slip44'/account'/0/index`, purpose: p2pkh → 44, p2sh-p2wpkh → 49, p2wpkh → 84,
p2tr → 86. Testnety: 1. Numery SLIP-44 dodawane do `coins.py` tylko po weryfikacji z oficjalnym
rejestrem (`satoshilabs/slips/slip-0044.md`); moneta bez `slip44` jest dostępna tylko dla
importowanych WIF. Typy adresów konta ograniczone do `get_address_types(coin)`.

## Plik portfela

Nagłówek i szyfrowanie jak w etapie 1 (magic `MCWALLET`, opslimit, memlimit, sól, nonce jako AAD;
Argon2id `MODERATE`; zapis `.tmp` + `fsync` + `os.replace`, plik `0600`, katalog `0700`), ale
**wersja formatu 2**. Zaszyfrowana treść:

```json
{
  "seed": {"mnemonic": "abandon ... art", "fingerprint": "73c5da0a"},
  "accounts": [
    {"id": "<uuid4>", "label": "BTC savings", "coin": "BTC", "address_type": "p2wpkh", "account": 0,
     "addresses": [{"index": 0, "label": "Savings", "created": "2026-10-27T10:00:00Z"}]}
  ],
  "imported": [{"id": "<uuid4>", "label": "Old miner", "coin": "ZEN", "wif": "…",
                "address_type": "p2pkh", "created": "…"}]
}
```

- Passphrase nie jest zapisywane; fingerprint klucza głównego (hex, 4 B) służy do wykrycia
  literówki w passphrase.
- Adresy i ścieżki są wyliczane, nie zapisywane.
- Unikalność: konto (moneta, typ, numer konta); adres (konto, index); importowany klucz
  (moneta, WIF, typ).

### API `multicrypto/wallet.py`

- `WalletError` — błędy pliku i odblokowania (złe hasło / uszkodzony plik, nieobsługiwany format,
  niezgodny fingerprint, portfel zablokowany).
- `HDAccount`, `HDAddress`, `ImportedKey` (dataclasses; `repr` bez sekretów).
- `WalletAddress` — jednolity widok adresu dla GUI: `id`, `label`, `coin`, `address_type`, `path`
  (np. `m/84'/0'/0'/0/1` albo `None` dla importowanego), `address`, `account_id` (lub `None`).
- `Wallet`:
  - `fingerprint`, `accounts`, `imported`;
  - `add_account(label, coin, address_type, account=None)` — domyślnie kolejny wolny numer konta;
  - `new_address(account_id, label) -> WalletAddress` — kolejny index;
  - `rename(item_id, label)`, `remove_account(account_id)`, `remove_address(account_id, index)`,
    `add_wif(...)`, `remove_imported(id)`;
  - `addresses() -> List[WalletAddress]`;
  - `private_key_wif(address: WalletAddress) -> str` — z seeda (klucz konta w cache) albo importowany;
  - `mnemonic` dostępny tylko do „Show mnemonic”.
- `WalletFile(path, opslimit, memlimit)`:
  - `create(password, mnemonic, passphrase) -> Wallet` — waliduje hasło (≥ 10 znaków), mnemonik,
    passphrase (niepuste); tworzy domyślne konto BTC p2wpkh #0;
  - `unlock(password, passphrase) -> Wallet` — hasło → odszyfrowanie; mnemonik + passphrase → seed →
    fingerprint; niezgodność → `WalletError("This passphrase gives wallet <fp>, but the wallet was
    created with <fp>. Check the passphrase.")`, stan pozostaje zablokowany;
  - `save(wallet)`, `verify_password(password)`, `change_password(old, new)`, `lock()`.
- Po zablokowaniu nie ma referencji do klucza pliku, seeda ani kluczy kont.

## Bezpieczeństwo

- Argon2id i PBKDF2 w wątku roboczym.
- Auto-blokada po 5 min bezczynności (`--auto_lock`), czyści widoki i klucze.
- „Show private key” i „Show mnemonic” wymagają ponownego hasła pliku; okno zamyka się po 30 s;
  mnemonik bez możliwości kopiowania, WIF tylko do odczytu.
- Do schowka kopiowane są tylko adresy i txid.
- Usuwanie konta / adresu ostrzega, że seed nadal odtwarza te adresy; usuwanie importowanego klucza
  ostrzega, że nie ma go w kopii mnemonika.
- Znane ograniczenie (README): Python nie gwarantuje wyczyszczenia sekretów z pamięci.

## Ekrany

**Start / ekran blokady:** brak pliku → „Create new wallet…” / „Open wallet file…”; plik istnieje →
„Unlock…” (dialog z polami: hasło pliku, passphrase).

**Kreator (`QWizard`):**
1. Hasło pliku (dwukrotnie, ≥ 10 znaków).
2. Wybór: „Generate new seed” / „Restore from mnemonic”.
3. Generate: 24 słowa w siatce 4×6 (bez kopiowania), ostrzeżenie o zapisaniu na papierze; następna
   strona: wpisanie 3 losowo wybranych słów. Restore: pole tekstowe z walidacją na bieżąco.
4. Passphrase (dwukrotnie, niepuste) z ostrzeżeniem, że bez niego seed nic nie odtworzy.
5. Utworzenie pliku w tle (Argon2 + PBKDF2), pokazanie fingerprintu.

**Okno główne:** menu File (New wallet…, Open…, Change password…, Show mnemonic…, Lock, Quit),
zakładki Wallet / Balance / Send, pasek stanu (ścieżka, fingerprint, odliczanie auto-blokady).
Styl Fusion, jasny / ciemny zgodnie z systemem.

**Wallet:** `QTreeView` — konta (etykieta, ścieżka konta) → adresy (etykieta, `0/index`, adres,
saldo) oraz grupa „Imported keys (not in mnemonic backup)”. Przyciski: New account…, New address…,
Import WIF…, Copy address, Show key…, Rename…, Remove…, Refresh balances. Menu kontekstowe: Copy
address, Check UTXO, Send from, Rename, Show key.

**Balance:** UTXO adresu z portfela albo dowolnego adresu (moneta z API), filtry min/max/limit,
tabela txid / potwierdzenia / satoshi / kwota + suma.

**Send:** źródła — wiele adresów z portfela tej samej monety i typu; adres docelowy z walidacją,
kwota (`Decimal`), opłata (domyślnie 10000), „Advanced” (min/max/limit, P2P, węzły). Prepare (w tle)
→ dialog potwierdzenia (From, To, Amount, Fee, Change, Inputs, Size, Broadcast; domyślnie Cancel) →
broadcast (w tle) → txid z przyciskiem Copy.

## Wątki i błędy

`Worker.run(func, on_success, on_error)` — `QRunnable` w `QThreadPool.globalInstance()`, wynik przez
sygnał (połączenie kolejkowane do wątku GUI). Błędy znane (`ValueError`, `OSError`, `WalletError`,
`InsufficientFundsError`, `NetworkError`) → `QMessageBox` z treścią; nieznane → ogólny komunikat
i `logger.exception`.

## Testy

- `tests/test_bip39.py`: wektory Trezora (`vectors.json`, passphrase `TREZOR`), błędy walidacji,
  normalizacja NFKD.
- `tests/test_bip32.py`: wektory testowe BIP-32 1–3, parsowanie ścieżek.
- `tests/test_wallet.py`: dla „abandon ×11 about” bez passphrase adresy z dokumentów BIP-44
  (`1LqBGSKuX5yYUonjxT5qGfpUsXKYYWeabA`), BIP-49 (weryfikowany z dokumentem BIP-49), BIP-84
  (`bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu`), BIP-86
  (`bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr`); zły passphrase → `WalletError`
  z fingerprintami; passphrase nie występuje w pliku; v1 odrzucony; konta / adresy / importowane WIF
  w cyklu zapisu i odczytu; dotychczasowe testy szyfrowania.
- `tests/test_gui_forms.py`: helpery formularzy.
- `tests/test_gui.py`: smoke test z `QT_QPA_PLATFORM=offscreen`, `pytest.importorskip('PySide6')`.
- Ręcznie: wysyłka TBTC i TLTC z adresów HD p2wpkh i p2tr; zgodność adresów ze Sparrow lub Electrum
  dla tego samego mnemonika i passphrase.

## Kolejność prac

1. `bip39` + `bip32` + `slip44` w `coins.py`.
2. Model `wallet.py` v2.
3. Dostosowanie `forms.py`.
4. Usunięcie warstwy tkinter, warstwa PySide6 (worker, dialogi, kreator, zakładki, okno).
5. CI bez `xvfb-run`, README.
