# GUI: grupy kont (moneta z podkontami typów adresów) — projekt

Data: 2026-10-28.

## Cel

Portfel ma działać podobnie do portfeli wielowalutowych (Ledger Live, Exodus): po utworzeniu lub
odtworzeniu portfela od razu widać konto każdej obsługiwanej monety ze wszystkimi typami adresów,
które ta moneta obsługuje. Konto w zakładce Wallet to „moneta #N” z podkontami typów, a nie
pojedyncze konto jednego typu.

Pod spodem zostają osobne konta BIP-44/49/84/86 (typ adresu jest częścią ścieżki derywacji),
więc zgodność z innymi portfelami (Sparrow, Electrum, Trezor, Ledger) się nie zmienia.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Model | grupowanie tylko w widoku i w API `Wallet`; `HDAccount` na typ zostaje, format pliku `.mcw` bez zmian |
| Grupa | konta o tej samej monecie i numerze konta (`coin`, `account`) |
| Kolejność podkont | `p2tr`, `p2wpkh`, `p2sh-p2wpkh`, `p2pkh` (jak w Ledger Live) |
| Etykieta grupy | zapisana w każdym koncie grupy; wspólna etykieta kont albo domyślna `<Name> #<N>` (np. `Bitcoin #0`, z `coin['name'].title()`), gdy etykiety się różnią |
| Nowy portfel | grupy #0 wszystkich monet z `slip44` (BTC, LTC, DOGE, DASH, TBTC, TLTC), każdy typ z adresem odbiorczym `0/0` — 18 kont |
| Odtworzenie | te same grupy #0; bez automatycznego skanu (znika dzisiejsze `start_coin('BTC')`) |
| Skan | tylko na żądanie: menu kontekstowe grupy, menu podkonta, File → Scan for used addresses |
| Skan monety | po numerach grup, wszystkie typy dla każdego numeru, koniec na pierwszym numerze bez transakcji w żadnym typie |
| Znalezione konto | nowa grupa jest zakładana w pełni (wszystkie typy, każdy z `0/0`) |
| New account | tworzy całą grupę z kolejnym wolnym numerem; bez wyboru typu |
| Istniejące portfele | bez migracji; stare konta pokazują się zgrupowane, grupy #0 nie są dodawane |
| Wysyłka | bez zmian: adresy źródłowe jednej transakcji muszą mieć ten sam typ |

## Model: `multicrypto/wallet.py`

- `ADDRESS_TYPE_ORDER = (P2TR, P2WPKH, P2SH_P2WPKH, P2PKH)` — kolejność podkont w grupie.
- `group_label(coin_symbol, number) -> str` — domyślna etykieta, np. `Bitcoin #0`,
  `Bitcoin Testnet #1`.
- `@dataclass AccountGroup` (nie jest zapisywana w pliku): `coin: str`, `number: int`,
  `label: str`, `accounts: List[HDAccount]` (w kolejności `ADDRESS_TYPE_ORDER`).
- `Wallet.account_groups() -> List[AccountGroup]` — grupuje `self.accounts` po
  `(coin, account)`, w kolejności pierwszego wystąpienia konta grupy w `self.accounts`. Etykieta:
  wspólna etykieta wszystkich kont grupy, a gdy się różnią — `group_label(coin, number)`.
- `Wallet.get_group(coin_symbol, number) -> AccountGroup` — `KeyError`, gdy grupy nie ma.
- `Wallet.next_group_number(coin_symbol) -> int` — o jeden większy od największego numeru
  konta tej monety w dowolnym typie (0, gdy moneta nie ma kont).
- `Wallet.add_account_group(label, coin_symbol, number=None) -> AccountGroup` — dla każdego typu
  z `get_address_types(coin)` zakłada `HDAccount` przez `add_account` z etykietą `label` (pusta →
  `group_label`) i dodaje adres odbiorczy `0/0` (`new_address`). `number=None` →
  `next_group_number`. Najpierw sprawdza wszystkie typy: gdy którekolwiek konto grupy już
  istnieje, zgłasza `ValueError` (komunikat jak w `add_account`) i nic nie dodaje. Monety bez
  `slip44` → `ValueError` jak w `add_account`.
- `Wallet.add_default_groups()` — `add_account_group('', symbol, 0)` dla każdej monety z
  `slip44`, w kolejności `coins`.
- `Wallet.rename_group(coin_symbol, number, label)` — ustawia etykietę wszystkich kont grupy.
- `Wallet.remove_group(coin_symbol, number)` — usuwa wszystkie konta grupy (mnemonik nadal je
  odtwarza).
