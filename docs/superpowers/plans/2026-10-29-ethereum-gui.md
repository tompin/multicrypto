# Ethereum w GUI — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ETH i TETH w GUI: portfel HD zgodny z MetaMask, salda, wysyłka, skanowanie użytych
adresów, podpisy EIP-191, vanity i tłumaczenie kluczy.

**Architecture:** `ethereum_coins` zostaje osobno, cienka warstwa helperów (`coins.py`,
`gui/forms.py`) i rozgałęzienia w zakładkach na `is_ethereum(symbol)`. W portfelu pseudo-typ
adresu `ethereum` (purpose 44, tylko łańcuch 0), importowany klucz ETH trzymany jako hex w polu
`ImportedKey.wif` bez zmiany formatu pliku.

**Tech Stack:** Python 3.10+, PySide6, pytest (`uv run python -m pytest`), ruff.

Specyfikacja: `docs/superpowers/specs/2026-10-29-ethereum-gui-design.md`. Branch: `ethereum-gui`.

Po każdej fazie: `uv run python -m pytest -q`, `uv run ruff check .`,
`uv run ruff format --check .` muszą przechodzić, potem commit.

---

## Pliki

- `multicrypto/coins.py` — `ETHEREUM`, `get_any_coin`, `is_ethereum`, `get_address_types`.
- `multicrypto/wallet.py` — konta i klucze ETH, `private_key`, `exported_private_key`,
  `add_ethereum_key`, domyślne grupy.
- `multicrypto/ethereum_api.py` — `max_value`, `BlockscoutAPI.get_usage`.
- `multicrypto/discovery.py` — skan ETH (tylko łańcuch 0, Blockscout).
- `multicrypto/gui/forms.py` — listy monet, formatowanie kwot, salda, parsowanie pól ETH, opis
  transakcji, helpery kluczy.
- `multicrypto/gui/dialogs.py` — czerwone wiersze `Warning` w `ConfirmDialog`.
- `multicrypto/gui/wallet_tab.py`, `balance_tab.py`, `send_tab.py`, `scan_dialog.py`,
  `sign_tab.py`, `vanity_tab.py`, `translate_tab.py` — zakładki.
- `README.md` — opis GUI.
- Testy: `tests/test_coins.py`, `tests/test_wallet.py`, `tests/test_ethereum_api.py`,
  `tests/test_discovery.py`, `tests/test_gui_forms.py`, `tests/test_gui.py`.

---

# Faza 1: model danych, helpery, zakładka Wallet

### Task 1: Helpery monet

**Files:** Modify `multicrypto/coins.py`, Test `tests/test_coins.py`

- [ ] **Step 1: Testy** (dopisz na końcu `tests/test_coins.py`, a do importów na górze dodaj
  `import pytest` jeśli go nie ma oraz
  `from multicrypto.coins import ETHEREUM, coins, ethereum_coins, get_address_types, get_any_coin, is_ethereum`)

```python
def test_get_any_coin():
    assert get_any_coin('BTC') is coins['BTC']
    assert get_any_coin('TETH') is ethereum_coins['TETH']
    with pytest.raises(ValueError, match='Unknown coin XYZ'):
        get_any_coin('XYZ')


def test_is_ethereum():
    assert is_ethereum('ETH') and is_ethereum('TETH')
    assert not is_ethereum('BTC')


def test_address_types_of_ethereum_coins():
    assert get_address_types(ethereum_coins['ETH']) == (ETHEREUM,)
    assert get_address_types(coins['DOGE']) == ('p2pkh',)
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_coins.py -q` — FAIL (ImportError).

- [ ] **Step 3: Implementacja** w `multicrypto/coins.py`: pod `ADDRESS_TYPES` dodaj

```python
# Pseudo address type of Ethereum coins, they have one kind of addresses (not in ADDRESS_TYPES,
# which lists the address types of the coins with unspent outputs)
ETHEREUM = 'ethereum'
```

a `get_address_types` zastąp i dodaj helpery na końcu pliku:

```python
def get_address_types(coin):
    if 'chain_id' in coin:
        return (ETHEREUM,)
    return coin.get('address_types', (P2PKH,))


def get_any_coin(coin_symbol):
    """Definition of the coin with unspent outputs or of the Ethereum coin."""
    if coin_symbol in coins:
        return coins[coin_symbol]
    if coin_symbol in ethereum_coins:
        return ethereum_coins[coin_symbol]
    raise ValueError(f'Unknown coin {coin_symbol}')


def is_ethereum(coin_symbol):
    return coin_symbol in ethereum_coins
```

(`get_coins_with_api` zostaje pod `get_address_types`.)

- [ ] **Step 4:** `uv run python -m pytest tests/test_coins.py -q` — PASS.

### Task 2: Konta i klucze ETH w portfelu

**Files:** Modify `multicrypto/wallet.py`, Test `tests/test_wallet.py`

- [ ] **Step 1: Testy** — do importów `tests/test_wallet.py` dodaj
  `from multicrypto.coins import coins, ethereum_coins` (zamiast samego `coins`),
  `from multicrypto.ethereum import private_key_to_address` i
  `from multicrypto.bip32 import master_key_from_seed`,
  `from multicrypto.bip39 import mnemonic_to_seed`; dopisz:

```python
ETH_KEY = '46' * 32
ETH_KEY_ADDRESS = '0x9d8A62f656a8d1615C1294fd71e9CFb3E4855A4F'
METAMASK_ADDRESS = '0x9858EfFD232B4033E47d90003D41EC34EcaEda94'  # m/44'/60'/0'/0/0 of MNEMONIC


@pytest.mark.parametrize('coin_symbol', ['ETH', 'TETH'])
def test_ethereum_group_has_metamask_addresses(coin_symbol):
    wallet = Wallet.create(MNEMONIC, '')

    group = wallet.add_account_group('', coin_symbol)

    [account] = group.accounts
    assert (account.address_type, account.path) == ('ethereum', "m/44'/60'/0'")
    second = wallet.new_address(account.id)
    first, second = wallet.account_addresses(account)
    assert (first.path, first.address) == ("m/44'/60'/0'/0/0", METAMASK_ADDRESS)
    root = master_key_from_seed(mnemonic_to_seed(MNEMONIC))
    expected = private_key_to_address(root.derive_path("m/44'/60'/0'/0/1").private_key)
    assert (second.path, second.address) == ("m/44'/60'/0'/0/1", expected)
    assert group.label == ('Ethereum #0' if coin_symbol == 'ETH' else 'Ethereum Sepolia Testnet #0')


def test_private_key_of_ethereum_address():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account_group('', 'ETH').accounts[0]
    [address] = wallet.account_addresses(account)

    private_key = wallet.private_key(address)

    assert private_key_to_address(private_key) == METAMASK_ADDRESS
    assert wallet.exported_private_key(address) == f'0x{private_key:064x}'
    with pytest.raises(ValueError, match='not in WIF format'):
        wallet.private_key_wif(address)


def test_add_ethereum_key():
    wallet = Wallet.create(MNEMONIC, '')

    address = wallet.add_ethereum_key('Key', 'ETH', ETH_KEY)

    assert (address.coin, address.address_type, address.address) == (
        'ETH',
        'ethereum',
        ETH_KEY_ADDRESS,
    )
    assert wallet.imported[0].wif == '0x' + ETH_KEY
    assert wallet.private_key(address) == int(ETH_KEY, 16)
    assert wallet.exported_private_key(address) == '0x' + ETH_KEY
    with pytest.raises(ValueError, match='already in the wallet as "Key"'):
        wallet.add_ethereum_key('Again', 'ETH', '0X' + ETH_KEY.upper())
    assert wallet.add_ethereum_key('Testnet', 'TETH', ETH_KEY).address == ETH_KEY_ADDRESS


@pytest.mark.parametrize(
    'coin_symbol, key, message',
    [
        ('BTC', ETH_KEY, 'BTC is not an Ethereum coin'),
        ('ETH', '1234', '64 hexadecimal digits'),
    ],
)
def test_add_ethereum_key_rejects_incorrect_keys(coin_symbol, key, message):
    with pytest.raises(ValueError, match=message):
        Wallet.create(MNEMONIC, '').add_ethereum_key('Key', coin_symbol, key)


def test_add_wif_rejects_ethereum_coin():
    with pytest.raises(ValueError, match='imported in hex format'):
        Wallet.create(MNEMONIC, '').add_wif('Key', 'ETH', BTC_WIF, 'ethereum')


def test_private_key_of_imported_wif():
    wallet = Wallet.create(MNEMONIC, '')

    address = wallet.add_wif('Key', 'BTC', BTC_WIF, 'p2wpkh')

    assert wallet.private_key(address) == get_private_key_from_wif_format(BTC_WIF)[0]
    assert wallet.exported_private_key(address) == BTC_WIF


def test_ethereum_accounts_and_keys_are_saved():
    wallet = Wallet.create(MNEMONIC, '')
    wallet.add_account_group('', 'ETH')
    wallet.add_ethereum_key('Key', 'TETH', ETH_KEY)

    restored = Wallet.from_json(wallet.to_json())
    restored.open('')

    assert [address.address for address in restored.addresses()] == [
        METAMASK_ADDRESS,
        ETH_KEY_ADDRESS,
    ]
```

Do importów dodaj też `from multicrypto.address import convert_private_key_to_wif_format, get_private_key_from_wif_format`
(pierwszy już jest). Zmień `test_add_default_groups`:

```python
def test_add_default_groups():
    wallet = Wallet.create(MNEMONIC, '')

    wallet.add_default_groups()

    expected_coins = {**coins, **ethereum_coins}
    assert [(g.coin, g.number, len(g.accounts)) for g in wallet.account_groups()] == [
        (symbol, 0, len(group_address_types(symbol)))
        for symbol, coin in expected_coins.items()
        if 'slip44' in coin
    ]
    assert len(wallet.accounts) == len(wallet.addresses()) == 20
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_wallet.py -q` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/wallet.py`:

Importy:

```python
from multicrypto import ethereum
from multicrypto.coins import (
    ETHEREUM,
    P2PKH,
    P2SH_P2WPKH,
    P2TR,
    P2WPKH,
    coins,
    ethereum_coins,
    get_address_types,
    get_any_coin,
    is_ethereum,
)
```

Stałe:

```python
PURPOSES = {P2PKH: 44, P2SH_P2WPKH: 49, P2WPKH: 84, P2TR: 86, ETHEREUM: 44}
# order of the accounts of the group, like in Ledger Live (Ethereum groups have one account)
ADDRESS_TYPE_ORDER = (P2TR, P2WPKH, P2SH_P2WPKH, P2PKH, ETHEREUM)
```

`get_coin`:

```python
def get_coin(coin_symbol: str) -> Dict[str, Any]:
    return get_any_coin(coin_symbol)
```

`check_entry` — pierwsze linie:

```python
def check_entry(coin_symbol: str, wif_private_key: str, address_type: str) -> str:
    """Validate imported private key data and return its address."""
    coin = get_coin(coin_symbol)
    if is_ethereum(coin_symbol):
        raise ValueError('Ethereum private keys are imported in hex format')
    validate_address_type(address_type, coin)
