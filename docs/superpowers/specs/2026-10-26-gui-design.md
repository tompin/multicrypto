# GUI dla multicrypto — projekt

Data: 2026-10-26

## Cel

Graficzny interfejs (Tkinter/ttk) do komend multicrypto, zbudowany wokół zaszyfrowanego portfela:
klucze prywatne są zapisywane na dysk wyłącznie w postaci zaszyfrowanej, w jednym pliku.

## Decyzje

- **Toolkit:** Tkinter/ttk z biblioteki standardowej.
- **Kryptografia pliku:** PyNaCl (libsodium) — XChaCha20-Poly1305 + Argon2id. Jedyna nowa zależność,
  jako opcjonalne extra `multicrypto[gui]`; CLI nadal wymaga tylko `pypng` i `PyQRCode`.
- **Architektura:** GUI działa w tym samym procesie i wywołuje funkcje biblioteki bezpośrednio.
  Odrzucone: uruchamianie komend CLI jako subprocess (klucze w argv, widoczne w `ps`/`/proc`)
  oraz lokalny serwer WWW (otwarty port przy odblokowanym portfelu).
- **Model wpisu portfela:** etykieta + moneta + WIF + typ adresu. Jeden wpis = jeden adres
  (mapuje się 1:1 na argumenty CLI); ten sam klucz w innym typie adresu to osobny wpis.

## Etapy

| Etap | Zakres |
|------|--------|
| 1 | Portfel, Saldo (`checkaddress`), Wyślij (`sendcrypto`) |
| 2 | Sweep (`sweepaddress`), Podpisz / Weryfikuj (`signmessage` / `verifymessage`), podgląd QR adresu |
| 3 | Translacja (`transaddress` / `transprivkey`), Vanity (`genaddress`) |

Poza zakresem: wysyłka z P2SH z ręcznymi skryptami (`-i/-u`), portfele HD / frazy seed,
wiele plików portfela otwartych jednocześnie.

Ten dokument szczegółowo opisuje etap 1; etapy 2 i 3 dostaną własne plany implementacji.

## Struktura modułów

```
multicrypto/
  wallet.py            # model portfela + szyfrowanie (PyNaCl), bez tkinter
  api.py               # podział budowy transakcji i rozgłaszania
  gui/
    __init__.py
    app.py             # main(): okno, Notebook z zakładkami, auto-blokada, pętla kolejki
    worker.py          # zadania w wątku + przekazywanie wyników do wątku Tk
    forms.py           # czyste helpery formularzy (bez tkinter), testowalne
    unlock.py          # dialogi: nowy portfel / odblokuj / zmień hasło
    wallet_tab.py      # lista wpisów, import WIF, generowanie klucza, usuwanie, pokaż WIF
    balance_tab.py     # checkaddress
    send_tab.py        # sendcrypto: formularz → podgląd → potwierdzenie → broadcast
```

`pyproject.toml`:

- `[project.scripts]`: `multicrypto-gui = "multicrypto.gui.app:main"`
- `[project.optional-dependencies]`: `gui = ["PyNaCl>=1.5"]`
- grupa `dev`: dodać `pynacl`, żeby CI zawsze testowało portfel.

Jeśli PyNaCl nie jest zainstalowany, `multicrypto-gui` pokazuje komunikat
„zainstaluj `multicrypto[gui]`” i kończy działanie.

## Plik portfela

**Lokalizacja:** domyślnie `~/.multicrypto/wallet.mcw` (katalog `0700`, plik `0600`); inną ścieżkę
można wskazać w dialogu otwierania.

**Format** (liczby big-endian):

```
offset  rozmiar  pole
0       8        magic b'MCWALLET'
8       1        wersja formatu (1)
9       8        opslimit Argon2id (uint64)
17      8        memlimit Argon2id (uint64)
25      16       sól
41      24       nonce XChaCha20
65      …        szyfrogram + 16 B tag Poly1305
```

- Nagłówek (bajty 0–64) jest przekazywany jako AAD do XChaCha20-Poly1305 — każda modyfikacja
  wersji, parametrów, soli lub nonce kończy się błędem uwierzytelnienia.
- Klucz: `nacl.pwhash.argon2id.kdf(32, hasło, sól, opslimit, memlimit)`. Domyślnie
  `OPSLIMIT_MODERATE` / `MEMLIMIT_MODERATE` (256 MiB). Parametry są zapisane w pliku, więc można je
  podnieść w przyszłości bez łamania starych portfeli.
- Szyfrowana jest cała treść (także etykiety i monety). Treść to JSON w UTF-8:

  ```json
  {"entries": [{"id": "<uuid4>", "label": "Oszcz.", "coin": "BTC",
                "wif": "Kx…", "address_type": "p2wpkh", "created": "2026-10-26T12:00:00Z"}]}
  ```

  Adres nie jest zapisywany — jest wyliczany z WIF, monety i typu przy odblokowaniu.

