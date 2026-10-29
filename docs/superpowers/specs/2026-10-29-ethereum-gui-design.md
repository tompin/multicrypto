# Ethereum in the GUI - stage 2

## Goal

Support Ethereum (ETH) and Sepolia testnet (TETH) in the GUI: HD wallet with MetaMask compatible
addresses, balances, sending, discovery of used addresses, message signing, vanity addresses and
translation of private keys. The library and the CLI support them since stage 1
(`2026-10-29-ethereum-design.md`).

## Decisions

- `ethereum_coins` stays separate from `coins`. A thin layer of helpers and branches in the tabs
  (like in the CLI) keeps the code of coins with unspent outputs almost unchanged.
- New and restored wallets get the account groups Ethereum #0 and TETH #0. Existing wallets are
  not migrated, the group is added with *New account group* or found by the scan.
- Sending ETH uses the existing Send tab, its form changes with the coin.
- One spec, implemented in four phases, each ending with passing tests and a commit on the branch
  `ethereum-gui`.

## Data model and helpers

`coins.py`:

- `ETHEREUM = 'ethereum'` - pseudo address type of Ethereum coins.
- `get_any_coin(symbol)` returns the definition from `coins` or `ethereum_coins` (ValueError for
  unknown symbols), `is_ethereum(symbol)`.
- `get_address_types()` returns `(ETHEREUM,)` for Ethereum coins.

`wallet.py`:

- `PURPOSES[ETHEREUM] = 44`: account n of ETH has path `m/44'/60'/n'` and addresses
  `m/44'/60'/n'/0/i`. Group #0 has the addresses of MetaMask (index i), group #n is account n of
  Ledger Live (index 0). TETH uses coin type 60 too, like other Ethereum wallets.
- Ethereum groups have one account (address type `ETHEREUM`) and only the receiving chain (0),
  there are no change addresses.
- `get_coin()` and `group_address_types()` accept Ethereum coins, `address_at()` calculates
  the address with `ethereum.private_key_to_address` (EIP-55 checksum).
- `ImportedKey.wif` keeps the private key in the export format of the coin: WIF for coins with
  unspent outputs, `0x` and 64 hex digits for Ethereum. The file format and its version don't
  change. `Wallet.add_ethereum_key(label, coin_symbol, hex_key)` validates the key with
  `ethereum.parse_private_key`, rejects present keys and stores the key formatted by
  `format_private_key`. `ImportedKey.address` handles both formats.
- `Wallet.private_key(address) -> int` returns the private key of any address,
  `private_key_wif()` stays for coins with unspent outputs, `exported_private_key(address)`
  returns WIF or hex for showing.
- `add_default_groups()` adds also ETH #0 and TETH #0.

`gui/forms.py`:

- `is_testnet`, `coins_with_slip44`, `coins_with_api` (for Ethereum: coins with `rpcs`) include
  Ethereum coins, so hiding testnets works for TETH.
- `format_coin_amount(symbol, units)` formats satoshis (8 decimal places) or wei (up to 18,
  without trailing zeros); `address_type_name(ETHEREUM)` is `Ethereum`.
- `fetch_balances` gets the balance of Ethereum addresses in wei from `eth_getBalance` (public
  nodes of the coin), errors are shown in the cell like for unspent outputs.

## Wallet tab

- The group Ethereum #0 shows one account named Ethereum with addresses `Address i` and paths
  `m/44'/60'/0'/0/i`.
- Balances and sums use `format_coin_amount`.
- *New address...* and *Receive...* work unchanged, the QR code contains the address with
  the checksum.
- *Import private key* asks for the hex key for ETH and TETH, hides the address type and shows
  the preview of the address.
- *Show key...* shows the hex key labelled `Private key (hex)`.
- Context menu of Ethereum addresses: *Check balance* instead of *Check UTXO*, no *Sweep*
  (replaced by *Max* in Send), *Sign message* and *Translate to another coin...* enabled.
- *Scan for used addresses* in the menus of Ethereum groups and accounts.

## Balance tab

For Ethereum coins the thresholds and the table of unspent outputs are hidden. The tab shows
the balance in ETH and wei, the nonce (sent transactions) and the number of all transactions
from Blockscout, using `check_ethereum_address` of `checkaddress`. When the explorer fails,
the number of transactions is shown as not available.

## Send tab