```

`ImportedKey` — docstring i `address`:

```python
@dataclass
class ImportedKey:
    """Private key which is not derived from the mnemonic, in the export format of the coin:
    WIF, or hex (0x and 64 digits) for Ethereum coins (the field keeps its name in the file)."""

    ...

    @cached_property
    def address(self) -> str:
        if self.address_type == ETHEREUM:
            return ethereum.private_key_to_address(ethereum.parse_private_key(self.wif))
        private_key, compressed = get_private_key_from_wif_format(self.wif)
        return convert_private_key_to_coin_address(
            private_key, coins[self.coin], compressed, self.address_type
        )
```

`Wallet.address_at`:

```python
    def address_at(self, account: HDAccount, chain: int, index: int) -> str:
        """Address of the account chain, it is not added to the wallet."""
        cache_key = (account.coin, account.path, chain, index)
        if cache_key not in self._addresses:
            private_key = self._derive(account, chain, index).private_key
            if account.address_type == ETHEREUM:
                address = ethereum.private_key_to_address(private_key)
            else:
                address = convert_private_key_to_coin_address(
                    private_key, coins[account.coin], True, account.address_type
                )
            self._addresses[cache_key] = address
        return self._addresses[cache_key]
```

`add_default_groups`:

```python
    def add_default_groups(self) -> None:
        """Add the first account group of every coin with SLIP-44 coin type."""
        for coin_symbol, coin in {**coins, **ethereum_coins}.items():
            if 'slip44' in coin:
                self.add_account_group('', coin_symbol, 0)
```

Po `add_wif` dodaj:

```python
def add_ethereum_key(self, label: str, coin_symbol: str, private_key_hex: str) -> WalletAddress:
    """Import Ethereum private key in hex format, raise ValueError when it is incorrect or
    present."""
    if not is_ethereum(coin_symbol):
        raise ValueError(f'{coin_symbol} is not an Ethereum coin')
    key_hex = ethereum.format_private_key(ethereum.parse_private_key(private_key_hex))
    for key in self.imported:
        if (key.coin, key.wif) == (coin_symbol, key_hex):
            raise ValueError(f'Address {key.address} is already in the wallet as "{key.label}"')
    key = ImportedKey(label, coin_symbol, key_hex, ETHEREUM)
    self.imported.append(key)
    return self._imported_address(key)
```

`private_key_wif` i nowe metody (zastąp `private_key_wif`):

```python
def private_key(self, address: WalletAddress) -> int:
    if address.account_id is None:
        key = self._locate(address.id)[0]
        if key.address_type == ETHEREUM:
            return ethereum.parse_private_key(key.wif)
        return get_private_key_from_wif_format(key.wif)[0]
    account = self.get_account(address.account_id)
    return self._derive(account, address.chain, address.index).private_key


def private_key_wif(self, address: WalletAddress) -> str:
    if address.address_type == ETHEREUM:
        raise ValueError('Ethereum private keys are not in WIF format')
    if address.account_id is None:
        return self._locate(address.id)[0].wif
    account = self.get_account(address.account_id)
    return generate_wif(
        account.coin, self._derive(account, address.chain, address.index).private_key
    )


def exported_private_key(self, address: WalletAddress) -> str:
    """Private key in WIF format, or in hex format for Ethereum."""
    if address.address_type == ETHEREUM:
        return ethereum.format_private_key(self.private_key(address))
    return self.private_key_wif(address)
```

- [ ] **Step 4:** `uv run python -m pytest tests/test_wallet.py tests/test_coins.py -q` — PASS.

### Task 3: Helpery formularzy

**Files:** Modify `multicrypto/gui/forms.py`, `multicrypto/gui/scan_dialog.py`,
Test `tests/test_gui_forms.py`

- [ ] **Step 1: Testy** — do importów `tests/test_gui_forms.py` dodaj z `multicrypto.gui.forms`:
  `add_private_key, address_type_name, all_coins, all_coins_with_api, coins_with_slip44,
  format_coin_amount, is_testnet, key_entry_address, scannable_coins`
  (część może już być) oraz `from multicrypto.wallet import Wallet`; dopisz:

```python
ETH_KEY = '46' * 32
ETH_KEY_ADDRESS = '0x9d8A62f656a8d1615C1294fd71e9CFb3E4855A4F'
ETH_NODE = 'https://ethereum-rpc.publicnode.com'


def test_coin_lists_with_ethereum():
    assert all_coins() == sorted([*coins, 'ETH', 'TETH'])
    assert {'ETH', 'TETH'} <= set(all_coins_with_api())
    assert {'ETH', 'TETH'} <= set(coins_with_slip44())
    assert 'ETH' not in coins_with_api()  # coins with unspent outputs, e.g. for Sweep
    assert 'ETH' not in scannable_coins()  # until discovery supports Ethereum (phase 3)
    assert is_testnet('TETH') and not is_testnet('ETH')


def test_format_coin_amount():
    assert format_coin_amount('BTC', 150000000) == '1.50000000'
    assert format_coin_amount('ETH', 10**18 + 5) == '1.000000000000000005'
    assert format_coin_amount('TETH', 0) == '0'


def test_address_type_name_of_ethereum():
    assert address_type_name('ethereum') == 'Ethereum'
    assert address_type_name('p2wpkh') == 'Native SegWit (p2wpkh)'


def test_key_entry_address():
    assert key_entry_address('ETH', '0x' + ETH_KEY, 'ethereum') == ETH_KEY_ADDRESS
    with pytest.raises(ValueError, match='64 hexadecimal digits'):
        key_entry_address('ETH', 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn', 'ethereum')


def test_add_private_key():
    wallet = Wallet.create(' '.join(['abandon'] * 11 + ['about']), '')

    eth = add_private_key(wallet, 'Eth', 'ETH', ETH_KEY, 'ethereum')
    btc = add_private_key(
        wallet, 'Btc', 'BTC', 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn', 'p2pkh'
    )

    assert eth.address == ETH_KEY_ADDRESS
    assert btc.address == '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'


@http_mock.activate
def test_fetch_balances_of_ethereum_addresses():
    http_mock.add(http_mock.POST, ETH_NODE, json={'jsonrpc': '2.0', 'id': 1, 'result': hex(10**18)})

    balances = fetch_balances(
        [make_address('e', coin='ETH', address_type='ethereum', address=ETH_KEY_ADDRESS)]
    )

    assert balances == {'e': 10**18}
```

(`make_address` już jest w pliku — sprawdź jego sygnaturę `make_address(id, coin=..., address_type=..., address=...)`
i dopasuj argumenty.)

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui_forms.py -q` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/gui/forms.py`:

Importy:

```python
from multicrypto import ethereum
from multicrypto.coins import (
    ETHEREUM,
    P2PKH,
    P2SH_P2WPKH,
    P2TR,
    P2WPKH,
    coins,
    ethereum_coins,
    get_address_types,
    get_any_coin,
    is_ethereum,
)
from multicrypto.ethereum_api import get_rpc
```

Zamień `is_testnet`, `coins_with_api`, `ADDRESS_TYPE_NAMES`, `address_type_name`,
`coins_with_slip44` i dodaj nowe funkcje:

```python
def is_testnet(coin_symbol: str) -> bool:
    return 'testnet' in get_any_coin(coin_symbol)['name']


def all_coins() -> List[str]:
    return sorted([*coins, *ethereum_coins])


def coins_with_api() -> List[str]:
    """Coins with unspent outputs and block explorer API."""
    return sorted(symbol for symbol, coin in coins.items() if coin.get('apis'))


def all_coins_with_api() -> List[str]:
    """Coins with API, Ethereum coins use nodes and block explorers."""
    ethereum_symbols = [symbol for symbol, coin in ethereum_coins.items() if coin.get('rpcs')]
    return sorted(coins_with_api() + ethereum_symbols)


ADDRESS_TYPE_NAMES = {
    P2TR: 'Taproot',
    P2WPKH: 'Native SegWit',
    P2SH_P2WPKH: 'SegWit',
    P2PKH: 'Legacy',
    ETHEREUM: 'Ethereum',
}


def address_type_name(address_type: str) -> str:
    if address_type == ETHEREUM:
        return ADDRESS_TYPE_NAMES[ETHEREUM]
    return f'{ADDRESS_TYPE_NAMES[address_type]} ({address_type})'


def coins_with_slip44() -> List[str]:
    return sorted(
        symbol for symbol, coin in {**coins, **ethereum_coins}.items() if 'slip44' in coin
    )


def scannable_coins() -> List[str]:
    """Coins whose HD accounts can be scanned for used addresses."""
    return sorted(set(coins_with_slip44()) & set(coins_with_api()))


def format_coin_amount(coin_symbol: str, units: int) -> str:
    """Amount in satoshis, or in wei for Ethereum coins, in coin units."""
    if is_ethereum(coin_symbol):
        return ethereum.format_ether(units)
    return format_amount(units)


def key_entry_address(coin_symbol: str, key: str, address_type: str) -> str:
    """Address of the private key entered for the coin: hex for Ethereum, WIF for other coins."""
    if is_ethereum(coin_symbol):
        return ethereum.private_key_to_address(ethereum.parse_private_key(key))
    return check_entry(coin_symbol, key, address_type)


def add_private_key(
    wallet: Wallet, label: str, coin_symbol: str, key: str, address_type: str
) -> WalletAddress:
    if is_ethereum(coin_symbol):
        return wallet.add_ethereum_key(label, coin_symbol, key)
    return wallet.add_wif(label, coin_symbol, key, address_type)
```

`parse_address` — na początku po sprawdzeniu pustego tekstu:

```python
    if is_ethereum(coin_symbol):
        return ethereum.validate_address(address)
```

`fetch_balances`:

```python
def fetch_balances(addresses: List[WalletAddress]) -> Dict[str, Union[int, str]]:
    """Return the sum of unspent outputs, or the balance in wei of Ethereum addresses (or
    the error message) for the address ids."""
    balances: Dict[str, Union[int, str]] = {}
    rpcs = {}
    for address in addresses:
        if is_ethereum(address.coin):
            if address.coin not in rpcs:
                rpcs[address.coin] = get_rpc(ethereum_coins[address.coin])
            try:
                balances[address.id] = rpcs[address.coin].get_balance(address.address)
            except EXPECTED_ERRORS as error:
                balances[address.id] = f'error: {error}'
            continue
        coin = coins[address.coin]
        ...  # dalej bez zmian
```

W `multicrypto/gui/scan_dialog.py` usuń lokalne `scannable_coins` i importuj je z forms:

```python
from multicrypto.gui.forms import EXPECTED_ERRORS, describe_error, scannable_coins
```

(`coins_with_api`, `coins_with_slip44` i `List` usuń z importów, jeśli nie są już używane.)

- [ ] **Step 4:** `uv run python -m pytest tests/test_gui_forms.py tests/test_gui.py -q -k "scan or forms or fetch"` — PASS.

### Task 4: Zakładka Wallet

**Files:** Modify `multicrypto/gui/wallet_tab.py`, Test `tests/test_gui.py`

- [ ] **Step 1: Testy** — dopisz w `tests/test_gui.py` (import
  `from multicrypto.ethereum import parse_private_key, private_key_to_address` na górze, obok
  innych importów `multicrypto`):

```python
ETH_KEY = '46' * 32
ETH_KEY_ADDRESS = '0x9d8A62f656a8d1615C1294fd71e9CFb3E4855A4F'


def ethereum_address(window, coin_symbol='ETH'):
    [account] = window.wallet.get_group(coin_symbol, 0).accounts
    return window.wallet.account_addresses(account)[0]


def tree_item(tab, kind, item_id):
    return next(
        item
        for item in tab._items()
        if tuple(item.data(0, wallet_tab_module.ITEM_ROLE)) == (kind, item_id)
    )


def test_wallet_tree_shows_ethereum_group_and_balances(window):
    unlock(window)
    tab = window.wallet_tab
    address = ethereum_address(window)
    tab.balances = {address.id: 10**18 + 5}

    tab.refresh()

    group = tree_item(tab, wallet_tab_module.ACCOUNT_GROUP, 'ETH/0')
    assert [group.text(column) for column in range(4)] == [
        'Ethereum #0',
        '',
        'ETH',
        '1.000000000000000005',
    ]
    account = group.child(0)
    assert (account.text(0), account.text(1)) == ('Ethereum', "m/44'/60'/0'")
    item = tree_item(tab, wallet_tab_module.ADDRESS, address.id)
    assert (item.text(1), item.text(2), item.text(3)) == (
        '0/0',
        address.address,
        '1.000000000000000005',
    )
    assert private_key_to_address(window.wallet.private_key(address)) == address.address


def test_import_ethereum_key(window, monkeypatch):
    unlock(window)

    def fill(dialog):
        dialog.label.setText('Imported')
        dialog.coin.setCurrentText('ETH')
        dialog.wif.setText('0x' + ETH_KEY)
        assert dialog.address.text() == ETH_KEY_ADDRESS
        assert not dialog.form.isRowVisible(dialog.address_type)
        assert dialog.form.labelForField(dialog.wif).text() == 'Private key (hex)'
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.ImportWifDialog, 'exec', fill)
    window.wallet_tab.import_wif()

    [imported] = window.wallet.imported_addresses()
    assert (imported.coin, imported.address_type, imported.address) == (
        'ETH',
        'ethereum',
        ETH_KEY_ADDRESS,
    )


