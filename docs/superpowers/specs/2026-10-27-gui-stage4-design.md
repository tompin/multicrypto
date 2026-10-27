# GUI etap 4: wykrywanie adresów HD, opłata w sat/vB, łańcuch reszty — projekt

Data: 2026-10-27. Kontynuacja etapów 1–3 (`2026-10-27-gui-hd-wallet-design.md`,
`2026-10-27-gui-stage2-design.md`, `2026-10-27-gui-stage3-design.md`).

## Cel

1. Po odtworzeniu mnemonika (lub na żądanie) znaleźć użyte konta i adresy HD, żeby środki
   z portfela odtworzonego z innego programu były widoczne.
2. Opłata podawana jako stawka sat/vB (z podpowiedzią z API) zamiast stałej kwoty.
3. Reszta z transakcji kont HD na adresy łańcucha reszty (`…/1/i`), jak w Electrum i Sparrow.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Kiedy skanować | automatycznie po odtworzeniu mnemonika w kreatorze (można pominąć) oraz z menu File → *Scan for used addresses...* |
| Zakres skanowania | wybrane monety (domyślnie BTC), wszystkie typy adresów monety, konta 0, 1, … do pierwszego bez transakcji (BIP-44), łańcuchy odbioru i reszty |
| Adres użyty | ma co najmniej jedną transakcję (potwierdzoną lub w mempoolu), nie tylko UTXO |
| Gap limit | 20, okna po 20 adresów sprawdzane równolegle (4 wątki) |
| Opłata | stawka sat/vB (do 0,1), przycisk *Estimate* (1, 3, 6, 144 bloki) z API; bez trybu stałej kwoty w GUI |
| Liczenie opłaty | iteracja: zbuduj → zmierz vsize → przebuduj, jeśli `fee < ceil(stawka · vsize)` (najwyżej 5 przebiegów) |
| Reszta | źródła z jednego konta HD → następny adres łańcucha reszty, zapisywany w portfelu po udanym wysłaniu; w innych przypadkach na adres źródłowy |
| CLI | `sendcrypto` i `sweepaddress`: nowe `-r/--fee_rate`, wykluczające się z `-f`; domyślnie bez zmian |
| Format pliku | wersja 2 bez zmian; `HDAddress.chain` z wartością domyślną 0 |

Poza zakresem: tryb stałej opłaty w GUI, RBF / CPFP, opłaty specyficzne dla monet (np. ZIP-317
Zcash — stawkę trzeba wpisać ręcznie odpowiednio wysoką), skanowanie importowanych kluczy, wysyłka
całego salda („max”).

## Biblioteka

### `multicrypto/api.py`

- `InsightAPI.get_tx_count(address)` — `GET /addr/<address>?noTxList=1`,
  `txApperances + unconfirmedTxApperances`.
- `EsploraAPI.get_tx_count(address)` — `GET /address/<address>`,
  `chain_stats.tx_count + mempool_stats.tx_count`.
- `estimate_fee_rates() -> Dict[int, float]` (sat/vB dla 1, 3, 6, 144 bloków):
  Esplora `GET /fee-estimates`; Insight `GET /utils/estimatefee?nbBlocks=1,3,6,144`, wartość w
  coin/kB × 10⁸ / 1000, wartości ujemne pomijane. Brak danych → `ValueError`
  („Fee estimate is not available for <coin>, enter the rate”).
- `PreparedTransaction.vsize` — z `Transaction.create()`: rozmiar bez świadka (`base`) i pełny
  (`total`), `vsize = ceil((3 · base + total) / 4)`; dla transakcji bez segwit `vsize = total`.
- `build_transaction(..., change_address=None)` i `prepare_utxos(..., change_address=None)` —
  reszta na `change_address`, domyślnie na adres źródłowy.
- `prepare_with_fee_rate(coin, utxos, destination, satoshis, fee_rate, change_address=None)` —
  `fee = ceil(fee_rate · 150)`, potem `prepare_utxos`; dopóki `fee < ceil(fee_rate · vsize)`:
  `fee = ceil(fee_rate · vsize)` i ponownie (najwyżej 5 razy, potem `ValueError`). Lista UTXO jest
  materializowana, żeby ponowne przebiegi mogły dobrać wejścia od początku.
- `prepare_from_private_keys(..., fee=None, fee_rate=None, change_address=None)` i
  `prepare_sweep(..., fee=None, fee_rate=None)` — dokładnie jedno z `fee` / `fee_rate`; w sweepie
  stawka liczona dla każdej partii (bez reszty, więc wystarczają 2 przebiegi).

### CLI

- `sendcrypto` i `sweepaddress`: `-r/--fee_rate` (sat/vB, liczba > 0), w grupie wykluczającej się
  z `-f`; gdy żadne nie podane — dotychczasowa domyślna opłata `-f`.

### `multicrypto/wallet.py`

- `RECEIVE_CHAIN = 0`, `CHANGE_CHAIN = 1`; `HDAddress.chain: int = RECEIVE_CHAIN` (pole na końcu,
  pliki bez niego wczytują się z 0).
- Ścieżka adresu `<konto>/<chain>/<index>`, identyfikator `WalletAddress.id` =
  `<account.id>/<chain>/<index>` (identyfikatory nie są zapisywane w pliku).
- `address_at(account, chain, index) -> str` — adres bez dodawania do portfela.
- `next_change_address(account_id) -> WalletAddress` — następny indeks łańcucha reszty (max + 1),
  bez zapisu.
- `add_address(account_id, chain, index, label) -> WalletAddress` — dodaje adres (pomija, jeśli
  już jest).
