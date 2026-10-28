# Wybór adresu portfela i nowy adres z typem — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pole Coin filtruje adresy portfela w zakładkach Balance, Sweep, Send i Sign, lista
pokazuje sam adres ze szczegółami pod nią, a New address pozwala wybrać typ adresu.

**Architecture:** Wspólny widżet `WalletAddressPicker` i funkcje opisu adresu w `forms.py`;
zakładki filtrują adresy po monecie i przekazują je do pickera (Send: tabela).

**Tech Stack:** Python 3, PySide6, pytest (`uv run pytest`), ruff.

Specyfikacja: `docs/superpowers/specs/2026-10-29-address-picker-design.md`.

---

### Task 1: Opis adresu i podgląd następnego adresu

**Files:** `multicrypto/gui/forms.py`, `multicrypto/wallet.py`, `multicrypto/gui/wallet_tab.py`,
testy `tests/test_gui_forms.py`, `tests/test_wallet.py`

- [ ] Testy: `address_details(wallet, address)` dla adresu z grupy (`[('Account', 'Bitcoin #0'),
  ('Address type', 'Native SegWit (p2wpkh)'), ('Path', "m/84'/0'/0'/0/0"), ('Label', 'Address
  0')]`) i klucza importowanego (`Imported key`, `—`); `next_receiving_address` zwraca `0/1` i nie
  dodaje adresu.
- [ ] FAIL → implementacja (`ADDRESS_TYPE_NAMES` przeniesione do `forms.py`, import w
  `wallet_tab.py`) → PASS → commit „Add descriptions of wallet addresses”.

### Task 2: `WalletAddressPicker`

**Files:** Create `multicrypto/gui/address_picker.py`, test `tests/test_gui.py`

- [ ] Test: po `set_addresses` lista ma teksty adresów, szczegóły pokazują wybrany adres,
  `select(id)` zmienia szczegóły, zaznaczenie zostaje po ponownym `set_addresses`, `clear()`
  czyści szczegóły.
- [ ] FAIL → implementacja → PASS → commit „Add wallet address picker”.

### Task 3: Balance

- [ ] Testy: Coin filtruje adresy (`TBTC` → tylko adresy TBTC), `check_address` z adresem LTC
  ustawia Coin na LTC i zaznacza adres; dostosować `test_wallet_is_shown...` (liczba adresów BTC).
- [ ] Implementacja: Coin na górze, `WalletAddressPicker` przy „Wallet address”, „Other
  address” używa tego samego Coin → PASS → commit „Filter wallet addresses by coin in balance
  tab”.

### Task 4: Sweep

- [ ] Testy: Coin filtruje źródła i cele, `select_source` ustawia Coin, klucz zewnętrzny używa
  Coin; dostosować istniejące testy Sweep.
- [ ] Implementacja: Coin na górze (wspólny dla źródła i klucza), pickery źródła i celu, `_source_coin`
  = Coin → PASS → commit „Filter wallet addresses by coin in sweep tab”.

### Task 5: Send

- [ ] Testy: tabela źródeł z kolumnami i filtrem Coin, `select_source` ustawia Coin i zaznacza
  wiersz; dostosować testy Send.
- [ ] Implementacja: Coin (monety z API), `QTableWidget` z zaznaczaniem wierszy → PASS → commit
  „Show send sources in table filtered by coin”.

### Task 6: Sign

- [ ] Testy: Coin filtruje adresy, taproot nie ma na liście, `select_address` ustawia Coin;
  zastąpić `test_taproot_address_cannot_be_selected_for_signing`.
- [ ] Implementacja → PASS → commit „Filter signing addresses by coin”.

### Task 7: New address z typem

**Files:** `multicrypto/gui/wallet_tab.py`, test `tests/test_gui.py`

- [ ] Testy: domyślne wartości z zaznaczenia (grupa → Native SegWit, DOGE → Legacy, podkonto →
  jego typ, adres → typ jego konta), podgląd ścieżki i adresu, OK dodaje adres z etykietą;
  zastąpić `test_new_address_needs_address_type`.
- [ ] Implementacja `NewAddressDialog`, `new_address()` bez `QInputDialog` → PASS → commit „Choose
  address type of new address”.

### Task 8: README i weryfikacja

- [ ] README: zakładki z polem Coin, New address z wyborem typu. Commit.
- [ ] `uv run ruff check multicrypto tests`, `uv run ruff format --check multicrypto tests`,
  `uv run pytest -q`; zrzuty zakładek (offscreen) do obejrzenia.