def test_import_dialog_shows_address_type_of_bitcoin(window):
    unlock(window)
    dialog = wallet_tab_module.ImportWifDialog(
        window.wallet_tab, lambda *args: None, ['BTC', 'ETH']
    )

    dialog.coin.setCurrentText('ETH')
    dialog.coin.setCurrentText('BTC')

    assert dialog.form.isRowVisible(dialog.address_type)
    assert dialog.form.labelForField(dialog.wif).text() == 'Private key (WIF)'


def test_show_key_of_ethereum_address(window, monkeypatch):
    unlock(window)
    address = ethereum_address(window)
    shown = []
    monkeypatch.setattr(wallet_tab_module, 'secret_line', lambda secret: secret)
    monkeypatch.setattr(
        wallet_tab_module,
        'SecretDialog',
        lambda parent, title, text, secret: shown.append((title, secret)) or Mock(),
    )

    window.wallet_tab._show_key(address, True)

    [(title, secret)] = shown
    assert title == 'Private key (hex) of "Address 0"'
    assert parse_private_key(secret) == window.wallet.private_key(address)
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui.py -q -k "ethereum"` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/gui/wallet_tab.py`:

Importy z coins i forms:

```python
from multicrypto.coins import P2TR, P2WPKH, coins, get_address_types, get_any_coin, is_ethereum
from multicrypto.gui.forms import (
    ADDRESS_TYPE_NAMES,
    EXPECTED_ERRORS,
    add_private_key,
    address_type_name,
    all_coins,
    coins_with_slip44,
    fetch_balances,
    format_coin_amount,
    key_entry_address,
    scannable_coins,
)
```

(`format_amount` i `check_entry` z `multicrypto.wallet` usuń z importów — po zmianach nie są
używane; `coins` zostaje dla `TranslateKeyDialog` do Task 16.)

`_CoinTypeForm.__init__`: `self.coin.setCurrentText('BTC')` zostaje. `_coin_changed`:

```python
    def _coin_changed(self):
        current = self.address_type.currentText()
        coin_symbol = self.coin.currentText()
        address_types = get_address_types(get_any_coin(coin_symbol))
        self.address_type.blockSignals(True)
        self.address_type.clear()
        self.address_type.addItems(address_types)
        if current in address_types:
            self.address_type.setCurrentText(current)
        self.address_type.blockSignals(False)
        # Ethereum coins have one address type
        self.form.setRowVisible(self.address_type, not is_ethereum(coin_symbol))
        self.update_preview()
```

`ImportWifDialog`:

```python
class ImportWifDialog(_CoinTypeForm):
    def __init__(self, parent, submit, symbols: Optional[List[str]] = None):
        super().__init__(parent, 'Import private key', symbols or all_coins(), submit)
        self.wif = password_field()
        self.address = QLabel()
        self.form.addRow('Private key (WIF)', self.wif)
        self.form.addRow('Address', self.address)
        self.wif.textChanged.connect(self.update_preview)
        self.add_buttons()

    def update_preview(self):
        coin_symbol = self.coin.currentText()
        key_format = 'hex' if is_ethereum(coin_symbol) else 'WIF'
        self.form.labelForField(self.wif).setText(f'Private key ({key_format})')
        key = self.wif.text().strip()
        if not key:
            self.address.setText('')
            return
        try:
            address = key_entry_address(coin_symbol, key, self.address_type.currentText())
        except ValueError as error:
            self.address.setText(f'({error})')
        else:
            self.address.setText(address)
```

(`submitted_values` bez zmian.)

`WalletTab`:

```python
    def _visible_groups(self) -> List[AccountGroup]:
        visible = set(self.app.visible_coins(all_coins()))
        return [group for group in self.app.wallet.account_groups() if group.coin in visible]
```

W `refresh`: `visible = set(self.app.visible_coins(all_coins()))`; `_add_address_item` i salda:

```python
def _add_address_item(self, parent: QTreeWidgetItem, address: WalletAddress, path: str):
    item = QTreeWidgetItem(
        parent, [address.label, path, address.address, self._balance_text(address)]
    )
    item.setData(0, ITEM_ROLE, (ADDRESS, address.id))
    self._align_balance(item)


def _balance_text(self, address: WalletAddress) -> str:
    balance = self.balances.get(address.id)
    if balance is None:
        return ''
    return format_coin_amount(address.coin, balance) if isinstance(balance, int) else balance


def _sum_text(self, addresses: List[WalletAddress]) -> str:
    """Sum of the known balances of the addresses of one coin (balances not fetched are
    skipped)."""
    balances = [self.balances.get(address.id) for address in addresses]
    known = [balance for balance in balances if isinstance(balance, int)]
    return format_coin_amount(addresses[0].coin, sum(known)) if known else ''
```

`import_wif`:

```python
    def import_wif(self):
        def submit(label, coin, key, address_type):
            self.app.modify_wallet(
                lambda wallet: add_private_key(wallet, label, coin, key, address_type)
            )

        ImportWifDialog(self, submit, self.app.visible_coins(all_coins())).exec()
```

`_show_key` — wywołanie dialogu:

```python
        key_format = ' (hex)' if is_ethereum(address.coin) else ''
        SecretDialog(
            self,
            f'Private key{key_format} of "{address.label}"',
            f'{address.coin} {address.address_type} {address.address}',
            secret_line(self.app.wallet.exported_private_key(address)),
        ).exec()
```

Akcje menu (ETH nie ma jeszcze skanowania, sprawdzania salda, wysyłki, podpisów ani
tłumaczenia — dochodzą w kolejnych fazach):

```python
def _account_actions(self, account) -> Dict[str, Callable[[], None]]:
    actions = {'New address...': self.new_address}
    if account.coin in scannable_coins():
        actions['Scan for used addresses'] = lambda: self.app.background_scan.start_account(account)
    return actions


def _group_actions(self, coin_symbol: str) -> Dict[str, Callable[[], None]]:
    if coin_symbol not in scannable_coins():
        return {}
    return {'Scan for used addresses': lambda: self.app.background_scan.start_coin(coin_symbol)}
```

W `_show_menu` część adresu:

```python
self.tree.setCurrentItem(item)
address = self.app.wallet.get_address(item_id)
menu = QMenu(self)
menu.addAction('Copy address', self.copy_address)
menu.addAction('Show QR...', self.show_qr)
if not is_ethereum(address.coin):
    menu.addAction('Check UTXO', lambda: self.app.balance_tab.check_address(address))
    menu.addAction('Send from this address', lambda: self.app.send_tab.select_source(address))
    if get_any_coin(address.coin).get('apis'):
        menu.addAction('Sweep this address', lambda: self.app.sweep_tab.select_source(address))
    sign_action = menu.addAction('Sign message', lambda: self.app.sign_tab.select_address(address))
    sign_action.setEnabled(address.address_type != P2TR)
    menu.addAction('Translate to another coin...', lambda: self.translate_key(address))
menu.addAction('Rename...', self.rename)
menu.addAction('Show key...', self.show_key)
menu.exec(self.tree.viewport().mapToGlobal(position))
```

`TranslateKeyDialog` i `WalletTab.translate_key` zostają bez zmian do Task 16 (dalej używają
`coins` i `translate_private_key`, więc te importy zostają w fazie 1).

- [ ] **Step 4:** `uv run python -m pytest tests/test_gui.py -q -k "ethereum or import"` — PASS.

### Task 5: Pełny przebieg testów i commit fazy 1

- [ ] **Step 1:** `uv run python -m pytest -q`. Testy, które liczą domyślne grupy, wiersze
  drzewa albo adresy portfela, mogą teraz widzieć dodatkowe grupy ETH i TETH. Znajdź je:
  `grep -n "account_groups()\|topLevelItemCount\|len(window.wallet\|addresses())" tests/test_gui.py`
  i zaktualizuj oczekiwane wartości o grupy `Ethereum #0` (ETH) i `Ethereum Sepolia Testnet #0`
  (TETH). Nie zmieniaj logiki testów UTXO.
- [ ] **Step 2:** `uv run ruff check . && uv run ruff format --check .` — PASS
  (w razie potrzeby `uv run ruff format .`).
- [ ] **Step 3: Commit**

```bash
git add multicrypto/coins.py multicrypto/wallet.py multicrypto/gui/forms.py multicrypto/gui/scan_dialog.py multicrypto/gui/wallet_tab.py tests/
git commit -m "Add Ethereum accounts, imported keys and balances to the wallet"
```

---

# Faza 2: Balance i Send

### Task 6: `max_value` i wspólne liczenie opłat

**Files:** Modify `multicrypto/ethereum_api.py`, Test `tests/test_ethereum_api.py`

- [ ] **Step 1: Testy** (do importów dodaj `MaxValue, max_value`):

```python
def test_max_value_with_suggested_fees():
    result = max_value(FakeRPC(), ADDRESS, DESTINATION.lower())

    assert result == MaxValue(10**18 - 21000 * 22 * GWEI, 2 * GWEI, 22 * GWEI)


def test_max_value_with_given_fees():
    result = max_value(FakeRPC(), ADDRESS, DESTINATION, GWEI, 3 * GWEI)

    assert result == MaxValue(10**18 - 21000 * 3 * GWEI, GWEI, 3 * GWEI)


def test_max_value_estimates_gas_with_value():
    rpc = FakeRPC(gas=204600)
    values = []
    estimate = rpc.estimate_gas
    rpc.estimate_gas = lambda sender, to, value, data=b'': (
        values.append(value) or estimate(sender, to, value)
    )

    assert max_value(rpc, ADDRESS, DESTINATION).value == 10**18 - 204600 * 22 * GWEI
    assert values == [1]


def test_max_value_insufficient_funds():
    with pytest.raises(InsufficientFundsError, match='does not cover the max fee'):
        max_value(FakeRPC(balance=1000), ADDRESS, DESTINATION)
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_ethereum_api.py -q` — FAIL.

