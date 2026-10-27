# GUI etap 4b: skan konta na żądanie i skan w tle po odtworzeniu — projekt

Data: 2026-10-28. Uzupełnia `2026-10-27-gui-stage4-design.md`.

## Cel

Pełny skan monety (wszystkie typy adresów i konta BIP-44) to 160–330 zapytań do publicznych API,
czyli 1,5–2 minuty przy tempie ok. 4 zapytań/s. Potrzebny jest szybki skan jednego konta oraz
skan po odtworzeniu mnemonika, który nie blokuje okna.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Skan konta | menu kontekstowe konta w zakładce Wallet → *Scan for used addresses*; łańcuch odbioru i reszty tego konta (gap limit 20), ok. 40 zapytań |
| Skan po odtworzeniu | pełny skan BTC w tle zamiast okna modalnego |
| Wynik skanu w tle | dodawany automatycznie (`add_discovered`), komunikat w pasku stanu |
| Postęp | pasek stanu: „Scanning <co>: checked N addresses” i przycisk *Cancel* |
| Równoległe skany | najwyżej jeden skan w tle; kolejny → komunikat „A scan is already running” |
| Blokada | trwający skan odnawia `last_activity`; *Lock* i zamknięcie okna przerywają skan, wynik odrzucony |
| Błąd API | okno z błędem; wyniki znalezione przed błędem są dodawane (ponowny skan pomija duplikaty) |
| File → *Scan for used addresses...* | bez zmian (okno z wyborem monet) |

## Biblioteka (`multicrypto/discovery.py`)

- `scan_account(wallet, account, progress, cancelled, tx_count=None) -> DiscoveredAccount` —
  skan obu łańcuchów konta, z tym samym tempem, rozkładaniem na API i ponawianiem co `discover`.
- Wspólna funkcja wewnętrzna `_scan_account(...)` używana przez `scan_account` i `discover`;
  `_scannable_coin(coin_symbol)` z dotychczasowym błędem dla monet bez SLIP-44 / API.
- `discover(..., tx_count=None, found=None)` — gdy podana lista `found`, znalezione konta są do
  niej dopisywane na bieżąco (wyniki częściowe przy błędzie); funkcja zwraca tę listę.

## GUI

- `gui/background_scan.py`: `BackgroundScan(app)` — etykieta i przycisk *Cancel* w pasku stanu
  (`addPermanentWidget`), `start(title, job)` gdzie `job(progress, cancelled, found)`,
  `start_account(account)`, `start_coin(coin_symbol)`, `cancel()`, `running`. Zadanie w `Worker`,
  timer 300 ms pokazuje postęp i odnawia `app.last_activity`. Koniec → `modify_wallet(add_discovered)`
  i „Scan of <co> finished: added N addresses”; przerwanie → „Scan of <co> cancelled”; błąd →
  dodanie częściowych wyników i `QMessageBox.warning`.
- `MainWindow`: `self.background_scan = BackgroundScan(self)`; `_created(..., restored=True)` →
  `self.background_scan.start_coin('BTC')`.
- `WalletTab._show_menu`: dla konta (monety z API) pozycja *Scan for used addresses* →
  `app.background_scan.start_account(account)`.

## Testy

- `tests/test_discovery.py`: `scan_account` (odbiór i reszta, fałszywe `tx_count`), `discover`
  z listą `found` (wyniki częściowe przed błędem).
- `tests/test_gui.py`: `BackgroundScan` z fałszywym zadaniem — automatyczne dodanie, *Cancel*,
  blokada przerywa i odrzuca wynik, błąd z częściowymi wynikami, drugi skan odrzucony, odnawianie
  `last_activity`; menu konta uruchamia skan konta; odtworzenie uruchamia `start_coin('BTC')`.
