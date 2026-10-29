# Grupy kont — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Konto w zakładce Wallet to „moneta #N” z podkontami wszystkich typów adresów monety;
nowy i odtworzony portfel ma grupy #0 wszystkich monet z SLIP-44, skan monety idzie po grupach i
jest uruchamiany tylko na żądanie.

**Architecture:** Grupowanie w API `Wallet` (dataclass `AccountGroup` liczona z `accounts`, bez
zmiany formatu pliku) i w drzewie `WalletTab` (trzy poziomy). `discover()` skanuje numery kont dla
wszystkich typów naraz, `add_discovered()` zakłada pełne grupy.

**Tech Stack:** Python 3, PySide6, pytest (`uv run pytest`).

Specyfikacja: `docs/superpowers/specs/2026-10-28-account-groups-design.md`.

---

## Pliki

- `multicrypto/wallet.py` — `ADDRESS_TYPE_ORDER`, `group_address_types`, `group_label`,
  `AccountGroup`, metody grup w `Wallet`, `WalletFile.create`.
- `multicrypto/discovery.py` — `discover` po grupach, `add_discovered` z pełnymi grupami.
- `multicrypto/gui/wallet_tab.py` — drzewo grup, `NewAccountGroupDialog`, akcje grup.
- `multicrypto/gui/window.py` — bez skanu po odtworzeniu, komunikat.
- `README.md` — opis grup i skanu.
- Testy: `tests/test_wallet.py`, `tests/test_discovery.py`, `tests/test_gui.py`.

### Task 1: Grupy kont w modelu (odczyt)

**Files:** Modify `multicrypto/wallet.py`, Test `tests/test_wallet.py`

- [ ] **Step 1: Testy**

```python
def test_group_address_types_and_label():
    assert group_address_types('BTC') == ['p2tr', 'p2wpkh', 'p2sh-p2wpkh', 'p2pkh']
    assert group_address_types('DOGE') == ['p2pkh']
    assert group_label('BTC', 0) == 'Bitcoin #0'
    assert group_label('TBTC', 2) == 'Bitcoin Testnet #2'


def test_account_groups():
    wallet = Wallet.create(MNEMONIC, '')
    legacy = wallet.add_account('Savings', 'BTC', 'p2pkh', 0)
    native = wallet.add_account('Savings', 'BTC', 'p2wpkh', 0)
    doge = wallet.add_account('Doge', 'DOGE', 'p2pkh', 0)
    taproot = wallet.add_account('Other', 'BTC', 'p2tr', 1)
    nested = wallet.add_account('Different', 'BTC', 'p2sh-p2wpkh', 1)

    groups = wallet.account_groups()

    assert [(g.coin, g.number, g.label, g.accounts) for g in groups] == [
        ('BTC', 0, 'Savings', [native, legacy]),
        ('DOGE', 0, 'Doge', [doge]),
        ('BTC', 1, 'Bitcoin #1', [taproot, nested]),
    ]
    assert wallet.get_group('BTC', 1) == groups[2]
    with pytest.raises(KeyError):
        wallet.get_group('LTC', 0)
    assert wallet.next_group_number('BTC') == 2
    assert wallet.next_group_number('LTC') == 0
```

- [ ] **Step 2:** `uv run pytest tests/test_wallet.py -k "group" -q` → FAIL (ImportError).
- [ ] **Step 3: Implementacja** (w `wallet.py`, po `account_path`, oraz metody `Wallet` po
  `next_account_number`):

```python
# order of the accounts of the group, like in Ledger Live
ADDRESS_TYPE_ORDER = (P2TR, P2WPKH, P2SH_P2WPKH, P2PKH)


def group_address_types(coin_symbol: str) -> List[str]:
    """Address types of the coin in the order of the accounts of the group."""
    address_types = get_address_types(get_coin(coin_symbol))
    return [address_type for address_type in ADDRESS_TYPE_ORDER if address_type in address_types]


def group_label(coin_symbol: str, number: int) -> str:
    return f'{get_coin(coin_symbol)["name"].title()} #{number}'


@dataclass
class AccountGroup:
    """Accounts of all address types of the coin with the same number (not saved in the file)."""

    coin: str
    number: int
    label: str
    accounts: List[HDAccount]
```