- `WalletFile.create` — zamiast `add_account('Bitcoin', 'BTC', P2WPKH)` wywołuje
  `add_default_groups()`.
- `add_account` (jeden typ), `next_account_number`, `rename` i `remove` zostają (używane przez
  skan, podkonta i adresy).

## Skan: `multicrypto/discovery.py`

- `discover(wallet, coin_symbol, ...)` — dla numerów 0, 1, … (do `MAX_ACCOUNTS`) skanuje konta
  wszystkich typów monety o tym numerze (`_scan_account`). Konta z transakcjami (używany adres
  na łańcuchu odbiorczym lub reszty) dopisuje do `found` od razu po zeskanowaniu. Kończy na
  pierwszym numerze, w którym żaden typ nie ma transakcji. Po przekroczeniu `MAX_ACCOUNTS`
  numerów — `ValueError('Stopped after … accounts of <coin>')`.
- Dla monet z jednym typem (DOGE, DASH) wynik i liczba zapytań są takie jak dziś.
- `add_discovered(wallet, discovered)` — gdy grupy o monecie i numerze znalezionego konta nie ma
  w portfelu, zakłada ją przez `add_account_group('', coin, number)` (wszystkie typy, `0/0`).
  Gdy grupa istnieje, ale brakuje w niej konta danego typu, zakłada je przez `add_account` z
  etykietą grupy. Następnie dopisuje brakujące adresy jak dziś. Zwracana liczba dodanych adresów
  obejmuje adresy `0/0` nowych grup.