- [ ] **Step 3: Implementacja** — przed `PreparedEthereumTransaction` dodaj:

```python
def _resolve_fees(
    suggestion: FeeSuggestion,
    max_priority_fee_per_gas: Optional[int],
    max_fee_per_gas: Optional[int],
):
    """Fees per gas: the given ones, missing ones from the suggestion (the priority fee is not
    above the given max fee)."""
    if max_priority_fee_per_gas is None:
        max_priority_fee_per_gas = suggestion.max_priority_fee_per_gas
        if max_fee_per_gas is not None:
            max_priority_fee_per_gas = min(max_priority_fee_per_gas, max_fee_per_gas)
    if max_fee_per_gas is None:
        max_fee_per_gas = 2 * suggestion.base_fee_per_gas + max_priority_fee_per_gas
    return max_priority_fee_per_gas, max_fee_per_gas
```

W `prepare_transfer` zastąp blok `suggestion = suggest_fees(rpc)` + `if ... is None` przez:

```python
    suggestion = suggest_fees(rpc)
    max_priority_fee_per_gas, max_fee_per_gas = _resolve_fees(
        suggestion, max_priority_fee_per_gas, max_fee_per_gas
    )
```

Na końcu modułu (przed `wait_for_receipt` lub po nim):

```python
@dataclass(frozen=True)
class MaxValue:
    """The most wei which can be sent with the fees, the fees are used for the transaction."""

    value: int
    max_priority_fee_per_gas: int
    max_fee_per_gas: int


def max_value(
    rpc: EthereumRPC,
    sender: str,
    destination: str,
    max_priority_fee_per_gas: Optional[int] = None,
    max_fee_per_gas: Optional[int] = None,
) -> MaxValue:
    """The balance minus the max fee of the transfer to the destination. Gas is estimated with
    1 wei, because creating an account by sending ether costs more gas than a transfer without
    value. The unused part of the max fee stays on the address."""
    destination = validate_address(destination)
    balance = rpc.get_balance(sender)
    gas_limit = rpc.estimate_gas(sender, destination, 1)
    max_priority_fee_per_gas, max_fee_per_gas = _resolve_fees(
        suggest_fees(rpc), max_priority_fee_per_gas, max_fee_per_gas
    )
    max_fee = gas_limit * max_fee_per_gas
    if balance <= max_fee:
        raise InsufficientFundsError(
            f'Balance {format_ether(balance)} of {sender} does not cover the max fee '
            f'{format_ether(max_fee)}'
        )
    return MaxValue(balance - max_fee, max_priority_fee_per_gas, max_fee_per_gas)
```

- [ ] **Step 4:** `uv run python -m pytest tests/test_ethereum_api.py tests/test_sendeth.py -q` — PASS.

### Task 7: Parsowanie pól ETH, opis transakcji, czerwone ostrzeżenia

**Files:** Modify `multicrypto/gui/forms.py`, `multicrypto/gui/dialogs.py`,
Test `tests/test_gui_forms.py`, `tests/test_gui.py`

- [ ] **Step 1: Testy** w `tests/test_gui_forms.py` (importy z forms:
  `describe_ethereum_transaction, parse_ether_amount, parse_gwei_field, parse_rpc_nodes`;
  `from multicrypto.ethereum import GWEI, Transaction`;
  `from multicrypto.ethereum_api import FeeSuggestion, PreparedEthereumTransaction`):

```python
def test_parse_ether_amount():
    assert parse_ether_amount(' 0,5 ') == 5 * 10**17
    for text, message in (('0', 'greater than zero'), ('abc', 'not a number'), ('', 'Enter')):
        with pytest.raises(ValueError, match=message):
            parse_ether_amount(text)


def test_parse_gwei_field():
    assert parse_gwei_field('', 'Max fee') is None
    assert parse_gwei_field('1,5', 'Max fee') == 15 * 10**8
    with pytest.raises(ValueError, match='Max fee: abc is not a number'):
        parse_gwei_field('abc', 'Max fee')


def test_parse_rpc_nodes():
    assert parse_rpc_nodes('') == []
    assert parse_rpc_nodes('http://localhost:8545, https://node.example') == [
        'http://localhost:8545',
        'https://node.example',
    ]
    with pytest.raises(ValueError, match='must start with http'):
        parse_rpc_nodes('localhost:8545')


def make_prepared(max_fee_per_gas=22 * GWEI, value=10**17):
    transaction = Transaction(
        chain_id=11155111,
        nonce=3,
        max_priority_fee_per_gas=2 * GWEI,
        max_fee_per_gas=max_fee_per_gas,
        gas_limit=21000,
        to='0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed',
        value=value,
    )
    return PreparedEthereumTransaction(
        transaction,
        transaction.sign(1),
        '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf',
        10**18,
        FeeSuggestion(10 * GWEI, 2 * GWEI),
    )


def test_describe_ethereum_transaction():
    rows = describe_ethereum_transaction(make_prepared(), 'TETH', 'public nodes')

    assert rows == [
        ('From', '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'),
        ('To', '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed'),
        ('Amount', '0.1 TETH'),
        ('Nonce', '3'),
        ('Gas limit', '21000'),
        ('Max fee per gas', '22 gwei'),
        ('Priority fee per gas', '2 gwei'),
        ('Max fee', '0.000462 TETH'),
        ('Balance after', 'at least 0.899538 TETH'),
        ('Broadcast', 'public nodes'),
    ]


def test_describe_ethereum_transaction_with_warning():
    rows = describe_ethereum_transaction(make_prepared(max_fee_per_gas=5 * GWEI), 'ETH', 'own node')

    assert rows[-1] == (
        'Warning',
        'Max fee per gas 5 gwei is lower than the base fee 10 gwei of the next block, '
        'the transaction will wait until the base fee drops',
    )
```

W `tests/test_gui.py`:

```python
def test_confirm_dialog_shows_warnings_in_red(qapp):
    from multicrypto.gui.dialogs import ConfirmDialog

    dialog = ConfirmDialog(None, 'Confirm', [('Amount', '1'), ('Warning', 'High fee')], 'Send')

    labels = {label.text(): label for label in dialog.findChildren(QLabel)}
    assert 'c62828' in labels['High fee'].styleSheet()
    assert labels['1'].styleSheet() == ''
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui_forms.py tests/test_gui.py -q -k "ether or gwei or rpc_nodes or describe_ethereum or red"` — FAIL.

- [ ] **Step 3: Implementacja** — w `multicrypto/gui/forms.py` (import
  `from multicrypto.ethereum_api import PreparedEthereumTransaction, get_rpc`):

```python
def parse_ether_amount(text: str) -> int:
    """Amount in ether, e.g. 0.25, in wei."""
    value = text.strip().replace(',', '.')
    if not value:
        raise ValueError('Enter the amount')
    wei = ethereum.parse_ether(value)
    if wei <= 0:
        raise ValueError('Amount must be greater than zero')
    return wei


def parse_gwei_field(text: str, name: str) -> Optional[int]:
    """Fee per gas in gwei in wei, None for the empty field (the fee is suggested)."""
    value = text.strip().replace(',', '.')
    if not value:
        return None
    try:
        return ethereum.parse_gwei(value)
    except ValueError as error:
        raise ValueError(f'{name}: {error}') from None


def parse_rpc_nodes(text: str) -> List[str]:
    """URLs of JSON-RPC of Ethereum nodes separated with commas or whitespace."""
    urls = text.replace(',', ' ').split()
    for url in urls:
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f'URL of the node {url} must start with http:// or https://')
    return urls


def describe_ethereum_transaction(
    prepared: PreparedEthereumTransaction, coin_symbol: str, broadcast_target: str
) -> List[Tuple[str, str]]:
    """Rows of the summary shown before the Ethereum transaction is broadcast."""
    transaction = prepared.transaction

    def ether(wei: int) -> str:
        return f'{ethereum.format_ether(wei)} {coin_symbol}'

    rows = [
        ('From', prepared.sender),
        ('To', transaction.to),
        ('Amount', ether(transaction.value)),
        ('Nonce', str(transaction.nonce)),
        ('Gas limit', str(transaction.gas_limit)),
        ('Max fee per gas', f'{ethereum.format_gwei(transaction.max_fee_per_gas)} gwei'),
        (
            'Priority fee per gas',
            f'{ethereum.format_gwei(transaction.max_priority_fee_per_gas)} gwei',
        ),
        ('Max fee', ether(transaction.max_fee)),
        ('Balance after', f'at least {ether(prepared.balance - prepared.max_total)}'),
        ('Broadcast', broadcast_target),
    ]
    return rows + [('Warning', warning) for warning in prepared.fee_warnings()]
```

W `multicrypto/gui/dialogs.py` w `ConfirmDialog.__init__` po utworzeniu `value_label`:

```python
            if name == 'Warning':
                value_label.setStyleSheet(f'color: {WARNING_COLOR}')
```

i stała na górze modułu: `WARNING_COLOR = '#c62828'`.

- [ ] **Step 4:** testy z kroku 2 — PASS.

### Task 8: Zakładka Balance

**Files:** Modify `multicrypto/gui/balance_tab.py`, Test `tests/test_gui.py`

- [ ] **Step 1: Test** (import `import multicrypto.gui.balance_tab as balance_tab_module` i
  `from multicrypto.commands.checkaddress import EthereumAccount`):

```python
def test_balance_tab_checks_ethereum_address(qapp, window, monkeypatch):
    unlock(window)
    tab = window.balance_tab
    address = ethereum_address(window, 'TETH')
    checked = []

    def check(args):
        checked.append((args.coin_symbol, args.address, args.node))
        return EthereumAccount(args.address, 10**18 + 5, 3, None)

    monkeypatch.setattr(balance_tab_module, 'check_ethereum_address', check)

    tab.check_address(address)
    wait_until(qapp, lambda: tab.account.text())

    assert checked == [('TETH', address.address, None)]
    assert tab.account.text() == (
        f'Address: {address.address}\n'
        'Balance: 1.000000000000000005 TETH (1000000000000000005 wei)\n'
        'Sent transactions (nonce): 3\n'
        'All transactions: not available'
    )
    assert tab.filters.isHidden() and tab.table.isHidden() and tab.total.isHidden()
    tab.coin.setCurrentText('BTC')
    assert not tab.filters.isHidden() and tab.account.isHidden()
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui.py -q -k balance_tab` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/gui/balance_tab.py`:

Importy:

```python
from multicrypto.coins import is_ethereum
from multicrypto.commands.checkaddress import check_address, check_ethereum_address
from multicrypto.ethereum import format_ether
from multicrypto.gui.forms import (
    all_coins_with_api,
    format_amount,
    parse_address,
    parse_thresholds,
)
```

W `__init__`: `self.coin = coin_box(app.visible_coins(all_coins_with_api()))`,
`self.coin.currentTextChanged.connect(lambda _text: self._coin_changed())`; blok filtrów i układ:

```python
        self.filters = QWidget()
        filters = QHBoxLayout(self.filters)
        filters.setContentsMargins(0, 0, 0, 0)
        for text, field in (
            ('Minimum input', self.minimum),
            ('Maximum input', self.maximum),
            ('Limit of inputs', self.limit),
        ):
            filters.addWidget(QLabel(text))
            filters.addWidget(field)
        actions = QHBoxLayout()
        actions.addWidget(self.filters)
        actions.addStretch()
        actions.addWidget(self.check_button)
        self.account = QLabel()  # balance, nonce and transactions of Ethereum address
        self.account.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.addLayout(source)
        layout.addLayout(actions)
        layout.addWidget(self.table)
        layout.addWidget(self.total, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.account)
        layout.addStretch()
        self._update_mode()
