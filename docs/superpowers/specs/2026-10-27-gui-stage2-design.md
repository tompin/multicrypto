# GUI etap 2: Sweep, Podpisz / Weryfikuj, kod QR — projekt

Data: 2026-10-27. Kontynuacja: `2026-10-27-gui-hd-wallet-design.md` (etap 1: portfel HD, Balance,
Send). Zastępuje zarys etapu 2 z `2026-10-26-gui-design.md` (tkinter).

## Cel

Dodać do GUI (PySide6) trzy funkcje odpowiadające komendom CLI: sweep (`sweepaddress`), podpis
i weryfikacja wiadomości (`signmessage` / `verifymessage`) oraz kod QR adresu. Podpisy mają działać
dla adresów segwit z portfela HD, nie tylko dla p2pkh.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Format podpisu | BIP-137 (jak Electrum, Sparrow, Trezor): p2pkh, p2sh-p2wpkh, p2wpkh; p2tr nieobsługiwany |
| Weryfikacja | odzyskany klucz publiczny porównywany z adresami wszystkich typów dla tego klucza |
| Kodowanie wiadomości | długości jako varint z bajtów UTF-8; bez limitu długości |
| Prefiks wiadomości | opcjonalny klucz `message_prefix` w `coins.py`; domyślnie `name.capitalize()` |
| Źródło sweepu | adres z portfela (konsolidacja) albo zewnętrzny WIF wklejony jednorazowo |
| Cel sweepu | ten sam adres (tylko źródło z portfela), adres z portfela tej samej monety, dowolny adres |
| Zewnętrzny WIF | nigdy zapisywany do pliku ani logów; pole czyszczone po sweepie i przy blokadzie |
| QR | sam adres (bez BIP-21), rysowany z macierzy `pyqrcode` na `QImage`, bez zapisu na dysk |
| Układ GUI | nowe zakładki Sweep oraz Sign / Verify; QR jako okno dialogowe z zakładki Wallet |
| Hasło przy podpisie | nie jest wymagane (jak w Send) |
| Teksty GUI | po angielsku, jak w etapie 1 |

Poza zakresem: BIP-322 (podpisy taproot), URI BIP-21 w QR, skanowanie wszystkich typów adresów
zewnętrznego WIF naraz, automatyczne ponawianie nieudanych partii sweepu.

## Biblioteka

### `multicrypto/ecdsa.py` — podpisy BIP-137

- `add_magic_prefix(message: str, coin) -> bytes` — `varint(len(prefix)) + prefix +
  varint(len(message_utf8)) + message_utf8`, gdzie `prefix = f'{message_prefix} Signed Message:\n'`.
  Dla wiadomości ASCII krótszych niż 128 znaków bajty są identyczne z obecnym `chr(len)`, więc
  dotychczasowe podpisy pozostają ważne. Dotąd wiadomości z 128+ bajtami lub znakami spoza ASCII
  dawały podpisy niezgodne z innymi portfelami.
- Prefiks: `coin.get('message_prefix', coin['name'].capitalize())`. W `coins.py` nadpisane:
  TBTC i TBCH → `Bitcoin`, TLTC → `Litecoin`, BTG → `Bitcoin Gold`, DASH → `DarkCoin` (Dash Core).
- `sign_message(coin, message, wif_private_key, address_type=P2PKH) -> bytes` (base64). Bajt
  nagłówka: p2pkh `27 + recid` (+4 dla klucza skompresowanego), p2sh-p2wpkh `35 + recid`,
  p2wpkh `39 + recid`. `ValueError` dla p2tr oraz dla typów segwit z kluczem nieskompresowanym.
- `verify_signature(coin, message: str, signature: str, address: str) -> bool` — dekoduje base64
  (65 bajtów), nagłówek 27–42 daje recid i informację o kompresji (35–42 zawsze skompresowany),
  odzyskuje klucz publiczny i zwraca `True`, gdy `address` jest adresem tego klucza dowolnego typu
  z `get_address_types(coin)` poza p2tr (dla nieskompresowanego tylko p2pkh). Dzięki temu przechodzą
  także podpisy segwit z nagłówkiem p2pkh (starsze Electrum, Trezor). Niepoprawny base64, długość
  lub nagłówek → `ValueError` z opisem.
- Obecna niskopoziomowa `verify_message(coin, message, v, signature, address)` jest usuwana (dziś
  używają jej tylko `sign_message` i CLI `verifymessage`). Odzyskiwanie klucza publicznego trafia
  do prywatnej `_recover_public_key(message_bytes, recid, r, s)`, której używają `sign_message`
  (wybór recid) i `verify_signature`.

### CLI

- `signmessage`: nowa opcja `-t/--address_type` (domyślnie p2pkh), usunięty limit długości.
- `verifymessage`: używa `verify_signature`; wypisuje `True` / `False`, błędy formatu przez logger.

### `multicrypto/api.py` — wspólny sweep

- `prepare_sweep(coin, utxos, destination_address, fee, batch_size) -> List[PreparedTransaction]`
  — dzieli UTXO na partie po `batch_size`; dla każdej `build_transaction` z
  `satoshis = suma − fee`, bez reszty, adres źródłowy z `source_address` pierwszego wejścia.
  `ValueError`, gdy lista jest pusta, suma partii ≤ fee albo `suma − fee` jest poniżej progu dust
  adresu docelowego.
- `commands/sweepaddress.py` używa `prepare_sweep` i `broadcast_prepared`; wynik dla użytkownika
  bez zmian (wypisuje odpowiedź API dla każdej partii).