**Zapis:** każdy zapis używa nowego losowego nonce (24 B) przy tej samej soli i kluczu (bez
ponownego Argon2). Plik jest pisany do `wallet.mcw.tmp` z uprawnieniami `0600`, potem `fsync`
i `os.replace()` — zapis atomowy.

### API `multicrypto/wallet.py`

- `WalletEntry` (dataclass): `id`, `label`, `coin`, `wif`, `address_type`, `created`;
  właściwość `address` wyliczana przez `convert_private_key_to_coin_address`.
- `Wallet`:
  - `add_wif(label, coin, wif, address_type) -> WalletEntry` — walidacja przez
    `validate_wif_private_key` i `validate_address_type`; odrzuca duplikat
    (ta sama moneta + WIF + typ).
  - `generate(label, coin, address_type) -> WalletEntry` — klucz z `secp256k1.gen_private_key()`
    (`os.urandom`), skompresowany WIF.
  - `remove(entry_id)`.
- `WalletFile(path, opslimit=..., memlimit=...)`:
  - `create(password) -> Wallet` — błąd, jeśli plik istnieje.
  - `unlock(password) -> Wallet`.
  - `save(wallet)`.
  - `change_password(old, new)` — nowa sól, ponowne szyfrowanie.
  - `lock()` — porzuca klucz i referencję do wpisów.
- Złe hasło lub uszkodzony plik (błąd uwierzytelnienia) → `WalletError`
  „Nieprawidłowe hasło lub uszkodzony plik”. Nieznany magic, nieobsługiwana wersja lub plik
  krótszy niż nagłówek → `WalletError` „Nieobsługiwany format pliku portfela” (sprawdzane przed
  Argon2, nic nie zdradza o haśle).

## Bezpieczeństwo w GUI

- Hasło przy tworzeniu: minimum 10 znaków, wpisywane dwukrotnie.
- Auto-blokada po 5 minutach bezczynności (konfigurowalne): `WalletFile.lock()`, wyczyszczenie
  widoków, powrót do dialogu odblokowania. Pasek stanu pokazuje odliczanie.
- „Pokaż WIF” wymaga ponownego wpisania hasła; WIF znika z okna po 30 s.
- Do schowka kopiowane są wyłącznie adresy, nigdy WIF.
- Argon2 (odblokowanie, zmiana hasła) działa w wątku roboczym z komunikatem „Odblokowywanie…”.
- Znane ograniczenie (do opisania w README): Python nie gwarantuje wyczyszczenia `str`/`bytes`
  z pamięci; auto-blokada skraca czas przebywania kluczy w RAM.

## Ekrany (etap 1)

**Start:** brak domyślnego pliku → wybór „Utwórz nowy portfel” / „Otwórz plik…”; w przeciwnym
razie dialog hasła.

**Okno główne:** menu Plik (Nowy portfel, Otwórz…, Zmień hasło, Zablokuj, Zakończ), zakładki
Portfel / Saldo / Wyślij, pasek stanu (ścieżka pliku, stan blokady, odliczanie auto-blokady).