```

Metody:

```python
def update_coins(self):
    set_coins(self.coin, self.app.visible_coins(all_coins_with_api()))


def _coin_changed(self):
    self._show_addresses()
    self._update_mode()


def _update_mode(self):
    """Ethereum addresses have a balance instead of unspent outputs."""
    ethereum = is_ethereum(self.coin.currentText())
    self.filters.setVisible(not ethereum)
    self.table.setVisible(not ethereum)
    self.total.setVisible(not ethereum)
    self.account.setVisible(ethereum)


def clear(self):
    self.picker.clear()
    self.table.setRowCount(0)
    self.total.setText('')
    self.account.setText('')


def check(self):
    try:
        coin_symbol, address = self._get_address()
        if not is_ethereum(coin_symbol):
            minimum, maximum, limit = parse_thresholds(
                self.minimum.text(), self.maximum.text(), self.limit.text()
            )
    except ValueError as error:
        self.app.show_error(error)
        return
    self.check_button.setEnabled(False)
    if is_ethereum(coin_symbol):
        args = Namespace(coin_symbol=coin_symbol, address=address, node=None)
        self.app.worker.run(
            lambda: check_ethereum_address(args),
            lambda account: self._show_account(account, coin_symbol),
            self._failed,
        )
        return
    args = Namespace(
        coin_symbol=coin_symbol,
        address=address,
        minimum_input_threshold=minimum,
        maximum_input_threshold=maximum,
        limit_inputs=limit,
    )
    self.app.worker.run(
        lambda: check_address(args), lambda utxos: self._show(utxos, coin_symbol), self._failed
    )


def _show_account(self, account, coin_symbol: str):
    self.check_button.setEnabled(True)
    tx_count = 'not available' if account.tx_count is None else str(account.tx_count)
    self.account.setText(
        f'Address: {account.address}\n'
        f'Balance: {format_ether(account.balance)} {coin_symbol} ({account.balance} wei)\n'
        f'Sent transactions (nonce): {account.nonce}\n'
        f'All transactions: {tx_count}'
    )
```

Do importów Qt dodaj `QWidget` (już jest) — sprawdź, że `QWidget` jest zaimportowany.

- [ ] **Step 4:** `uv run python -m pytest tests/test_gui.py -q -k balance_tab` — PASS.

### Task 9: Zakładka Send

**Files:** Modify `multicrypto/gui/send_tab.py`, Test `tests/test_gui.py`

- [ ] **Step 1: Testy** (importy: `import json`, `from multicrypto.coins import ethereum_coins`,
  `from multicrypto.ethereum import GWEI, decode_transaction`,
  `from PySide6.QtWidgets import QAbstractItemView`):

```python
ETH_DESTINATION = '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed'
TETH_NODE = ethereum_coins['TETH']['rpcs'][0]
FEE_HISTORY = {'baseFeePerGas': [hex(GWEI), hex(2 * GWEI)], 'reward': [[hex(GWEI)]]}


def add_node_results(results, node=TETH_NODE):
    for result in results:
        http_mock.add(http_mock.POST, node, json={'jsonrpc': '2.0', 'id': 1, 'result': result})


def test_send_tab_form_of_ethereum(window):
    unlock(window)
    tab = window.send_tab

    tab.select_source(ethereum_address(window, 'TETH'))

    assert tab.sources.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert not tab.form.isRowVisible(tab.fee)
    assert tab.form.isRowVisible(tab.ethereum_fees)
    assert not tab.advanced_form.isRowVisible(tab.minimum)
    assert not tab.advanced_form.isRowVisible(tab.p2p)
    assert not tab.max_button.isHidden()
    tab.coin.setCurrentText('BTC')
    assert tab.sources.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection
    assert tab.form.isRowVisible(tab.fee) and not tab.form.isRowVisible(tab.ethereum_fees)
    assert tab.max_button.isHidden()


@http_mock.activate
def test_send_ethereum(qapp, window, monkeypatch):
    unlock(window)
    address = ethereum_address(window, 'TETH')
    add_node_results([hex(11155111), hex(10**18), '0x0', '0x5208', FEE_HISTORY, '0xhash'])
    confirmations, sent = [], []
    monkeypatch.setattr(
        send_tab_module,
        'confirm',
        lambda parent, title, rows, button: confirmations.append(dict(rows)) or True,
    )
    monkeypatch.setattr(
        send_tab_module, 'show_text', lambda parent, title, label, text: sent.append(text)
    )
    tab = window.send_tab

    tab.select_source(address)
    tab.destination.setText(ETH_DESTINATION.lower())
    tab.amount.setText('0.5')
    tab.prepare()
    wait_until(qapp, lambda: sent)

    assert sent == ['0xhash']
    rows = confirmations[0]
    assert (rows['From'], rows['To'], rows['Amount']) == (
        address.address,
        ETH_DESTINATION,
        '0.5 TETH',
    )
    assert rows['Broadcast'] == 'public nodes'
    raw = json.loads(http_mock.calls[-1].request.body)['params'][0]
    transaction, sender = decode_transaction(bytes.fromhex(raw[2:]))
    assert (sender, transaction.chain_id, transaction.value) == (
        address.address,
        11155111,
        5 * 10**17,
    )
    assert transaction.max_fee_per_gas == 5 * GWEI  # 2 * base fee 2 gwei + tip 1 gwei


@http_mock.activate
def test_send_ethereum_with_given_fees_and_own_node(qapp, window, monkeypatch):
    unlock(window)
    address = ethereum_address(window, 'TETH')
    node = 'http://localhost:8545'
    add_node_results([hex(11155111), hex(10**18), '0x0', '0x5208', FEE_HISTORY, '0xhash'], node)
    confirmations = []
    monkeypatch.setattr(
        send_tab_module,
        'confirm',
        lambda parent, title, rows, button: confirmations.append(dict(rows)) or False,
    )
    tab = window.send_tab

    tab.select_source(address)
    tab.destination.setText(ETH_DESTINATION)
    tab.amount.setText('0.1')
    tab.priority_fee.setText('0.5')
    tab.max_fee.setText('1.5')
    tab.nodes.setText(node)
    tab.prepare()
    wait_until(qapp, lambda: confirmations)

    assert confirmations[0]['Max fee per gas'] == '1.5 gwei'
    assert confirmations[0]['Priority fee per gas'] == '0.5 gwei'
    assert confirmations[0]['Broadcast'] == 'own node'
    methods = [json.loads(call.request.body)['method'] for call in http_mock.calls]
    assert 'eth_sendRawTransaction' not in methods  # not confirmed


@http_mock.activate
def test_send_ethereum_max_and_suggest(qapp, window):
    unlock(window)
    tab = window.send_tab
    tab.select_source(ethereum_address(window, 'TETH'))
    tab.destination.setText(ETH_DESTINATION)
    add_node_results([hex(10**18), '0x5208', FEE_HISTORY])

    tab.fill_max()
    wait_until(qapp, lambda: tab.amount.text())

    assert tab.amount.text() == '0.999895'  # 1 - 21000 * 5 gwei
    assert (tab.priority_fee.text(), tab.max_fee.text()) == ('1', '5')
    assert 'stays on the address' in tab.amount_note.text()
    tab.priority_fee.clear()
    tab.max_fee.clear()
    add_node_results([FEE_HISTORY])
    tab.suggest_fees()
    wait_until(qapp, lambda: tab.max_fee.text())
    assert (tab.priority_fee.text(), tab.max_fee.text()) == ('1', '5')


def test_send_ethereum_requires_one_source_and_destination_for_max(window, monkeypatch):
    unlock(window)
    errors = []
    monkeypatch.setattr(window, 'show_error', errors.append)
    tab = window.send_tab
    tab.select_source(ethereum_address(window, 'TETH'))

    tab.fill_max()

    assert str(errors[0]) == 'Enter the address'
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui.py -q -k "send_tab_form or send_ethereum"` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/gui/send_tab.py`:

Importy:

```python
from PySide6.QtWidgets import (  # dodaj QHBoxLayout
    ...
    QHBoxLayout,
    ...
)

from multicrypto import ethereum_api
from multicrypto.api import broadcast_prepared, prepare_from_private_keys
from multicrypto.coins import coins, ethereum_coins, is_ethereum
from multicrypto.ethereum import format_ether, format_gwei
from multicrypto.gui.forms import (
    EXPECTED_ERRORS,
    address_details,
    all_coins_with_api,
    check_sources,
    describe_ethereum_transaction,
    describe_transaction,
    extract_txid,
    parse_address,
    parse_amount,
    parse_ether_amount,
    parse_gwei_field,
    parse_nodes,
    parse_rpc_nodes,
    parse_thresholds,
)
```

Stałe:

```python
UTXO_SOURCES_TEXT = 'From (one or more addresses with the same address type)'
ETHEREUM_SOURCES_TEXT = 'From (one address)'
P2P_NODES_PLACEHOLDER = 'optional, host[:port] separated with commas'
RPC_NODES_PLACEHOLDER = 'optional, JSON-RPC URLs of own nodes separated with commas'
MAX_NOTE = 'The unused part of the max fee stays on the address, the fee paid is usually lower.'
```

W `__init__`: `self.coin = coin_box(app.visible_coins(all_coins_with_api()))`;
`self.nodes.setPlaceholderText(P2P_NODES_PLACEHOLDER)`; po `self.amount`:

```python
        self.max_button = QPushButton('Max')
        self.max_button.clicked.connect(lambda _checked=False: self.fill_max())
        self.amount_field = QWidget()
        amount_row = QHBoxLayout(self.amount_field)
        amount_row.setContentsMargins(0, 0, 0, 0)
        amount_row.addWidget(self.amount)
        amount_row.addWidget(self.max_button)
        self.amount_note = QLabel()
        self.amount_note.setWordWrap(True)
        self.priority_fee = QLineEdit()
        self.max_fee = QLineEdit()
        for field in (self.priority_fee, self.max_fee):
            field.setPlaceholderText('automatic')
        self.suggest_button = QPushButton('Suggest')
        self.suggest_button.clicked.connect(lambda _checked=False: self.suggest_fees())
        self.ethereum_fees = QWidget()
        fees_row = QHBoxLayout(self.ethereum_fees)
        fees_row.setContentsMargins(0, 0, 0, 0)
        fees_row.addWidget(QLabel('Priority fee'))
        fees_row.addWidget(self.priority_fee)
        fees_row.addWidget(QLabel('Max fee'))
        fees_row.addWidget(self.max_fee)
        fees_row.addWidget(self.suggest_button)
```

Układ formularza (zastąp `form = QFormLayout()` ... `advanced_form.addRow('Nodes', self.nodes)`):