## GUI

Nowe moduły: `gui/sweep_tab.py`, `gui/sign_tab.py`, `gui/qr.py`. Czyste funkcje w `gui/forms.py`.
`MainWindow`: zakładki Wallet | Balance | Send | Sweep | Sign / Verify; nowe zakładki implementują
`refresh()` (po zmianie portfela) i `clear()` (przy blokadzie).

### Zakładka Sweep

- Źródło (radio):
  - *Wallet address* — lista adresów portfela monet z API.
  - *External private key (WIF)* — moneta (z API), pole WIF (maskowane, z przełącznikiem
    „Show”), typ adresu spośród obsługiwanych przez monetę; pod spodem adres wyliczony z klucza
    na żywo albo czerwony błąd walidacji.
- Cel (radio):
  - *The same address* — tylko dla źródła z portfela.
  - *Wallet address* — adresy portfela tej samej monety.
  - *Other address* — pole z walidacją na żywo jak w Send.
- *Fee per transaction (satoshis)* — domyślnie 10000. *Advanced*: minimum input, maximum input,
  batch size (domyślnie 50).
- *Prepare sweep...* — w workerze: UTXO (`get_utxo_from_private_keys` z progami) i
  `prepare_sweep`. Potwierdzenie (`confirm`) pokazuje From, To, liczbę transakcji, liczbę wejść,
  sumę wejść, łączną opłatę, kwotę docierającą do celu oraz listę partii (wejścia, kwota, opłata,
  rozmiar).
- *Send* — partie rozgłaszane po kolei, każda osobnym zadaniem workera; status „Broadcast k/n”.
  Na koniec okno z listą txid. Błąd partii k zatrzymuje dalsze partie; komunikat zawiera błąd
  i txid partii 1…k−1. Po sukcesie pole WIF jest czyszczone.
- Po blokadzie portfela callbacki niczego nie pokazują, a kolejne partie nie startują.

### Zakładka Sign / Verify

- *Sign*: lista adresów portfela (p2tr wyszarzone z dopiskiem „taproot: not supported”), pole
  wiadomości (wieloliniowe), *Sign* (w workerze), wynik w polu tylko do odczytu z *Copy*.
- *Verify*: moneta, adres, wiadomość, podpis; *Verify* pokazuje zielone „Signature is valid”,
  czerwone „Signature is not valid” albo czerwony opis błędu formatu. Moneta jest wybierana
  ręcznie (np. TBTC i TLTC mają ten sam prefiks p2pkh); gdy wpisany adres jest w portfelu, moneta
  ustawia się sama.

### QR (`gui/qr.py`)

- `qr_image(text: str, scale: int = 6) -> QImage` — macierz `pyqrcode.create(text).code`, margines
  4 moduły, piksele bez wygładzania.
- `QrDialog(parent, address: WalletAddress)` — obraz, etykieta i adres do zaznaczenia, *Copy*,
  *Close*.

### Zakładka Wallet

- Przycisk *Show QR...* w rzędzie przycisków.
- Menu kontekstowe adresu: *Show QR...*, *Sweep this address*, *Sign message* (przełączają
  zakładkę i ustawiają w niej adres, jak *Send from this address*).

## Obsługa błędów

- Walidacja formularzy w `forms.py` przez `ValueError` → `app.show_error`: `parse_wif(text,
  coin_symbol, address_type)` (istniejące `check_wif_private_key`, klucz nieskompresowany
  odrzucany dla segwit), istniejące `parse_int` dla rozmiaru partii, `check_signable(address)` (p2tr), oraz
  `describe_sweep(prepared_list, coin_symbol, source, destination)` budujące wiersze potwierdzenia.
- Błędy API i odrzucone transakcje przez `describe_error`. Sweep nie ponawia automatycznie —
  ponowne *Prepare* pobierze tylko pozostałe UTXO.

## Testy

- `tests/test_ecdsa.py`: wektory zgodności dla p2pkh, p2sh-p2wpkh i p2wpkh z niezależnego źródła
  (testy Electrum / bitcoinjs-message); round-trip podpis–weryfikacja dla każdego typu i kilku
  monet; wiadomości z polskimi znakami i dłuższe niż 255 bajtów; zgodność starych podpisów ASCII;
  segwit z nagłówkiem p2pkh; `ValueError` dla p2tr i klucza nieskompresowanego przy segwit;
  prefiksy TBTC, BTG, DASH.
- `tests/test_api.py`: `prepare_sweep` na mockowanych UTXO — partie, brak reszty, fee ≥ suma,
  dust, pusta lista.
- `tests/test_signmessage.py`, `tests/test_verifymessage.py`, `tests/test_sweepaddress.py`:
  istniejące testy przechodzą; nowy test `signmessage -t p2wpkh`.
- `tests/test_gui_forms.py`: nowe funkcje `forms.py`.
- `tests/test_gui.py` (offscreen, mock sieci): sweep z portfela i z zewnętrznego WIF; przerwanie
  na drugiej partii; czyszczenie WIF przy blokadzie; Sign → Verify przez widgety; wyszarzony p2tr;
  `qr_image` — moduły odczytane z obrazu równe macierzy `pyqrcode`.
- Ręcznie po implementacji: sweep TBTC z portfela i z zewnętrznego WIF przez offscreen GUI;
  podpis p2wpkh z GUI zweryfikowany niezależną biblioteką w osobnym środowisku.