```python
def account_groups(self) -> List[AccountGroup]:
    grouped: Dict[Tuple[str, int], List[HDAccount]] = {}
    for account in self.accounts:
        grouped.setdefault((account.coin, account.account), []).append(account)
    groups = []
    for (coin_symbol, number), accounts in grouped.items():
        accounts.sort(key=lambda account: ADDRESS_TYPE_ORDER.index(account.address_type))
        labels = {account.label for account in accounts}
        label = labels.pop() if len(labels) == 1 else group_label(coin_symbol, number)
        groups.append(AccountGroup(coin_symbol, number, label, accounts))
    return groups


def get_group(self, coin_symbol: str, number: int) -> AccountGroup:
    for group in self.account_groups():
        if (group.coin, group.number) == (coin_symbol, number):
            return group
    raise KeyError(f'{coin_symbol} #{number}')


def next_group_number(self, coin_symbol: str) -> int:
    numbers = [account.account for account in self.accounts if account.coin == coin_symbol]
    return max(numbers, default=-1) + 1
```

Import `get_address_types` z `multicrypto.coins`.

- [ ] **Step 4:** testy przechodzą. **Step 5:** commit „Add account groups of the wallet”.

### Task 2: Tworzenie, zmiana nazwy i usuwanie grup

**Files:** Modify `multicrypto/wallet.py`, Test `tests/test_wallet.py`

- [ ] **Step 1: Testy**

```python
def test_add_account_group():
    wallet = Wallet.create(MNEMONIC, '')

    group = wallet.add_account_group('Savings', 'BTC')
    doge = wallet.add_account_group('', 'DOGE', 3)

    assert [(a.label, a.address_type, a.account) for a in group.accounts] == [
        ('Savings', 'p2tr', 0),
        ('Savings', 'p2wpkh', 0),
        ('Savings', 'p2sh-p2wpkh', 0),
        ('Savings', 'p2pkh', 0),
    ]
    assert [[address.path for address in wallet.account_addresses(a)] for a in group.accounts] == [
        ["m/86'/0'/0'/0/0"],
        ["m/84'/0'/0'/0/0"],
        ["m/49'/0'/0'/0/0"],
        ["m/44'/0'/0'/0/0"],
    ]
    assert (doge.label, [a.address_type for a in doge.accounts]) == ('Dogecoin #3', ['p2pkh'])
    assert wallet.add_account_group('', 'BTC').number == 1


def test_add_account_group_conflict_changes_nothing():
    wallet = Wallet.create(MNEMONIC, '')
    wallet.add_account('Taproot', 'BTC', 'p2tr', 1)

    with pytest.raises(ValueError, match='already in the wallet'):
        wallet.add_account_group('', 'BTC', 1)
    with pytest.raises(ValueError, match='Account number must be'):
        wallet.add_account_group('', 'BTC', 2**31)

    assert len(wallet.accounts) == 1


def test_add_default_groups():
    wallet = Wallet.create(MNEMONIC, '')

    wallet.add_default_groups()

    assert [(g.coin, g.number, len(g.accounts)) for g in wallet.account_groups()] == [
        (symbol, 0, len(group_address_types(symbol)))
        for symbol, coin in coins.items()
        if 'slip44' in coin
    ]
    assert len(wallet.accounts) == len(wallet.addresses()) == 18


def test_rename_and_remove_group():
    wallet = Wallet.create(MNEMONIC, '')
    wallet.add_account_group('Savings', 'BTC')
    doge = wallet.add_account_group('', 'DOGE')

    wallet.rename_group('BTC', 0, 'Renamed')
    wallet.remove_group('BTC', 0)

    assert wallet.account_groups() == [doge]
    with pytest.raises(KeyError):
        wallet.rename_group('BTC', 0, 'Missing')
```

(W teście zmiany nazwy przed usunięciem sprawdzić też etykiety:
`assert {a.label for a in wallet.get_group('BTC', 0).accounts} == {'Renamed'}`.)

- [ ] **Step 2:** FAIL. **Step 3: Implementacja** (metody `Wallet` po `add_account`):