```python
        self.form = QFormLayout()
        self.form.addRow('To address', self.destination)
        self.form.addRow('', self.destination_status)
        self.form.addRow('Amount', self.amount_field)
        self.form.addRow('', self.amount_note)
        self.form.addRow('Fee rate (sat/vB)', self.fee)
        self.form.addRow('Fees per gas (gwei)', self.ethereum_fees)
        advanced = QGroupBox('Advanced')
        self.advanced_form = QFormLayout(advanced)
        self.advanced_form.addRow('Minimum input (satoshis)', self.minimum)
        self.advanced_form.addRow('Maximum input (satoshis)', self.maximum)
        self.advanced_form.addRow('Limit of inputs', self.limit)
        self.advanced_form.addRow(self.p2p)
        self.advanced_form.addRow('Nodes', self.nodes)
```

oraz `self.sources_label = QLabel(UTXO_SOURCES_TEXT)` dodane do layoutu zamiast
`QLabel('From (...)')`, `layout.addLayout(self.form)`, a na końcu `__init__`:
`self._update_mode()`.

Metody:

```python
def refresh(self):
    self._update_mode()
    ...  # dotychczasowa treść refresh


def update_coins(self):
    set_coins(self.coin, self.app.visible_coins(all_coins_with_api()))


def _update_mode(self):
    """Ethereum transactions have one source address and fees per gas in gwei."""
    ethereum = is_ethereum(self.coin.currentText())
    self.sources.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
        if ethereum
        else QAbstractItemView.SelectionMode.ExtendedSelection
    )
    self.sources_label.setText(ETHEREUM_SOURCES_TEXT if ethereum else UTXO_SOURCES_TEXT)
    self.max_button.setVisible(ethereum)
    self.form.setRowVisible(self.amount_note, ethereum and bool(self.amount_note.text()))
    self.form.setRowVisible(self.fee, not ethereum)
    self.form.setRowVisible(self.ethereum_fees, ethereum)
    for widget in (self.minimum, self.maximum, self.limit, self.p2p):
        self.advanced_form.setRowVisible(widget, not ethereum)
    self.nodes.setPlaceholderText(RPC_NODES_PLACEHOLDER if ethereum else P2P_NODES_PLACEHOLDER)


def clear(self):
    self.sources.setRowCount(0)
    self.destination.clear()
    self.amount.clear()
    self.amount_note.clear()
    self.priority_fee.clear()
    self.max_fee.clear()


def _single_source(self) -> WalletAddress:
    addresses = self._selected_addresses()
    if len(addresses) != 1:
        raise ValueError('Select one source address')
    return addresses[0]


def _ethereum_rpc(self, coin_symbol: str):
    """Client of the nodes entered in the form (public nodes when empty) and its
    description."""
    nodes = parse_rpc_nodes(self.nodes.text())
    rpc = ethereum_api.get_rpc(ethereum_coins[coin_symbol], nodes)
    return rpc, 'own node' if nodes else 'public nodes'


def _ethereum_fees(self):
    return (
        parse_gwei_field(self.priority_fee.text(), 'Priority fee'),
        parse_gwei_field(self.max_fee.text(), 'Max fee'),
    )


def suggest_fees(self):
    try:
        rpc, _ = self._ethereum_rpc(self.coin.currentText())
    except ValueError as error:
        self.app.show_error(error)
        return
    self.suggest_button.setEnabled(False)
    self.app.worker.run(
        lambda: ethereum_api.suggest_fees(rpc), self._show_suggestion, self._fees_failed
    )


def _show_suggestion(self, suggestion):
    self.suggest_button.setEnabled(True)
    self.priority_fee.setText(format_gwei(suggestion.max_priority_fee_per_gas))
    self.max_fee.setText(format_gwei(suggestion.max_fee_per_gas))


def _fees_failed(self, error):
    self.suggest_button.setEnabled(True)
    self.max_button.setEnabled(True)
    self.app.show_error(error)


def fill_max(self):
    coin_symbol = self.coin.currentText()
    try:
        source = self._single_source()
        destination = parse_address(self.destination.text(), coin_symbol)
        priority_fee, max_fee = self._ethereum_fees()
        rpc, _ = self._ethereum_rpc(coin_symbol)
    except ValueError as error:
        self.app.show_error(error)
        return
    self.max_button.setEnabled(False)
    self.app.worker.run(
        lambda: ethereum_api.max_value(rpc, source.address, destination, priority_fee, max_fee),
        self._show_max,
        self._fees_failed,
    )


def _show_max(self, result):
    self.max_button.setEnabled(True)
    self.amount.setText(format_ether(result.value))
    self.priority_fee.setText(format_gwei(result.max_priority_fee_per_gas))
    self.max_fee.setText(format_gwei(result.max_fee_per_gas))
    self.amount_note.setText(MAX_NOTE)
    self.form.setRowVisible(self.amount_note, True)


def prepare(self):
    coin_symbol = self.coin.currentText()
    if is_ethereum(coin_symbol):
        self._prepare_ethereum(coin_symbol)
        return
    ...  # dotychczasowa treść prepare


def _prepare_ethereum(self, coin_symbol: str):
    try:
        source = self._single_source()
        destination = parse_address(self.destination.text(), coin_symbol)
        value = parse_ether_amount(self.amount.text())
        priority_fee, max_fee = self._ethereum_fees()
        rpc, target = self._ethereum_rpc(coin_symbol)
    except ValueError as error:
        self.app.show_error(error)
        return
    coin = ethereum_coins[coin_symbol]
    private_key = self.app.wallet.private_key(source)
    self.prepare_button.setEnabled(False)
    self.app.worker.run(
        lambda: ethereum_api.prepare_transfer(
            coin,
            rpc,
            private_key,
            destination,
            value,
            max_priority_fee_per_gas=priority_fee,
            max_fee_per_gas=max_fee,
        ),
        lambda prepared: self._confirm_ethereum(rpc, coin_symbol, prepared, target),
        self._failed,
    )


def _confirm_ethereum(self, rpc, coin_symbol: str, prepared, target: str):
    self.prepare_button.setEnabled(True)
    rows = describe_ethereum_transaction(prepared, coin_symbol, target)
    if not confirm(self, 'Confirm transaction', rows, 'Send'):
        return
    self.prepare_button.setEnabled(False)
    self.app.worker.run(
        lambda: ethereum_api.broadcast_transaction(rpc, prepared), self._sent, self._failed
    )
```

W `_sent` dodaj `self.amount_note.clear()` i `self.form.setRowVisible(self.amount_note, False)`
po `self.amount.clear()`. Kolejność walidacji w `fill_max` (najpierw źródło, potem adres)
musi dawać komunikat `Enter the address` w teście z kroku 1, gdy źródło jest zaznaczone.

- [ ] **Step 4:** `uv run python -m pytest tests/test_gui.py -q -k "send"` — PASS (także stare
  testy wysyłki UTXO).

### Task 10: Menu adresu ETH i commit fazy 2

**Files:** Modify `multicrypto/gui/wallet_tab.py`

- [ ] **Step 1:** W `_show_menu` po `menu.addAction('Show QR...', self.show_qr)` zamień
  `if not is_ethereum(address.coin):` tak, żeby wysyłka była dla wszystkich monet, a sprawdzanie
  salda miało nazwę zależną od monety:

```python
ethereum = is_ethereum(address.coin)
menu.addAction(
    'Check balance' if ethereum else 'Check UTXO',
    lambda: self.app.balance_tab.check_address(address),
)
menu.addAction('Send from this address', lambda: self.app.send_tab.select_source(address))
if not ethereum:
    if get_any_coin(address.coin).get('apis'):
        menu.addAction('Sweep this address', lambda: self.app.sweep_tab.select_source(address))
    sign_action = menu.addAction('Sign message', lambda: self.app.sign_tab.select_address(address))
    sign_action.setEnabled(address.address_type != P2TR)
    menu.addAction('Translate to another coin...', lambda: self.translate_key(address))
```

- [ ] **Step 2:** `uv run python -m pytest -q && uv run ruff check . && uv run ruff format --check .` — PASS.
- [ ] **Step 3: Commit**

```bash
git add multicrypto/ethereum_api.py multicrypto/gui/ tests/
git commit -m "Check balances and send ether in the GUI"
```

---

# Faza 3: skanowanie

### Task 11: `BlockscoutAPI.get_usage`

**Files:** Modify `multicrypto/ethereum_api.py`, Test `tests/test_ethereum_api.py`

- [ ] **Step 1: Testy:**

```python
def add_address_info(info, status=200):
    if status == 200:
        http_mock.add(http_mock.GET, BLOCKSCOUT_ADDRESS, json=info)
    else:
        http_mock.add(http_mock.GET, BLOCKSCOUT_ADDRESS, status=status, body='error')


EMPTY_INFO = {'coin_balance': '0', 'has_token_transfers': False, 'has_tokens': False}


@pytest.mark.parametrize(
    'info, transactions, usage',
    [
        (EMPTY_INFO, 0, 0),
        (EMPTY_INFO, 2, 2),
        (dict(EMPTY_INFO, coin_balance='5'), 0, 1),  # received by an internal transaction
        (dict(EMPTY_INFO, has_token_transfers=True), 0, 1),
        (dict(EMPTY_INFO, has_tokens=True, coin_balance=None), 1, 2),
    ],
)
@http_mock.activate
def test_blockscout_get_usage(info, transactions, usage):
    add_address_info(info)
    page = {'items': [{'hash': '0x1'}] * transactions, 'next_page_params': None}
    http_mock.add(http_mock.GET, f'{BLOCKSCOUT_ADDRESS}/transactions', json=page)

    assert get_explorer(ETH).get_usage(ADDRESS) == usage


@http_mock.activate
def test_blockscout_get_usage_of_unknown_address():
    add_address_info(None, status=404)

    assert get_explorer(ETH).get_usage(ADDRESS) == 0
    assert len(http_mock.calls) == 1


@http_mock.activate
def test_blockscout_get_usage_rate_limit():
    add_address_info(None, status=429)

    with pytest.raises(RateLimitError):
        get_explorer(ETH).get_usage(ADDRESS)
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_ethereum_api.py -q -k usage` — FAIL.

- [ ] **Step 3: Implementacja** — stała modułu obok `TRANSIENT_ERROR_CODES`:
`NOT_FOUND = 404  # HTTP status of addresses unknown to the explorer`, a w `BlockscoutAPI`:

```python
    def get_usage(self, address: str) -> int:
        """Number of transactions of the address plus 1 when it has ether or tokens, 0 for
        unused addresses (also unknown to the explorer). The balance and the tokens find
        addresses which received ether only by internal transactions (e.g. from contracts) or
        received only tokens, they have no transactions in the list."""
        response = http_request(f'{self.base_url}/addresses/{address}', self.timeout)
        if response.status == NOT_FOUND:
            return 0
        info = check_response(response, self.base_url).json()
        holds = (
            int(info.get('coin_balance') or 0) > 0
            or bool(info.get('has_token_transfers'))
            or bool(info.get('has_tokens'))
        )
        return self.get_tx_count(address) + int(holds)
```

- [ ] **Step 4:** `uv run python -m pytest tests/test_ethereum_api.py -q` — PASS.

### Task 12: Discovery dla ETH

**Files:** Modify `multicrypto/discovery.py`, Test `tests/test_discovery.py`