```
┌ multicrypto — ~/.multicrypto/wallet.mcw ───────────────────────────┐
│ Plik                                                                │
│ ┌Portfel┐┌Saldo┐┌Wyślij┐                                           │
│ │ Etykieta   Moneta  Typ      Adres                               │ │
│ │ Mining     ZEN     p2pkh    znXk…                               │ │
│ │ Oszcz.     BTC     p2wpkh   bc1q…                               │ │
│ │ [Importuj WIF] [Generuj nowy] [Kopiuj adres] [Pokaż WIF] [Usuń] │ │
│ └─────────────────────────────────────────────────────────────────┘ │
│ Odblokowany · auto-blokada za 4:12                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Portfel

- Treeview: Etykieta, Moneta, Typ, Adres. Menu kontekstowe: „Sprawdź saldo”, „Wyślij z tego
  adresu” — przełącza zakładkę z preselekcją wpisu.
- Importuj WIF / Generuj nowy: dialog z etykietą, monetą (combobox wszystkich monet), typem adresu
  (combobox filtrowany przez `get_address_types(coin)`), przy imporcie pole WIF z `show='•'`.
  Przed zapisem pokazywany jest wyliczony adres.
- Usuń: ostrzeżenie „klucz zostanie trwale usunięty — upewnij się, że masz kopię”, domyślny
  przycisk „Anuluj”.
- Każda zmiana od razu zapisuje plik.

### Saldo (`checkaddress`)

- Źródło: wpis z portfela albo ręczny adres + moneta (tylko monety z `apis`).
- Opcjonalne filtry: minimum, maksimum, limit wejść.
- Wynik: tabela txid / potwierdzenia / satoshi / kwota + wiersz sumy.

### Wyślij (`sendcrypto`)

- Źródła: jeden lub więcej wpisów portfela; wszystkie muszą mieć tę samą monetę i typ adresu
  (wymóg `send_from_private_keys`), GUI to wymusza.
- Adres docelowy walidowany na bieżąco przez `validate_address`.
- Kwota w jednostkach monety, przeliczana na satoshi przez `Decimal` (maks. 8 miejsc po
  przecinku, > 0). Opłata w satoshi, domyślnie 10000.
- „Zaawansowane”: min/max/limit wejść, wysyłka P2P, lista węzłów `host[:port]`.

**Przepływ:**

1. „Przygotuj” — w wątku: pobranie UTXO, wybór wejść, budowa i podpis transakcji. Nic nie jest
   wysyłane.
2. Dialog „Potwierdź transakcję”: adresy źródłowe, adres docelowy, kwota, opłata, reszta i jej
   adres, liczba wejść, rozmiar w bajtach; wyróżniona informacja, jeśli reszta poniżej progu dust
   została dodana do opłaty. Domyślny przycisk „Anuluj”.
3. „Wyślij” — w wątku: rozgłoszenie przez API lub P2P; wynik: txid z przyciskiem „Kopiuj”.

## Zmiany w `multicrypto/api.py`

Rozdzielenie budowy transakcji od rozgłaszania; zachowanie CLI bez zmian.

- `PreparedTransaction` (dataclass): `raw_transaction`, `inputs`, `outputs`, `fee`,
  `input_satoshis`, `change_added_to_fee`.
- `build_transaction(...) -> PreparedTransaction` — logika budowy wydzielona z `send_inputs`.
- `send_inputs(...)` — wrapper: `build_transaction` → `broadcast_prepared` (sweepaddress bez zmian).
- `prepare_utxos(...)`, `prepare_from_private_keys(...) -> PreparedTransaction`.
- `send_utxos(...)`, `send_from_private_keys(...)` — wrappery prepare → broadcast.
- `broadcast_prepared(coin, prepared, broadcast=None) -> str` — API monety albo przekazana funkcja
  (np. P2P z `network.broadcast_transaction`).

## Wątki i obsługa błędów

- `gui/worker.py`: `run_task(func, on_success, on_error)` — funkcja w `threading.Thread`, wynik
  w `queue.Queue`, kolejka sprawdzana co 100 ms przez `root.after`; widżety Tk modyfikowane
  wyłącznie w wątku głównym. Na czas zadania przyciski akcji są wyłączone.
- Błędy znane (`ValueError`, `WalletError`, `InsufficientFundsError`, `NetworkError`, błędy HTTP)
  → `messagebox` z treścią błędu. Nieznane → ogólny komunikat + `logger.exception`.

## Testy

- `tests/test_wallet.py`: cykl create → unlock → save → unlock; złe hasło; modyfikacja każdego pola
  nagłówka i szyfrogramu → `WalletError`; nowy nonce przy każdym zapisie; uprawnienia `0600` i brak
  `.tmp` po zapisie; `change_password`; odrzucenie WIF innej monety, nieobsługiwanego typu adresu
  i duplikatu; `generate()` daje poprawny WIF i adres; adresy zgodne z wektorami z testów
  `address`. Parametry Argon2 w testach: `OPSLIMIT_MIN` / `MEMLIMIT_MIN`.
- `tests/test_api.py`: `prepare_from_private_keys` (na `http_mock`) daje ten sam
  `raw_transaction`, który obecne testy `sendcrypto` oczekują w wysyłce; `broadcast_prepared`
  przez API i przez własną funkcję. Istniejące testy CLI przechodzą bez zmian.
- `tests/test_gui_forms.py`: parsowanie kwoty `Decimal` → satoshi, wymóg tej samej monety i typu
  źródeł, walidacja formularzy.
- Smoke test GUI: budowa okna na tymczasowym portfelu i przełączanie zakładek; `pytest.skip`
  przy braku wyświetlacza (`TclError`); w CI uruchamiany przez `xvfb-run`.
- Test ręczny przed wydaniem: wysyłka TBTC i TLTC przez GUI (p2wpkh i p2tr) kluczami z
  `testnet_wallet.json`, weryfikacja txid w eksploratorze.

## Etapy 2 i 3 (zarys)

- **Sweep:** `prepare` dla wielu partii, podgląd listy transakcji, jedno potwierdzenie, rozgłaszanie
  po kolei z postępem.
- **Podpisz / Weryfikuj:** podpis kluczem z portfela, weryfikacja dowolnego adresu.
- **QR:** PyQRCode → XBM → `tk.BitmapImage`, bez zapisu plików.
- **Translacja:** `transaddress` / `transprivkey` z opcją „dodaj przetłumaczony klucz do portfela”.
- **Vanity:** `multiprocessing`, postęp, przycisk Stop; wynik trafia bezpośrednio do portfela
  (bez wypisywania WIF i bez zapisu QR klucza na dysk).
