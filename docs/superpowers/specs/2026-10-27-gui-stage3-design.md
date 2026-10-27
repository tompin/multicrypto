# GUI etap 3: Translacja adresów i kluczy, Vanity — projekt

Data: 2026-10-27. Kontynuacja: `2026-10-27-gui-stage2-design.md` (Sweep, Sign / Verify, QR).
Zastępuje zarys etapu 3 z `2026-10-26-gui-design.md` (tkinter).

## Cel

Dodać do GUI (PySide6) odpowiedniki komend `transaddress` / `transprivkey` (ten sam klucz lub
hash160 dla innej monety, np. forków BTC) oraz `genaddress` (adresy vanity), z możliwością dodania
wyniku do portfela jako importowany klucz.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Translacja | zakładka Translate (dowolny adres base58 / WIF / klucz jako liczba) oraz „Translate to another coin...” w menu adresu portfela |
| Adres bech32 | nie jest tłumaczony (wymaga klucza); komunikat błędu |
| Rodzaj adresu do translacji | wykrywany z prefiksu (p2pkh / p2sh), bez przełącznika jak `-s` w CLI |
| Klucz po translacji | adresy wszystkich typów obsługiwanych przez monetę docelową; „Add to wallet” jako imported key |
| Typy vanity | p2pkh, p2sh-p2wpkh, p2wpkh; bez p2tr (tweak na kandydata — wielokrotnie wolniej) |
| Wzorzec vanity | początek całego adresu (jak w CLI): `1Abc`, `3Abc`, `bc1qabc` |
| Klucz vanity w GUI | zawsze skompresowany |
| Wyszukiwanie | moduł `multicrypto/vanity.py`, procesy `multiprocessing` w kontekście `spawn`, wspólny dla CLI i GUI |
| Wynik vanity | panel w zakładce z adresem i WIF (maskowany), etykietą, *Add to wallet* i *Discard* |
| Hasło | nie jest wymagane przy dodawaniu kluczy (klucz z portfela nie jest pokazywany) |
| Teksty GUI | po angielsku |

Poza zakresem: vanity p2tr, adres P2SH ze skryptu (`genaddress -i`) w GUI, wzorce w środku
adresu i bez rozróżniania wielkości liter, klucze nieskompresowane w GUI, zapis QR na dysk.

## Biblioteka

### `multicrypto/vanity.py` (nowy, bez Qt)

- `VANITY_ADDRESS_TYPES = (P2PKH, P2SH_P2WPKH, P2WPKH)`.
- `validate_vanity_pattern(pattern, coin_symbol, address_type) -> str` — zwraca wzorzec
  (dla bech32 zamieniony na małe litery). Base58: istniejące `validate_pattern(pattern,
  coin_symbol, is_script=address_type == P2SH_P2WPKH)`. Bech32: wymagany początek `<hrp>1q`
  i znaki z alfabetu bech32; typ musi być obsługiwany przez monetę (`validate_address_type`).
- `expected_attempts(pattern, coin_symbol, address_type) -> int` — base58:
  `58 ** (len(pattern) − len(wspólny początek najmniejszego i największego adresu zakresu))`
  (zakres z `get_address_range`); bech32: `32 ** (len(pattern) − len(hrp) − 2)`; minimum 1.
- `search_worker(coin_symbol, address_type, pattern, compressed, stop, attempts, results)` —
  funkcja na poziomie modułu (importowalna przez spawn). Losowy klucz startowy, kolejni kandydaci
  przez `point += G` (jak dziś w `generate_address`); funkcja adresu wybrana raz przed pętlą; co
  1000 prób dodaje do `attempts` (`multiprocessing.Value`) i sprawdza `stop`. Po trafieniu wkłada
  `(address, wif)` do `results` (`Queue`) i ustawia `stop`.
- `VanitySearch(coin_symbol, address_type, pattern, workers, compressed=True)`:
  `start()`, `attempts` (int), `result() -> Optional[Tuple[str, str]]` (bez blokowania),
  `failed` (procesy zakończone bez wyniku i bez `stop`), `stop()` (Event + join). Wzorzec
  sprawdzany w konstruktorze; `compressed=False` tylko z p2pkh.
- `commands/genaddress.py` używa `VanitySearch`: nowa opcja `-t/--address_type` (p2pkh,
  p2sh-p2wpkh, p2wpkh), `-w` zostaje jako alias p2sh-p2wpkh; postęp co 10 s jako suma wszystkich
  procesów; `-i`, `-u`, `-c`, `-d` bez zmian w działaniu.

### `multicrypto/address.py`

- `detect_address_kind(address, coin_symbol) -> str` — `'p2pkh'` albo `'p2sh'` z prefiksu
  adresu base58; `ValueError` dla bech32 („Bech32 (segwit) addresses cannot be translated, they
  need the private key”).