- `new_address(account_id, label)` — bez zmian (łańcuch odbioru).

### `multicrypto/discovery.py` (nowy, bez Qt)

- `GAP_LIMIT = 20`, `THREADS = 4`, `MAX_ACCOUNTS = 100`, `MAX_ADDRESSES = 10000`.
- `scan_chain(address_at: Callable[[int], str], tx_count: Callable[[str], int], progress,
  cancelled) -> List[int]` — sprawdza okna `GAP_LIMIT` indeksów równolegle (`ThreadPoolExecutor`),
  przesuwa okno za ostatni użyty, kończy po `GAP_LIMIT` kolejnych nieużywanych; zwraca użyte
  indeksy; `MAX_ADDRESSES` → `ValueError` („Stopped after …”).
- `DiscoveredAccount(coin, address_type, account, receive: List[int], change: List[int])`.
- `discover(wallet, coin_symbol, progress, cancelled) -> List[DiscoveredAccount]` — dla każdego
  typu z `get_address_types` konta 0, 1, … (konto użyte, gdy którykolwiek łańcuch ma użyty adres),
  do pierwszego nieużytego; `tx_count` z `get_api(coin)`; `MAX_ACCOUNTS` → `ValueError`.
  `cancelled()` → `None` zamiast wyniku.
- Monety bez `slip44` lub bez API nie są oferowane do skanowania.

## GUI

### Okno *Scan for used addresses* (`gui/scan_dialog.py`)

- Lista monet z SLIP-44 i API z checkboxami (domyślnie BTC), *Scan*, *Cancel*, licznik
  „Checked N addresses”; skanowanie w `Worker` (monety po kolei).
- Wynik: lista znalezionych kont („BTC p2wpkh account 0: 7 receiving, 3 change”), błędy
  poszczególnych monet, *Add* — jeden `modify_wallet`: brakujące konta (etykieta
  `<moneta> <typ> #<n>`) i adresy (`Address i` / `Change i`); istniejące są pomijane.
- Otwierane z menu File oraz automatycznie po utworzeniu portfela z odtworzonego mnemonika
  (*Cancel* zostawia domyślne konto BTC p2wpkh).
- Blokada portfela w trakcie → przerwanie, wynik odrzucony.

### Zakładka Wallet

- Adresy reszty pod kontem razem z odbiorczymi, ze ścieżką `…/1/i` i etykietą `Change i`;
  widoczne w saldach, Send, Sweep i menu kontekstowym. *New address* tworzy adres odbiorczy.

### Opłata w Send i Sweep

- „Fee rate (sat/vB)” zamiast opłaty w satoshi; obok wybór 1 / 3 / 6 / 144 bloków i *Estimate*
  (w `Worker`, moneta źródła). Puste pole → błąd „Enter the fee rate or press Estimate”.
- Potwierdzenie Send: „Fee: 0.00000420 BTC (420 satoshis, 3.0 sat/vB)”, „Size: 140 vB”.
  Sweep: opłata i vsize każdej partii, suma opłat.

### Reszta w Send

- Źródła z jednego konta HD → `next_change_address` przy *Prepare*; potwierdzenie pokazuje
  adres i ścieżkę reszty. Po udanym wysłaniu (i tylko gdy transakcja ma wyjście reszty)
  `add_address(..., CHANGE_CHAIN, index, 'Change i')` przez `modify_wallet`; błąd zapisu →
  komunikat z adresem i ścieżką reszty („skanowanie go znajdzie”).
- Importowane klucze lub różne konta → reszta na adres źródłowy (jak dotąd).

## Obsługa błędów

- Skanowanie: błąd sieci przerywa daną monetę (komunikat w oknie), wyniki innych monet można
  dodać; bez automatycznych ponowień.
- `parse_fee_rate(text)` w `forms.py`: liczba > 0, najwyżej jedno miejsce po przecinku; powyżej
  1000 sat/vB ostrzeżenie w potwierdzeniu.
- Brak środków na opłatę → istniejący `InsufficientFundsError`.

## Testy

- `tests/test_api.py`: `get_tx_count`, `estimate_fee_rates` (Esplora, Insight, przeliczenie,
  pominięcie −1, brak danych), `prepare_with_fee_rate` (opłata ≥ stawka · vsize, dodatkowe
  wejście, reszta na `change_address`), `fee_rate` w `prepare_sweep`.
- `tests/test_transaction.py`: vsize dla transakcji p2pkh (= rozmiar) i p2wpkh (z wagi BIP-141).
- `tests/test_wallet.py`: adres reszty BIP-84 `m/84'/0'/0'/1/0` =
  `bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el` (wektor BIP-84, sprawdzony też przez `bip_utils`),
  wczytanie pliku bez `chain`, `next_change_address`, `add_address`.
- `tests/test_discovery.py`: przerwa < 20 przeskakiwana, przerwa 20 kończy, konta 0–1 użyte i 2
  nie, `cancelled`, limity — z fałszywym `tx_count`, bez sieci.
- `tests/test_sendcrypto.py`, `tests/test_sweepaddress.py`: `-r`, błąd przy `-f` i `-r` naraz.
- `tests/test_gui_forms.py`, `tests/test_gui.py`: `parse_fee_rate`, okno skanowania (zamockowane
  `discover`), Send z resztą `…/1/0` zapisaną po wysłaniu, *Estimate* z `http_mock`.
- Na żywo (TBTC): wysyłka z konta HD z resztą na `…/1/0` i stawką z *Estimate*; odtworzenie tego
  samego mnemonika w nowym pliku i skanowanie (muszą się znaleźć adresy odbiorcze i reszty);
  zwrot środków do portfela testowego.