- Grupy z „dziurą” w numeracji (np. używana grupa #3 przy pustej #2) i adresy za gap limitem
  20 nie są znajdowane — użytkownik zakłada grupę przez New account z tym numerem i skanuje
  podkonto.

Przykład (BTC): używane `p2tr` #0 (0/0), `p2wpkh` #1 (0/0, 0/1), `p2pkh` #3 (0/0), reszta pusta.
Dzisiejszy skan po typach znajduje tylko `p2tr` #0. Skan po grupach znajduje `p2tr` #0 i
`p2wpkh` #1 (sprawdza ok. 480 adresów zamiast ok. 200), kończy na pustej grupie #2, więc
`p2pkh` #3 trzeba odtworzyć ręcznie.

## GUI

### `multicrypto/gui/wallet_tab.py` — drzewo

- Trzy poziomy:
  - grupa — kolumny: etykieta grupy, pusta ścieżka, symbol monety, suma sald adresów grupy,
  - podkonto — nazwa typu (`Taproot`, `Native SegWit`, `SegWit`, `Legacy`), ścieżka konta,
    pusta kolumna adresu, suma sald adresów podkonta,
  - adres — jak dziś (`chain/index`, adres, saldo).
- Nazwy typów w słowniku `ADDRESS_TYPE_NAMES = {P2TR: 'Taproot', P2WPKH: 'Native SegWit',
  P2SH_P2WPKH: 'SegWit', P2PKH: 'Legacy'}`.
- Suma pokazywana, gdy saldo znane dla co najmniej jednego adresu; adresy z błędem pobrania
  (tekst zamiast liczby) nie wchodzą do sumy.
- Nowy rodzaj elementu `ACCOUNT_GROUP = 'account_group'`, dane: `(ACCOUNT_GROUP, (coin, number))`.
- `_items()` przechodzi po wszystkich poziomach (rekurencyjnie), żeby `_select` zachowywał
  zaznaczenie po odświeżeniu.
- Grupa importowanych kluczy (`GROUP`) bez zmian.

### Przyciski i menu

- **New account...** — nowe okno `NewAccountGroupDialog` (zamiast `NewAccountDialog`): Label
  (opcjonalna), Coin (monety z `slip44`, domyślnie BTC), Account number (domyślnie
  `next_group_number`, aktualizowany po zmianie monety), Paths (podgląd ścieżek wszystkich typów
  monety, np. `m/86'/0'/1'`, `m/84'/0'/1'`, …). Zatwierdzenie → `add_account_group`; błąd
  (`EXPECTED_ERRORS`) w oknie z ostrzeżeniem, okno się nie zamyka. `_CoinTypeForm` zostaje dla
  Import WIF i Translate.
- **New address...** — podkonto lub adres: jak dziś. Grupa: komunikat „Select an address type
  first”. `_selected_account_id` bez skrótu „jedyne konto w portfelu” (nowy portfel ma 18 kont).
- **Rename...** — grupa: `rename_group`. Podkonto: komunikat „Rename the account group” (podkonto
  pokazuje nazwę typu). Adres i importowany klucz: jak dziś.
- **Remove...** — grupa: `remove_group` z ostrzeżeniem „The account group and its addresses will
  be removed from the list. The mnemonic still restores them.” Podkonto: usuwa jedno konto (grupa
  staje się niepełna). Adres i importowany klucz: jak dziś.
- Menu kontekstowe grupy: **Scan for used addresses** (tylko dla monet z `apis`) →
  `background_scan.start_coin(coin)`, czyli skan po grupach całej monety (wszystkie numery).
- Menu kontekstowe podkonta: jak dziś menu konta (New address, Scan for used addresses →
  `start_account`).

### `multicrypto/gui/window.py`

- `_created(wallet, restored)` — bez `background_scan.start_coin('BTC')`. Komunikat „New wallet”
  dla odtworzonego portfela dodaje: „To find used accounts and addresses, right-click a coin and
  choose Scan for used addresses (or File → Scan for used addresses).”

### Bez zmian

Zakładki Send, Sweep, Sign / Verify, Balance, Translate i Vanity (płaskie listy adresów
`coin typ · ścieżka · adres`), `BackgroundScan` (pasek statusu, anulowanie, dodawanie adresów
znalezionych przed błędem), okno File → Scan for used addresses (korzysta z nowego `discover`).

## Znane zachowania

- TBTC i TLTC mają ten sam numer SLIP-44 (`1`) oraz te same prefiksy `p2pkh` (`6f`) i `p2sh`
  (`c4`), więc konta `p2pkh` i `p2sh-p2wpkh` tych testnetów o tym samym numerze dają identyczne
  adresy. Różnią się tylko adresy bech32 (`tb1…`, `tltc1…`). Salda są pobierane z API właściwej
  sieci, więc działa to poprawnie; w drzewie ten sam adres występuje w dwóch grupach.
- Wyliczenie 18 adresów nowego portfela trwa ok. 0,75 s; przy tworzeniu i odblokowaniu adresy
  liczy wątek w tle (`_opened`), więc GUI się nie blokuje.
- Etykiety, puste konta i importowane klucze nie są odtwarzane z mnemonika.

## Błędy

- Konflikt z istniejącym kontem lub numer spoza `0…2³¹-1` w `add_account_group` → `ValueError`,
  pokazywany w oknie New account.
- Skan: zasady jak dziś — znalezione konta trafiają do `found` na bieżąco (przy błędzie API
  dodawane jest to, co znaleziono wcześniej), ponowne próby przy limitach zapytań, anulowanie.

## Testy

- `tests/test_wallet.py`: `add_account_group` dla BTC (4 konta w kolejności
  `ADDRESS_TYPE_ORDER`, każde z adresem `0/0` i etykietą) i DOGE (1 konto); pusta etykieta →
  `group_label`; konflikt → `ValueError` bez zmian w portfelu; `next_group_number` przy grupach
  niepełnych; etykieta grupy wspólna i domyślna przy różnych etykietach; `rename_group`,
  `remove_group`; `add_default_groups` daje 18 kont; `WalletFile.create` zapisuje grupy #0 i
  plik po odczycie ma te same konta.
- `tests/test_discovery.py`: przykład z sekcji Skan (`p2tr` #0 i `p2wpkh` #1 znalezione,
  `p2pkh` #3 nie); `add_discovered` zakłada pełną grupę i liczy jej adresy `0/0`; etykieta
  istniejącej grupy dla brakującego typu; dotychczasowe testy dostosowane do skanu po grupach.
- `tests/test_gui.py`: drzewo grupa → podkonto → adres z sumami sald; New address na grupie →
  komunikat; Rename i Remove na grupie; `NewAccountGroupDialog` (numer i podgląd ścieżek po
  zmianie monety, zatwierdzenie tworzy grupę); pozycja Scan for used addresses w menu grupy;
  odtworzenie portfela nie uruchamia skanu.

## Dokumentacja

README, sekcja GUI: grupy kont (moneta #N z podkontami typów, grupy #0 wszystkich monet w nowym
portfelu), skan na żądanie z menu monety zamiast automatycznego skanu BTC po odtworzeniu, przypadki
do ręcznego odtworzenia (dziura w numeracji grup, adresy za gap limitem).