- Translacja adresu: istniejąca `translate_address` z prefiksami wykrytego rodzaju.
- Translacja klucza: istniejące `translate_private_key` i `get_integer` (liczba dziesiętna lub
  hex); adresy dla monety docelowej przez `convert_private_key_to_coin_address` dla każdego typu
  z `get_address_types`.

## GUI

Nowe moduły `gui/translate_tab.py`, `gui/vanity_tab.py`; czyste funkcje w `gui/forms.py`.
`MainWindow`: Wallet | Balance | Send | Sweep | Sign / Verify | Translate | Vanity. Nowe zakładki
implementują `refresh()` i `clear()`; `clear()` czyści klucze, Vanity zatrzymuje też wyszukiwanie.

### Zakładka Translate

- *Address*: adres, moneta źródłowa, moneta docelowa, *Translate* → wynik (zaznaczalny) i *Copy*;
  błędy na czerwono.
- *Private key*: klucz (maskowany, *Show*), przełącznik *WIF* / *Integer*, moneta docelowa,
  *Translate* → przetłumaczony WIF (maskowany, *Show*, *Copy*), tabelka adresów dla typów monety
  docelowej, *Add to wallet...* (etykieta i typ adresu → `add_wif`). Wynik czyszczony przy zmianie
  wejścia i przy blokadzie.

### „Translate to another coin...” (menu adresu w zakładce Wallet)

- Dialog: moneta docelowa (wszystkie), typ adresu (typy monety docelowej), adres tego samego klucza
  na żywo, etykieta (domyślnie `<etykieta> (<moneta>)`), *Add to wallet* → `add_wif` z kluczem
  przetłumaczonym przez `translate_private_key`. Klucz nie jest pokazywany.

### Zakładka Vanity

- Moneta, typ adresu (spośród `VANITY_ADDRESS_TYPES` obsługiwanych przez monetę), wzorzec
  z walidacją na żywo i podpowiedzią początku (np. „must start with bc1q”), liczba procesów
  (`QSpinBox`, domyślnie liczba rdzeni − 1, minimum 1, maksimum liczba rdzeni), szacunek
  „~N attempts, ~T” (szybkość ostatniego pomiaru, przed pierwszym uruchomieniem 10 000/s na
  proces).
- *Start* / *Stop*; timer co 1 s pokazuje liczbę prób, szybkość, czas; po wyniku procesy są
  zatrzymywane.
- Panel wyniku: adres, WIF (maskowany, *Show*, *Copy*), etykieta, *Add to wallet*, *Discard*;
  napis „Imported keys are not restored from the mnemonic, back up the key separately.” oraz
  ostrzeżenie, że niedodany wynik przepada przy blokadzie.
- Blokada portfela i zamknięcie okna zatrzymują wyszukiwanie i czyszczą wynik.

## Obsługa błędów

- `forms.py`: `parse_vanity_pattern`, `parse_private_key_input(text, integer) -> str` (WIF:
  base58 i suma kontrolna; Integer: zakres 1…n−1, wynik jako WIF BTC skompresowany jak w CLI),
  `translate_address_text(address, input_symbol, output_symbol) -> str`,
  `translated_key_addresses(wif, output_symbol) -> Tuple[str, List[Tuple[str, str]]]`
  (WIF monety docelowej i pary typ–adres). Błędy jako `ValueError`.
- Vanity: proces zakończony bez wyniku i bez Stop → zatrzymanie pozostałych i błąd w GUI; wzorzec
  dłuższy niż 7 znaków ponad część stałą → ostrzeżenie o czasie (bez blokady).
- Duplikat klucza przy *Add to wallet* → istniejący błąd `add_wif`.
- WIF nie trafia do logów ani na dysk; wynik z procesów wraca przez `Queue` w pamięci.

## Testy

- `tests/test_vanity.py`: `validate_vanity_pattern` (BTC p2pkh / p2sh-p2wpkh / p2wpkh, ZEC `t1`,
  błędy), `expected_attempts`, `VanitySearch` z 1 procesem i krótkim wzorcem (`1A`, `3A`,
  `bc1qq`, `tb1qq`) — adres zaczyna się od wzorca, a WIF wylicza ten adres; *Stop* przy wzorcu
  niemożliwym do szybkiego znalezienia.
- `tests/test_genaddress.py`: istniejące testy przechodzą; nowy test `-t p2wpkh`.
- `tests/test_address.py`: `detect_address_kind`.
- `tests/test_gui_forms.py`: nowe parsery i translacje (BTC → BTG p2pkh i p2sh; WIF i Integer →
  adresy typów LTC).
- `tests/test_gui.py` (offscreen): Translate (adres, klucz, *Add to wallet*), dialog *Translate to
  another coin* (adres HD → LTC p2wpkh, import), Vanity (*Start*, wynik, *Add to wallet*,
  *Discard*), blokada w trakcie wyszukiwania.
- Zgodność: adres i WIF z vanity p2wpkh sprawdzone niezależnie przez `bip_utils`.