```python
def add_account_group(
    self, label: str, coin_symbol: str, number: Optional[int] = None
) -> AccountGroup:
    """Add the accounts of all address types of the coin, each with its first address."""
    address_types = group_address_types(coin_symbol)
    if number is None:
        number = self.next_group_number(coin_symbol)
    for existing in self.accounts:
        if (existing.coin, existing.account) == (coin_symbol, number):
            raise ValueError(
                f'Account {number} of {coin_symbol} {existing.address_type} is already in '
                f'the wallet as "{existing.label}"'
            )
    label = label or group_label(coin_symbol, number)
    for address_type in address_types:
        account = self.add_account(label, coin_symbol, address_type, number)
        self.new_address(account.id)
    return self.get_group(coin_symbol, number)


def add_default_groups(self) -> None:
    """Add the first group of every coin with SLIP-44 coin type."""
    for coin_symbol, coin in coins.items():
        if 'slip44' in coin:
            self.add_account_group('', coin_symbol, 0)


def rename_group(self, coin_symbol: str, number: int, label: str) -> None:
    for account in self.get_group(coin_symbol, number).accounts:
        account.label = label


def remove_group(self, coin_symbol: str, number: int) -> None:
    """Remove the accounts of the group (the seed still derives them)."""
    removed = self.get_group(coin_symbol, number).accounts
    self.accounts[:] = [account for account in self.accounts if account not in removed]
```

`add_account` sprawdza SLIP-44 i zakres numeru przed dodaniem pierwszego konta, więc przy tych
błędach nic nie jest dodawane. `account not in removed` porównuje dataclassy — konta mają unikalne
`id`, więc równość oznacza to samo konto.

- [ ] **Step 4:** PASS. **Step 5:** commit „Add creating, renaming and removing account groups”.

### Task 3: Grupy #0 w nowym pliku portfela

**Files:** Modify `multicrypto/wallet.py` (`WalletFile.create`), `tests/test_wallet.py`,
`tests/test_gui.py`

- [ ] **Step 1:** W `test_create_and_unlock`:

```python
def test_create_and_unlock(wallet_file):
    wallet = wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE)
    address = wallet.new_address(wallet.get_group('BTC', 0).accounts[1].id, 'Savings')
    wallet_file.save(wallet)
    wallet_file.lock()

    unlocked = WalletFile(wallet_file.path).unlock(PASSWORD, PASSPHRASE)

    assert unlocked.accounts == wallet.accounts
    assert len(unlocked.accounts) == 18
    assert address in unlocked.addresses()
```

- [ ] **Step 2:** FAIL. **Step 3:** w `WalletFile.create`: docstring „Create wallet file with
  the mnemonic and the first account group of every coin.”, `wallet.add_default_groups()` zamiast
  `wallet.add_account('Bitcoin', 'BTC', P2WPKH)`.
- [ ] **Step 4:** `uv run pytest -q` — naprawić testy GUI zależne od jednego konta BTC
  `p2wpkh` bez adresów. Pomocnik w `tests/test_gui.py`:

```python
def btc_account(window, address_type='p2wpkh'):
    return next(
        account
        for account in window.wallet.get_group('BTC', 0).accounts
        if account.address_type == address_type
    )
```

  i zamiana `window.wallet.accounts[0]` na `btc_account(window)`, liczności (drzewo, źródła Send,
  Balance) liczone z `window.wallet.addresses()`, `accounts[-1]` po skanie zastąpione szukaniem
  konta po monecie, typie i numerze. Testy, które przy skanie dodają `p2tr` #0, uwzględniają
  istniejący adres `0/0` (np. „added 2 addresses”).
- [ ] **Step 5:** PASS całości, commit „Create first account group of every coin in new wallet”.

### Task 4: Skan po grupach

**Files:** Modify `multicrypto/discovery.py`, Test `tests/test_discovery.py`

- [ ] **Step 1: Testy** (zastępują `test_discover_accounts_of_all_address_types`,
  `test_add_discovered`, poprawka `test_discover_keeps_accounts_found_before_error`):