- [ ] **Step 1: Testy:**

```python
def test_discover_ethereum_scans_only_receiving_chain():
    wallet = Wallet.create(MNEMONIC, '')
    used = used_addresses(
        wallet,
        [('ETH', 'ethereum', 0, RECEIVE_CHAIN, 3), ('ETH', 'ethereum', 1, RECEIVE_CHAIN, 0)],
    )
    checked = []

    found = discover(
        wallet, 'ETH', checked.append, lambda: False, tx_count=lambda address: int(address in used)
    )

    assert found == [
        DiscoveredAccount('ETH', 'ethereum', 0, [3], []),
        DiscoveredAccount('ETH', 'ethereum', 1, [0], []),
    ]
    assert sum(checked) == 24 + 21 + 20  # accounts 0, 1 and unused 2, no change chains


def test_discover_ethereum_uses_explorer(monkeypatch):
    explorers = []

    def ethereum_usage(coin):
        explorers.append(coin['chain_id'])
        return lambda address: 0

    monkeypatch.setattr(discovery, 'ethereum_usage', ethereum_usage)

    assert discover(Wallet.create(MNEMONIC, ''), 'TETH', lambda count: None, lambda: False) == []
    assert explorers == [11155111]


def test_add_discovered_ethereum_account():
    wallet = Wallet.create(MNEMONIC, '')

    added = add_discovered(wallet, [DiscoveredAccount('ETH', 'ethereum', 0, [0, 2], [])])

    assert added == 2  # the address 0 of the new group and the address 2
    [account] = wallet.get_group('ETH', 0).accounts
    assert [address.index for address in wallet.account_addresses(account)] == [0, 2]
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_discovery.py -q -k ethereum` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/discovery.py`:

```python
from multicrypto.api import RateLimitError, get_api
from multicrypto.coins import ETHEREUM, get_any_coin, is_ethereum
from multicrypto.ethereum_api import get_explorer

# Blockscout gets two requests for every Ethereum address
ETHEREUM_REQUEST_INTERVAL = 2 * REQUEST_INTERVAL
```

(stała pod `REQUEST_INTERVAL`), funkcje:

```python
def ethereum_usage(coin) -> Callable[[str], int]:
    """Usage of Ethereum address (transactions, ether or tokens) from the block explorer."""
    explorer = get_explorer(coin)
    pacer = Pacer(ETHEREUM_REQUEST_INTERVAL)

    def usage(address: str) -> int:
        pacer.wait()
        return explorer.get_usage(address)

    return usage


def _default_tx_count(coin_symbol: str, coin) -> Callable[[str], int]:
    return ethereum_usage(coin) if is_ethereum(coin_symbol) else coin_tx_count(coin)


def _scannable_coin(coin_symbol: str):
    coin = get_any_coin(coin_symbol)
    source = 'explorers' if is_ethereum(coin_symbol) else 'apis'
    if 'slip44' not in coin or not coin.get(source):
        raise ValueError(f'{coin_symbol} cannot be scanned, it has no SLIP-44 coin type or API')
    return coin
```

W `_scan_account`:

```python
    # Ethereum accounts have no change addresses
    chains = (RECEIVE_CHAIN,) if account.address_type == ETHEREUM else (RECEIVE_CHAIN, CHANGE_CHAIN)
    used = [
        scan_chain(
            lambda index, chain=chain: wallet.address_at(account, chain, index),
            tx_count,
            progress,
            cancelled,
            mapper,
        )
        for chain in chains
    ]
    return DiscoveredAccount(account.coin, account.address_type, account.account, *used)
```

W `scan_account` i `discover`: `tx_count or coin_tx_count(coin)` →
`tx_count or _default_tx_count(account.coin, coin)` / `_default_tx_count(coin_symbol, coin)`.
Import `coins` usuń, jeśli przestanie być używany.

- [ ] **Step 4:** `uv run python -m pytest tests/test_discovery.py -q` — PASS.

### Task 13: Skanowanie ETH w GUI i commit fazy 3

**Files:** Modify `multicrypto/gui/forms.py`, Test `tests/test_gui_forms.py`, `tests/test_gui.py`

- [ ] **Step 1: Testy** — w `test_coin_lists_with_ethereum` zamień linię o `scannable_coins` na
  `assert {'ETH', 'TETH'} <= set(scannable_coins())` i dopisz w `tests/test_gui.py`:

```python
def test_scan_dialog_lists_ethereum(window):
    unlock(window)

    dialog = scan_dialog_module.ScanDialog(window)

    assert {'ETH', 'TETH'} <= set(dialog.coins)


def test_ethereum_group_menu_scans_coin(window, monkeypatch):
    unlock(window)
    started = []
    monkeypatch.setattr(window.background_scan, 'start_coin', started.append)

    window.wallet_tab._group_actions('ETH')['Scan for used addresses']()

    assert started == ['ETH']
```

- [ ] **Step 2:** testy — FAIL.
- [ ] **Step 3:** w `forms.scannable_coins` zamień `coins_with_api()` na `all_coins_with_api()`
  i popraw docstring („Coins whose HD accounts can be scanned, Ethereum coins with the block
  explorer”).
- [ ] **Step 4:** `uv run python -m pytest -q && uv run ruff check . && uv run ruff format --check .` — PASS.
- [ ] **Step 5: Commit**

```bash
git add multicrypto/ethereum_api.py multicrypto/discovery.py multicrypto/gui/forms.py tests/
git commit -m "Scan Ethereum accounts for used addresses with Blockscout"
```

---

# Faza 4: Sign, Vanity, Translate, README, test na żywo

### Task 14: Zakładka Sign

**Files:** Modify `multicrypto/gui/sign_tab.py`, `multicrypto/gui/wallet_tab.py`,
Test `tests/test_gui.py`

- [ ] **Step 1: Testy:**

```python
WEB3_ADDRESS = '0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E'
WEB3_SIGNATURE = (
    '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3'
    '3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c'
)


def test_sign_and_verify_ethereum_message(qapp, window):
    unlock(window)
    address = ethereum_address(window, 'TETH')
    tab = window.sign_tab

    tab.select_address(address)
    tab.sign_message.setPlainText('Zażółć gęślą jaźń')
    tab.sign()
    wait_until(qapp, lambda: tab.signature.text())
    tab.verify_address.setText(address.address)
    tab.verify_message.setPlainText('Zażółć gęślą jaźń')
    tab.verify_signature.setText(tab.signature.text())
    tab.verify()

    assert len(tab.signature.text()) == 132
    assert tab.verify_coin.currentText() == 'TETH'  # detected from the wallet address
    assert 'Signature is valid' in tab.verify_result.text()


def test_verify_ethereum_message_of_other_address(window):
    unlock(window)
    tab = window.sign_tab
    tab.verify_coin.setCurrentText('BTC')

    tab.verify_address.setText(WEB3_ADDRESS)
    tab.verify_message.setPlainText('I♥SF')
    tab.verify_signature.setText(WEB3_SIGNATURE)
    tab.verify()

    assert tab.verify_coin.currentText() == 'ETH'
    assert 'Signature is valid' in tab.verify_result.text()
    tab.verify_signature.setText('0x1234')
    tab.verify()
    assert 'Signature must have 65 bytes' in tab.verify_result.text()
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui.py -q -k "ethereum_message"` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/gui/sign_tab.py`:

```python
from multicrypto import ethereum
from multicrypto.coins import P2TR, coins, is_ethereum
from multicrypto.ecdsa import sign_message, verify_signature
from multicrypto.gui.address_picker import WalletAddressPicker
from multicrypto.gui.dialogs import coin_box, set_coins
from multicrypto.gui.forms import all_coins, check_signable, parse_address
```

W `__init__` oba `coin_box(app.visible_coins(sorted(coins)))` → `all_coins()`; tytuł grupy:

```python
        sign_group = QGroupBox(
            'Sign message (p2pkh, p2sh-p2wpkh and p2wpkh addresses, BIP-137, taproot addresses '
            'are not supported; Ethereum addresses like personal_sign, EIP-191)'
        )
```

`update_coins` — oba `sorted(coins)` → `all_coins()`. `sign`:

```python
        self.signature.clear()
        self.sign_button.setEnabled(False)
        if is_ethereum(address.coin):
            private_key = self.app.wallet.private_key(address)
            self.app.worker.run(
                lambda: ethereum.sign_message(message, private_key), self._signed, self._failed
            )
            return
        wif = self.app.wallet.private_key_wif(address)
        self.app.worker.run(
            lambda: sign_message(coins[address.coin], message, wif, address.address_type).decode(),
            self._signed,
            self._failed,
        )
```

`_detect_coin`:

```python
    def _detect_coin(self, text: str):
        """Select the coin of the wallet address entered for verification, an address starting
        with 0x selects ETH unless an Ethereum coin is selected."""
        address_text = text.strip()
        if self.app.wallet is not None:
            for address in self.app.wallet.addresses():
                if address.address == address_text:
                    self.verify_coin.setCurrentText(address.coin)
                    return
        if address_text.startswith('0x') and not is_ethereum(self.verify_coin.currentText()):
            self.verify_coin.setCurrentText('ETH')
```

`verify`:

```python
    def verify(self):
        coin_symbol = self.verify_coin.currentText()
        message = self.verify_message.toPlainText()
        signature = self.verify_signature.text()
        try:
            address = parse_address(self.verify_address.text(), coin_symbol)
            if is_ethereum(coin_symbol):
                valid = ethereum.verify_message(message, signature, address)
            else:
                valid = verify_signature(coins[coin_symbol], message, signature, address)
        except ValueError as error:
            self._show_result(str(error), INVALID_COLOR)
            return
        ...  # dalej bez zmian
```

W `wallet_tab._show_menu` przenieś `Sign message` przed `if not ethereum:` (dla wszystkich
monet, z `setEnabled(address.address_type != P2TR)`).

- [ ] **Step 4:** `uv run python -m pytest tests/test_gui.py -q -k "sign"` — PASS.

### Task 15: Zakładka Vanity

**Files:** Modify `multicrypto/gui/vanity_tab.py`, Test `tests/test_gui.py`

- [ ] **Step 1: Test:**

```python
def test_vanity_search_ethereum_and_add_to_wallet(qapp, window):
    unlock(window)
    tab = window.vanity_tab
    tab.coin.setCurrentText('ETH')
    tab.pattern.setText('0xA')
    tab.workers.setValue(1)

    assert not tab.address_type.isEnabled()
    assert tab.address_type.currentText() == 'ethereum'
    assert 'Addresses start with 0x' in tab.pattern_status.text()
    assert '~16 attempts' in tab.pattern_status.text()
    tab.start()
    wait_until(qapp, lambda: not tab.result_group.isHidden(), seconds=60)

    address = tab.result_address.text()
    assert address.lower().startswith('0xa')
    assert private_key_to_address(parse_private_key(tab.result_key.text())) == address
    tab.result_label.setText('Vanity')
    tab.add_to_wallet()
    [imported] = window.wallet.imported_addresses()
    assert (imported.coin, imported.address) == ('ETH', address)
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui.py -q -k vanity_search_ethereum` — FAIL.

- [ ] **Step 3: Implementacja** w `multicrypto/gui/vanity_tab.py`:

```python
from multicrypto.coins import ETHEREUM, get_address_types, get_any_coin, is_ethereum
from multicrypto.gui.forms import (
    EXPECTED_ERRORS,
    add_private_key,
    all_coins,
    format_duration,
    parse_vanity_pattern,
)
```

`self.coin.addItems(sorted(coins))` → `self.coin.addItems(all_coins())`. `_coin_changed`:

```python
    def _coin_changed(self):
        coin_symbol = self.coin.currentText()
        if is_ethereum(coin_symbol):
            address_types = [ETHEREUM]
        else:
            address_types = [
                address_type
                for address_type in get_address_types(get_any_coin(coin_symbol))
                if address_type in VANITY_ADDRESS_TYPES
            ]
        self.address_type.blockSignals(True)
        self.address_type.clear()
        self.address_type.addItems(address_types)
        self.address_type.blockSignals(False)
        self.address_type.setEnabled(not is_ethereum(coin_symbol))
        self._validate_pattern()
```

`add_to_wallet` — wywołanie:

```python
            self.app.modify_wallet(
                lambda wallet: add_private_key(wallet, label, coin_symbol, wif, address_type)
            )
```

Komentarz przy `self.found`: `# coin, type, address, private key (WIF, hex for Ethereum)`.

- [ ] **Step 4:** `uv run python -m pytest tests/test_gui.py -q -k vanity` — PASS.

### Task 16: Tłumaczenie kluczy (Translate i dialog z portfela)

**Files:** Modify `multicrypto/gui/forms.py`, `multicrypto/gui/wallet_tab.py`,
`multicrypto/gui/translate_tab.py`, Test `tests/test_gui_forms.py`, `tests/test_gui.py`

- [ ] **Step 1: Testy** — `tests/test_gui_forms.py` (importy `source_wif, translated_private_key`):

```python
KEY_1_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn'


def test_translated_key_addresses_to_ethereum():
    key, addresses = translated_key_addresses(KEY_1_WIF, 'ETH')

    assert key == '0x' + '00' * 31 + '01'
    assert addresses == [('ethereum', '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf')]


def test_translated_private_key():
    assert translated_private_key(KEY_1_WIF, 'TETH') == '0x' + '00' * 31 + '01'
    assert translated_private_key(KEY_1_WIF, 'LTC').startswith('T')


def test_source_wif_of_ethereum_address():
    wallet = Wallet.create(' '.join(['abandon'] * 11 + ['about']), '')
    address = wallet.add_ethereum_key('Key', 'ETH', '00' * 31 + '01')

    assert source_wif(wallet, address) == KEY_1_WIF
```

`tests/test_gui.py`:

```python
def test_translate_key_tab_to_ethereum(window, monkeypatch):
    unlock(window)
    tab = window.translate_tab
    tab.key.setText('0x' + '00' * 31 + '01')
    tab.integer.setChecked(True)
    tab.key_output_coin.setCurrentText('ETH')

    tab.translate_key()

    assert tab.translated_key.text() == '0x' + '00' * 31 + '01'
    assert tab.key_addresses.item(0, 1).text() == '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'


def test_translate_ethereum_key_to_bitcoin_in_wallet(window, monkeypatch):
    unlock(window)
    address = window.modify_wallet(
        lambda wallet: wallet.add_ethereum_key('Eth', 'ETH', '00' * 31 + '01')
    )

    def accept(dialog):
        dialog.coin.setCurrentText('BTC')
        dialog.address_type.setCurrentText('p2pkh')
        assert dialog.address.text() == '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.TranslateKeyDialog, 'exec', accept)
    window.wallet_tab.translate_key(address)

    btc = [key for key in window.wallet.imported_addresses() if key.coin == 'BTC']
    assert [key.address for key in btc] == ['1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH']


def test_translate_bitcoin_key_to_ethereum_in_wallet(window, monkeypatch):
    unlock(window)
    address = window.modify_wallet(
        lambda wallet: wallet.add_wif(
            'Btc', 'BTC', 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn', 'p2pkh'
        )
    )

    def accept(dialog):
        dialog.coin.setCurrentText('ETH')
        assert not dialog.form.isRowVisible(dialog.address_type)
        assert dialog.address.text() == '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'
        dialog.accept()

    monkeypatch.setattr(wallet_tab_module.TranslateKeyDialog, 'exec', accept)
    window.wallet_tab.translate_key(address)

    eth = [key for key in window.wallet.imported_addresses() if key.coin == 'ETH']
    assert [key.address for key in eth] == ['0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf']
```

- [ ] **Step 2:** `uv run python -m pytest tests/test_gui_forms.py tests/test_gui.py -q -k "translat or source_wif"` — FAIL.

- [ ] **Step 3: Implementacja** — `multicrypto/gui/forms.py`:

```python
def translated_private_key(wif: str, output_symbol: str) -> str:
    """Private key in WIF format of another coin, or in hex format for Ethereum."""
    if is_ethereum(output_symbol):
        return ethereum.format_private_key(get_private_key_from_wif_format(wif)[0])
    return translate_private_key(wif, coins[output_symbol]['secret_prefix_bytes'])


def translated_key_addresses(wif: str, output_symbol: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Private key of another coin and its addresses of all supported types."""
    translated = translated_private_key(wif, output_symbol)
    private_key, compressed = get_private_key_from_wif_format(wif)
    if is_ethereum(output_symbol):
        return translated, [(ETHEREUM, ethereum.private_key_to_address(private_key))]
    coin = coins[output_symbol]
    address_types = get_address_types(coin) if compressed else (P2PKH,)
    return translated, [
        (
            address_type,
            convert_private_key_to_coin_address(private_key, coin, compressed, address_type),
        )
        for address_type in address_types
    ]


def source_wif(wallet: Wallet, address: WalletAddress) -> str:
    """Private key of the wallet address in WIF format, Ethereum keys as bitcoin WIF with
    compressed public key, so they can be translated to other coins."""
    if is_ethereum(address.coin):
        return convert_private_key_to_wif_format(
            wallet.private_key(address), coins['BTC']['secret_prefix_bytes']
        )
    return wallet.private_key_wif(address)
```

`multicrypto/gui/wallet_tab.py` — `TranslateKeyDialog`:

```python
        super().__init__(parent, title, symbols or all_coins(), submit)
        ...

    def _translated_wif(self) -> str:
        return translated_private_key(self.source_wif, self.coin.currentText())

    def update_preview(self):
        coin_symbol = self.coin.currentText()
        if not self.label.isModified():
            self.label.setText(f'{self.base_label} ({coin_symbol})')
        try:
            address = key_entry_address(
                coin_symbol, self._translated_wif(), self.address_type.currentText()
            )
        except ValueError as error:
            self.address.setText(f'({error})')
        else:
            self.address.setText(address)
```

`WalletTab.translate_key`:

```python
    def translate_key(self, address: WalletAddress):
        def submit(label, coin, key, address_type):
            self.app.modify_wallet(
                lambda wallet: add_private_key(wallet, label, coin, key, address_type)
            )

        TranslateKeyDialog(
            self,
            'Translate to another coin',
            source_wif(self.app.wallet, address),
            address.label,
            submit,
            symbols=self.app.visible_coins(all_coins()),
        ).exec()
```

Importy forms w wallet_tab: dodaj `source_wif, translated_private_key`; usuń
`from multicrypto.address import translate_private_key` i `coins`, jeśli nieużywane.
W `_show_menu` przenieś `Translate to another coin...` przed `if not ethereum:`.

`multicrypto/gui/translate_tab.py`:

```python
from multicrypto.gui.forms import (
    add_private_key,
    all_coins,
    parse_private_key_input,
    translate_address_text,
    translated_key_addresses,
)
```

W `__init__`: `self.key_output_coin = coin_box('LTC')` →

```python
        self.key_output_coin = coin_box('LTC')
        self.key_output_coin.clear()
        self.key_output_coin.addItems(all_coins())
        self.key_output_coin.setCurrentText('LTC')
```

`add_to_wallet` — `submit`:

```python
def submit(label, coin, key, address_type):
    self.app.modify_wallet(lambda wallet: add_private_key(wallet, label, coin, key, address_type))
```

- [ ] **Step 4:** `uv run python -m pytest tests/test_gui_forms.py tests/test_gui.py -q` — PASS.

### Task 17: README

**Files:** Modify `README.md`

- [ ] **Step 1:** W sekcji GUI (punkt 10) po opisie zakładek dopisz akapit:

```markdown
Ethereum (`ETH`) and its Sepolia testnet (`TETH`) are supported too: the account group
*Ethereum #n* has the addresses `m/44'/60'/n'/0/i` (group #0 has the addresses of MetaMask, the
address 0 of group #n is account n of Ledger Live), private keys are imported and shown in hex
format, Balance shows the balance, nonce and number of transactions, Send sends ether from one
address with EIP-1559 fees in gwei (*Max* sends the balance minus the max fee, *Suggest* fills the
fees suggested by the node), the scan finds used addresses with Blockscout, messages are signed
like `personal_sign` (EIP-191) and Vanity and Translate support Ethereum private keys. New and
restored wallets get the groups Ethereum #0 and TETH #0, existing wallets add them with
*New account...*.
```

W sekcji `### Ethereum` zmień zdanie „the GUI does not support them yet” na
„the GUI supports them too”.

- [ ] **Step 2:** `uv run ruff format --check .` — PASS (ruff formatuje bloki kodu w README).

### Task 18: Test na żywo i commit fazy 4

**Files:** skrypt w scratchpadzie, bez zmian w repo

- [ ] **Step 1:** Skrypt `live_gui.py` w scratchpadzie (uruchamiany z katalogu repo przez
  `uv run python <ścieżka>`, `QT_QPA_PLATFORM=offscreen`): tworzy `WalletFile` w scratchpadzie
  (`OPSLIMIT_MIN`), portfel z `generate_mnemonic()`, importuje oba klucze TETH z
  `testnet_wallet.json` przez `add_ethereum_key`, uruchamia `MainWindow`, woła
  `fetch_balances` (prawdziwe węzły) i sprawdza, że oba salda są > 0; potem w `SendTab` wybiera
  pierwszy klucz, wpisuje drugi adres i `0.001`, podmienia `send_tab.confirm` na funkcję
  zapisującą wiersze i zwracającą True, `send_tab.show_text` na zapisującą hash, woła
  `prepare()` i czeka (pętla `qapp.processEvents()`) na hash; na koniec
  `ethereum_api.wait_for_receipt(get_rpc(ethereum_coins['TETH']), hash, 180)` i wypisuje status,
  blok i opłatę. Klucze tylko z pliku, nigdy nie są wypisywane.
- [ ] **Step 2:** Skan na żywo (tylko odczyt): `discover(Wallet.create(MNEMONIC, ''), 'ETH', ...)`
  dla mnemoniki `abandon … about` na mainnecie przez Blockscout — oczekiwany co najmniej adres
  `m/44'/60'/0'/0/0` (`0x9858…`), który ma historię na mainnecie.
- [ ] **Step 3:** `uv run python -m pytest -q && uv run ruff check . && uv run ruff format --check .` — PASS.
- [ ] **Step 4:** Dopisz wyniki testu na żywo do sekcji „Testing” w specu i zrób commit:

```bash
git add multicrypto/gui/ README.md docs/superpowers/specs/2026-10-29-ethereum-gui-design.md tests/
git commit -m "Sign messages, search vanity addresses and translate keys of Ethereum in the GUI"
```
