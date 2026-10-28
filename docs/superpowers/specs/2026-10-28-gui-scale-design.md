# GUI: skalowanie interfejsu — projekt

Data: 2026-10-28.

## Cel

Na monitorach o dużej rozdzielczości interfejs `multicrypto-gui` bywa za mały: Qt 6 skaluje
automatycznie tylko wtedy, gdy system zgłasza współczynnik DPI (na Linuksie z X11 często go nie
zgłasza). Użytkownik ma móc ustawić skalę całego interfejsu i zachować ją między uruchomieniami.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Mechanizm | zmienna `QT_SCALE_FACTOR` ustawiana przed utworzeniem `QApplication`; skaluje równo czcionki, okna, sztywne rozmiary w pikselach i kody QR |
| Menu | *View → Scale*: *Auto (system)*, 100%, 125%, 150%, 175%, 200%, 250%, 300%; zaznaczona wartość, z którą działa aplikacja po zapisie (zapisana w pliku) |
| Zapis | `~/.multicrypto/gui.json`, np. `{"scale": 1.5}`; *Auto* usuwa klucz `scale` |
| Zastosowanie zmiany | po ponownym uruchomieniu; po wyborze komunikat „The scale will be applied after restarting the application.” |
| Linia poleceń | `--scale <liczba>` (0.5–4) nadpisuje zapisaną wartość, nie jest zapisywana |
| Priorytet | `--scale` > zapisana wartość > *Auto* |
| *Auto* | zmienna nie jest ustawiana — działa skalowanie systemowe i ewentualne `QT_SCALE_FACTOR` ustawione przez użytkownika |
| Błędny plik | brak pliku, niepoprawny JSON lub wartość spoza 0.5–4 → *Auto* (bez błędu) |

## Moduł `multicrypto/gui/settings.py`

Bez zależności od PySide6 (używany przed utworzeniem `QApplication`).

- `SETTINGS_PATH = ~/.multicrypto/gui.json`, `MIN_SCALE = 0.5`, `MAX_SCALE = 4`.
- `load_scale(path) -> Optional[float]` — zapisana skala albo `None` (*Auto*) przy braku pliku,
  błędnym JSON lub wartości spoza zakresu.
- `save_scale(path, scale: Optional[float])` — zapisuje skalę (`None` usuwa klucz), zachowuje
  pozostałe klucze pliku, tworzy katalog z prawami `0o700`.
- `initial_scale(cli_scale: Optional[float], path) -> Optional[float]` — `cli_scale`, a gdy
  `None`, to `load_scale(path)` (priorytet z tabeli).
- `apply_scale(scale: Optional[float])` — gdy skala podana, ustawia
  `os.environ['QT_SCALE_FACTOR']`; dla `None` nic nie zmienia.

## `multicrypto/gui/app.py`

- Opcja `--scale` (typ: liczba w zakresie 0.5–4, walidowana w argparse).
- Przed `QApplication`: `apply_scale(initial_scale(args.scale, SETTINGS_PATH))`.

## `multicrypto/gui/window.py`

- `MainWindow(wallet_file, auto_lock_seconds, settings_path=SETTINGS_PATH)`.
- Menu *View → Scale* z `QActionGroup` (akcje wzajemnie wykluczające się); zaznaczenie wg
  `load_scale(settings_path)`. Wybór → `save_scale(...)` i komunikat o restarcie.

## Dokumentacja

README: opcja `--scale` w przykładzie uruchomienia GUI i zdanie o menu *View → Scale*.

## Testy

- `tests/test_gui_settings.py`: zapis i odczyt, *Auto* usuwa klucz, inne klucze zachowane,
  brak pliku / błędny JSON / wartość spoza zakresu → `None`; `apply_scale` ustawia zmienną,
  `None` jej nie zmienia (z `monkeypatch.setenv`/`delenv`); `initial_scale` — wartość z linii
  poleceń wygrywa z zapisaną, bez niej zapisana.
- `tests/test_gui.py`: menu zaznacza zapisaną skalę; wybór 150% zapisuje 1.5 w pliku i pokazuje
  komunikat; wybór *Auto* usuwa wartość.
- Opcja `--scale`: walidacja zakresu w `get_args`.