```python
def test_discover_scans_account_groups():
    wallet = Wallet.create(MNEMONIC, '')
    used = used_addresses(
        wallet,
        [
            ('BTC', 'p2tr', 0, RECEIVE_CHAIN, 0),
            ('BTC', 'p2wpkh', 1, RECEIVE_CHAIN, 0),
            ('BTC', 'p2wpkh', 1, RECEIVE_CHAIN, 1),
            ('BTC', 'p2pkh', 3, RECEIVE_CHAIN, 0),  # after the unused group 2, not found
        ],
    )
    checked = []

    found = discover(
        wallet, 'BTC', checked.append, lambda: False, tx_count=lambda address: int(address in used)
    )

    assert found == [
        DiscoveredAccount('BTC', 'p2tr', 0, [0], []),
        DiscoveredAccount('BTC', 'p2wpkh', 1, [0, 1], []),
    ]
    # group 0: p2tr 21 + 20, three unused accounts 3 * 40; group 1: p2wpkh 22 + 20,
    # three unused accounts 3 * 40; group 2: four unused accounts 4 * 40
    assert sum(checked) == 41 + 120 + 42 + 120 + 160


def test_add_discovered():
    wallet = Wallet.create(MNEMONIC, '')
    existing = wallet.add_account('Savings', 'BTC', 'p2wpkh')
    wallet.new_address(existing.id)
    discovered = [
        DiscoveredAccount('BTC', 'p2wpkh', 0, [0, 1], [0]),
        DiscoveredAccount('BTC', 'p2pkh', 0, [], [2]),
        DiscoveredAccount('BTC', 'p2tr', 1, [0], []),
    ]

    # p2wpkh 0/1 and 1/0, p2pkh 1/2, group 1 with the addresses 0/0 of four accounts
    assert add_discovered(wallet, discovered) == 7
    assert add_discovered(wallet, discovered) == 0
    assert [address.path for address in wallet.account_addresses(existing)] == [
        "m/84'/0'/0'/0/0",
        "m/84'/0'/0'/0/1",
        "m/84'/0'/0'/1/0",
    ]
    group = wallet.get_group('BTC', 0)
    assert [(a.label, a.address_type) for a in group.accounts] == [
        ('Savings', 'p2wpkh'),
        ('Savings', 'p2pkh'),
    ]
    assert [address.label for address in wallet.account_addresses(group.accounts[1])] == [
        'Change 2'
    ]
    new_group = wallet.get_group('BTC', 1)
    assert new_group.label == 'Bitcoin #1'
    assert [len(account.addresses) for account in new_group.accounts] == [1, 1, 1, 1]
```

W `test_discover_keeps_accounts_found_before_error` używany adres `('BTC', 'p2wpkh', 0,
RECEIVE_CHAIN, 0)` (skanowany przed `p2sh-p2wpkh`), oczekiwane `found ==
[DiscoveredAccount('BTC', 'p2wpkh', 0, [0], [])]`.

- [ ] **Step 2:** FAIL. **Step 3: Implementacja**

```python
def discover(...):
    """Used accounts of all address types of the coin: the account groups (accounts of all
    address types with the same number) are checked from 0 to the first one without transactions
    on the receiving and change chains of all its accounts. The accounts are appended to the
    found list as soon as they are scanned, so they are available also when the scan fails."""
    _scannable_coin(coin_symbol)
    coin = ...
    found = [] if found is None else found
    with ThreadPoolExecutor(THREADS) as executor:
        for number in range(MAX_ACCOUNTS + 1):
            if number == MAX_ACCOUNTS:
                raise ValueError(f'Stopped after {MAX_ACCOUNTS} accounts of {coin_symbol}')
            used = False
            for address_type in group_address_types(coin_symbol):
                account = HDAccount('', coin_symbol, address_type, number)
                item = _scan_account(wallet, account, progress, cancelled, tx_count, executor.map)
                if item.receive or item.change:
                    found.append(item)
                    used = True
            if not used:
                break
    return found


def add_discovered(wallet: Wallet, discovered: List[DiscoveredAccount]) -> int:
    """Add the discovered accounts and addresses missing in the wallet, return the number of the
    added addresses. The missing account group is added with the accounts of all address types."""
    before = len(wallet.addresses())
    for item in discovered:
        account = _find_account(wallet, item)
        if account is None:
            try:
                label = wallet.get_group(item.coin, item.account).label
            except KeyError:
                wallet.add_account_group('', item.coin, item.account)
            else:
                wallet.add_account(label, item.coin, item.address_type, item.account)
            account = _find_account(wallet, item)
        present = ...  # bez zmian
        for chain, indexes in ...:
            for index in indexes:
                if (chain, index) not in present:
                    wallet.add_address(account.id, chain, index)
    return len(wallet.addresses()) - before
```