The form changes when an Ethereum coin is selected:

- Sources: one address (single selection), the fields of unspent outputs (fee rate, input
  thresholds, peer-to-peer) are hidden.
- Destination: validated while typing (`ethereum.validate_address`, checksum errors shown).
- Amount in ETH (`parse_ether`). *Max* requires the destination: in the worker it estimates gas
  with a non-zero value (creating an account costs more gas) and fees, and fills balance minus
  gas limit times max fee per gas. The note under the field says that the unused part of the
  max fee stays on the address.
- Fees: *Priority fee* and *Max fee* in gwei, empty means automatic (suggestion from
  `eth_feeHistory` when the transaction is prepared). *Suggest* fills the current suggestion.
  Nonce and gas limit are automatic.
- Nodes: optional JSON-RPC URLs of own nodes (the field of peer-to-peer nodes), empty means
  the public nodes of the coin.
- *Prepare transaction* runs `prepare_transfer` in the worker, the confirmation shows From, To,
  Value, Nonce, Gas limit, Max fee per gas, Priority fee per gas, Max fee, the balance after
  the transaction (at least) and the warnings of `fee_warnings()` in red. *Send* runs
  `broadcast_transaction` and shows the transaction hash.

Waiting for the receipt is not shown in the GUI, balances are refreshed with *Refresh balances*.

## Discovery

- `BlockscoutAPI.get_usage(address) -> int` returns the number of transactions from the first
  page of `/addresses/{address}/transactions` plus 1 when `/addresses/{address}` has
  `coin_balance` above 0, `has_token_transfers` or `has_tokens`. It finds addresses which
  received ether only by internal transactions (contracts, multisigs, some exchanges) or only
  tokens. HTTP 404 (address unknown to the explorer) means unused.
- `discovery` uses `get_usage` as the transaction count of Ethereum coins and scans only
  the receiving chain of their accounts. The gap limit, the account discovery from #0, pacing and
  retrying after rate limits (Blockscout returns HTTP 429, `RateLimitError`) are unchanged.
- ETH and TETH are in the scan dialog (TETH only with shown testnets), in the menus and in
  the background scan after restoring a wallet. Results are added with `add_discovered`.
- When Blockscout fails, the scan fails like it does when the API of a coin with unspent
  outputs fails. Nodes alone are not enough, the nonce does not count received transactions.

## Sign tab

- ETH and TETH are in the coin lists. Messages are signed with `ethereum.sign_message`
  (EIP-191, like `personal_sign` of MetaMask), the signature is 65 bytes in hex.
- Verification uses `ethereum.verify_message`, an address starting with `0x` selects ETH unless
  TETH is selected.

## Vanity tab

ETH and TETH are in the coin list, the address type box shows Ethereum and is disabled, the hint
and the expected attempts (16^n) come from `vanity`. The result shows the address with
the checksum and the hex private key, *Add to wallet* imports it with `add_ethereum_key`.

## Translate tab

- Address translation does not list Ethereum coins: an Ethereum address cannot be calculated
  from the address of another coin.
- Private key translation lists Ethereum coins as output: WIF or integer gives the hex key and
  the Ethereum address. A hex key with *Integer* gives WIF of any coin. *Add to wallet* and
  *Translate to another coin...* of the Wallet tab work in both directions.

## Error handling

Network operations run in `app.worker` and their errors are shown with `show_error`, like for
coins with unspent outputs. `RpcError`, `NodeUnavailableError` and `InsufficientFundsError`
have readable messages.

## Testing

- Wallet: addresses of ETH #0 match MetaMask (`abandon ... about` gives
  `0x9858EfFD232B4033E47d90003D41EC34EcaEda94`), import and export of hex keys, JSON round trip,
  default groups, rejected keys.
- Discovery: fake usage function (only chain 0, accounts after #0), `get_usage` with
  `http_mock` including HTTP 404.
- GUI (offscreen): every changed tab with ETH and fake node responses, following the existing
  GUI tests.
- Live: a test wallet with the TETH keys from `testnet_wallet.json` - import, balances, sending
  from the GUI on Sepolia and the scan.

## Phases

1. Data model and helpers, Wallet tab (tree, balances, Receive, import and export of keys).
2. Balance and Send tabs.
3. Discovery.
4. Sign, Vanity and Translate tabs, README, live test.
