# GUI: wybór adresu portfela i nowy adres z typem — projekt

Data: 2026-10-29.

## Cel

Przy 18 adresach w 6 monetach (grupy kont) listy adresów portfela w zakładkach są długie i
nieczytelne: pokazują wszystkie monety, a jeden wiersz łączy etykietę, monetę, typ, ścieżkę i
adres. „New address...” nie pozwala wybrać typu adresu.

## Decyzje

| Temat | Decyzja |
|-------|---------|
| Moneta | pole **Coin** na górze zakładek Balance, Sweep, Send i Sign; filtruje adresy portfela |
| Balance | Coin dotyczy adresu portfela i adresu wpisanego ręcznie (monety z API) |
| Sweep | Coin dotyczy adresu portfela i klucza zewnętrznego; adresy docelowe portfela tej monety |
| Send | Coin (monety z API) i tabela źródeł z kolumnami Address, Account, Address type, Path, Label |
| Sign | Coin (wszystkie monety); adresy taproot nie są na liście (BIP-137 ich nie obsługuje) |
| Lista adresów | sam adres; pod nią szczegóły: Account, Address type, Path, Label |
| Account | etykieta grupy (`Bitcoin #0`) albo `Imported key` |
| Address type | `Native SegWit (p2wpkh)` itd. |
| Path | ścieżka adresu albo `—` dla klucza importowanego |
| Akcje z menu adresu | Check UTXO, Send from, Sweep, Sign ustawiają monetę adresu i go zaznaczają |
| New address... | okno: Account (grupa), Address type (typy grupy), Label, podgląd Path i Address |
| Domyślne w New address | zaznaczona grupa → Native SegWit (jeśli jest, inaczej pierwszy typ); typ lub adres → ten typ; brak zaznaczenia → pierwsza grupa |

## Komponenty

- `multicrypto/gui/forms.py`: `ADDRESS_TYPE_NAMES` (przeniesione z `wallet_tab.py`),
  `address_type_name(address_type)` → `Native SegWit (p2wpkh)`, `address_details(wallet,
  address) -> List[Tuple[str, str]]` (Account, Address type, Path, Label).
- `multicrypto/wallet.py`: `Wallet.next_receiving_address(account_id)` — podgląd następnego
  adresu odbiorczego bez dodawania (jak `next_change_address`).
- `multicrypto/gui/address_picker.py`: `WalletAddressPicker(QWidget)` — `QComboBox` z adresami
  (tekst = adres, dane = id) i etykiety szczegółów pod nią; `set_addresses(wallet, addresses)`
  (zachowuje zaznaczenie po id), `current() -> Optional[WalletAddress]`, `select(address_id) ->
  bool`, `clear()`, sygnał `changed`, dostęp do listy `box` (sygnał `activated` dla zakładek).
- `multicrypto/gui/wallet_tab.py`: `NewAddressDialog` zamiast `QInputDialog`.
- Zakładki: `balance_tab.py`, `sweep_tab.py`, `send_tab.py`, `sign_tab.py`.

## Testy

- `forms`: `address_details` dla adresu HD i klucza importowanego.
- `wallet`: `next_receiving_address` nie dodaje adresu.
- GUI: filtr monety w każdej zakładce; picker pokazuje sam adres i szczegóły; akcje z menu
  ustawiają monetę; Sign bez taproota; tabela źródeł Send; `NewAddressDialog` (domyślny typ z
  zaznaczenia, podgląd, dodanie adresu).