`_find_account(wallet, item)` — dotychczasowe `next(...)` po `(coin, address_type, account)`.
Import `group_address_types` z `multicrypto.wallet`, `get_address_types` przestaje być potrzebny.

- [ ] **Step 4:** PASS (`tests/test_discovery.py` i testy GUI skanu). **Step 5:** commit „Scan
  account groups and add discovered accounts as full groups”.

### Task 5: Drzewo grup i akcje w zakładce Wallet

**Files:** Modify `multicrypto/gui/wallet_tab.py`, Test `tests/test_gui.py`

- [ ] **Step 1: Testy**

```python
def test_wallet_tree_shows_account_groups(window):
    unlock(window)
    account = btc_account(window)
    address = window.modify_wallet(lambda wallet: wallet.new_address(account.id))
    first = window.wallet.account_addresses(account)[0]
    window.wallet_tab.balances = {first.id: 1000, address.id: 500}
    window.wallet_tab.refresh()

    group = window.wallet_tab.tree.topLevelItem(0)
    native = group.child(1)

    assert [group.text(i) for i in range(4)] == ['Bitcoin #0', '', 'BTC', '0.00001500']
    assert [native.text(i) for i in range(4)] == ['Native SegWit', "m/84'/0'/0'", '', '0.00001500']
    assert native.child(1).text(2) == address.address
    assert window.wallet_tab.tree.topLevelItemCount() == 6


def test_new_address_needs_address_type(window, monkeypatch):
    unlock(window)
    messages = []
    monkeypatch.setattr(
        wallet_tab_module.QMessageBox, 'information', lambda *args: messages.append(args[2])
    )
    tab = window.wallet_tab
    tab.tree.setCurrentItem(tab.tree.topLevelItem(0))

    tab.new_address()

    assert messages == ['Select an address type first']


def test_rename_and_remove_account_group(window, monkeypatch):
    unlock(window)
    tab = window.wallet_tab
    monkeypatch.setattr(wallet_tab_module.QInputDialog, 'getText', lambda *args: ('Savings', True))
    monkeypatch.setattr(
        wallet_tab_module.QMessageBox, 'question', lambda *args: QMessageBox.StandardButton.Yes
    )
    tab.tree.setCurrentItem(tab.tree.topLevelItem(0))

    tab.rename()
    assert window.wallet.get_group('BTC', 0).label == 'Savings'
    assert tab.tree.currentItem().text(0) == 'Savings'

    tab.remove()
    assert [group.coin for group in window.wallet.account_groups()][0] != 'BTC'


def test_new_account_dialog_creates_group(window):
    unlock(window)
    dialog = wallet_tab_module.NewAccountGroupDialog(
        window.wallet_tab, window.wallet, window.wallet_tab.add_group
    )

    dialog.coin.setCurrentText('DOGE')
    assert dialog.account.value() == 1
    assert dialog.paths.text() == "Legacy: m/44'/3'/1'"
    dialog.coin.setCurrentText('BTC')
    dialog.label.setText('Savings')
    dialog.accept()

    group = window.wallet.get_group('BTC', 1)
    assert (group.label, len(group.accounts)) == ('Savings', 4)


def test_group_menu_scans_coin(window, monkeypatch):
    unlock(window)
    started = []
    monkeypatch.setattr(window.background_scan, 'start_coin', started.append)

    window.wallet_tab._group_actions('LTC')['Scan for used addresses']()

    assert started == ['LTC']
    assert window.wallet_tab._group_actions('DOGE') == {}
```

(`QMessageBox` importowany w teście z `PySide6.QtWidgets`; sprawdzić format kwoty
`format_amount(1500)` i dostosować oczekiwany tekst.)

- [ ] **Step 2:** FAIL. **Step 3: Implementacja** w `wallet_tab.py`:
  - `ACCOUNT_GROUP = 'account_group'`, `ADDRESS_TYPE_NAMES = {P2TR: 'Taproot', P2WPKH: 'Native
    SegWit', P2SH_P2WPKH: 'SegWit', P2PKH: 'Legacy'}`, `group_id(coin, number) ->
    f'{coin}/{number}'`, `parse_group_id(item_id) -> (coin, int(number))`.
  - `NewAccountGroupDialog(QDialog)` — pola Label, Coin (`coins_with_slip44()`, BTC), Account
    number (`QSpinBox` 0…HARDENED-1, `next_group_number` po zmianie monety), Paths (`QLabel`,
    linie `<nazwa typu>: <account_path>` dla `group_address_types`); `accept()` wywołuje
    `submit(label, coin, number)`, błędy `EXPECTED_ERRORS` → `QMessageBox.warning`, okno zostaje.
    `NewAccountDialog` usunięty.
  - `refresh()` — dla `wallet.account_groups()` element grupy `[label, '', coin, suma]`, podkonta
    `[ADDRESS_TYPE_NAMES[type], account.path, '', suma]`, adresy jak dziś; `_sum_text(addresses)`
    sumuje salda `int` (pusty tekst, gdy żadnego). Kolumna 3 wyrównana do prawej.
  - `_items()` rekurencyjnie od `invisibleRootItem()`.
  - `_selected_account_id()` bez skrótu „jedyne konto”; `new_address()` dla grupy → „Select an
    address type first”.
  - `new_account()` → `NewAccountGroupDialog(self, wallet, self.add_group)`; `add_group(label,
    coin, number)` → `modify_wallet(add_account_group)` i zaznaczenie grupy.
  - `rename()` — grupa → `rename_group`, konto → „Rename the account group”.
  - `remove()` — grupa → ostrzeżenie grupy i `remove_group`.
  - `_group_actions(coin)` → `{'Scan for used addresses': start_coin}` dla monet z `apis`;
    `_show_menu` dla grupy pokazuje te akcje (bez menu, gdy puste).
- [ ] **Step 4:** PASS. **Step 5:** commit „Show account groups in the wallet tab”.

### Task 6: Bez skanu po odtworzeniu

**Files:** Modify `multicrypto/gui/window.py`, Test `tests/test_gui.py`

- [ ] **Step 1:** test zastępujący `test_restored_wallet_is_scanned_in_background`:

```python
def test_restored_wallet_is_not_scanned(window, monkeypatch):
    started, messages = [], []
    monkeypatch.setattr(window.background_scan, 'start_coin', started.append)
    monkeypatch.setattr(
        'multicrypto.gui.window.QMessageBox.information', lambda *args: messages.append(args[2])
    )

    window._created(window.wallet_file.create(PASSWORD, MNEMONIC, PASSPHRASE), restored=True)

    assert started == []
    assert 'right-click a coin and choose Scan for used addresses' in messages[0]
```

- [ ] **Step 2:** FAIL. **Step 3:** `_created` — bez `start_coin`, dla `restored` dopisek „To find
  used accounts and addresses, right-click a coin and choose Scan for used addresses (or File →
  Scan for used addresses).”
- [ ] **Step 4:** PASS. **Step 5:** commit „Scan restored wallet only on demand”.

### Task 7: README

- [ ] Sekcja GUI: opis grup („coin #N” z podkontami typów, grupy #0 w nowym portfelu), skan z
  menu monety zamiast skanu BTC po odtworzeniu, ręczne odtwarzanie grup za pustą grupą i adresów
  za gap limitem. Commit „Describe account groups in README”.

### Weryfikacja końcowa

- [ ] `uv run pytest -q` — wszystkie testy przechodzą.
- [ ] `uv run ruff check multicrypto tests` i `uv run ruff format --check multicrypto tests`
  (jeśli projekt używa ruff — sprawdzić `pyproject.toml`).
