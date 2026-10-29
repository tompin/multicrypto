# README

[![Coverage Status](https://coveralls.io/repos/github/tompin/multicrypto/badge.svg?branch=master)](https://coveralls.io/github/tompin/multicrypto?branch=master)
[![Latest Version](https://img.shields.io/pypi/v/multicrypto.svg)](https://pypi.python.org/pypi/multicrypto/)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Highly experimental, pure python tool for cryptocurrencies.
Please notice that coins could change their protocols so make sure the coin parameters are not outdated.

## INSTALLATION

Python 3.10 or newer is required. If you don't have it, install it by following instructions from
python.org. Then run (using pip for Python 3):
```bash
pip install multicrypto
```

The package contains below commands:
 1. `sweepaddress` - combines many inputs into one
 2. `sendcrypto` - creates raw transaction and send it to block explorer api (Insight or Esplora)
 3. `checkaddress` - checks address balance using block explorer api (Insight or Esplora), for Ethereum
    using JSON-RPC of nodes
 4. `transaddress` - translates address to different coin format (resulting address will have the same private key) 
 5. `transprivkey` - translates WIF private key to different coin format
 6. `genaddress` - generates vanity address for given coin (also Ethereum)
 7. `signmessage`- signs message using ECDSA
 8. `verifymessage` - verifies ECDSA signed message
 9. `multicrypto-gui` - graphical user interface with HD wallet (BIP-39 mnemonic with optional passphrase)
 10. `sendeth` - creates EIP-1559 transaction sending ether and sends it to Ethereum node (JSON-RPC)

The GUI requires optional dependencies PyNaCl and PySide6:
```bash
pip install "multicrypto[gui]"
```

## USAGE
Before running any commands it is advised to disable shell history. For example on linux it should 
be enough to run:
```bash
unset HISTFILE
```
### Run
1. Combining many small inputs to larger ones.
```bash
sweepaddress --coin_symbol=<COIN SYMBOL> --address=<ADDRESS> --wif_private_key=<PRIVATE KEY> --minimum_input_threshold=<INT> --maximum_input_threshold=<INT>
```
After mining some currency for longer period we could end up with address having a lot of small inputs. 
In such case it is very likely it will be not possible to send the funds in one transaction and it could 
be difficult to cope with. Let say for Dash we have private key of the address which inputs 
we want to combine, but we want only combine inputs which are smaller than 0.1 DASH:
```bash
sweepaddress -c DASH -p XBHdfdHC4YocfzyfuFRx3DxjmvFJmK3txDh3zXk29GxpMWaWfDKL --maximum_input_threshold=10000000
```
This will create appropriate number of transactions (by default one transaction for each 50 inputs, you can
override this value by setting parameter --batch_size, but setting it too high will result in too big transaction error),
transaction fee will be set to default 10000 satoshis (0.0001 DASH) per transaction (you can override it using
--fee parameter, or use --fee_rate (`-r`) to pay the given number of satoshis per virtual byte of each
transaction) and the funds will be sent back to original address (you can override the output address
using --address parameter). Inputs can be also filtered with --minimum_input_threshold.
2. Sending funds:
```bash
sendcrypto --coin_symbol=<COIN_SYMBOL> --satoshis=<INT> --address=<ADDRESS> --wif_private_keys=<PRIVATE KEYS> --fee=<INT> --minimum_input_threshold=<INT> --maximum_input_threshold=<INT> --limit_inputs=<INT>
```
Funds can be sent from many addresses at once by providing comma separated private keys. The default fee
is 10000 satoshis, `--limit_inputs` (`-l`) limits the number of inputs used in the transaction and the change
is sent back to the address of the last used input. Instead of the fixed fee, `--fee_rate` (`-r`) pays the
given number of satoshis per virtual byte, the fee is calculated from the size of the transaction.
Sending (P2PKH) 0.25 BTC to address 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG with default fee 10000 satoshis
and only using inputs containing not more than 100000 satoshis:
```bash
sendcrypto -c BTC -s 25000000 -x 100000 -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp
```
Sending (P2SH) 0.0019 BTC on testnet to address 2NDN55zZ6BtStckQWnhGJejBdM5EaGcNn7h with fee 5000 satoshis
(notice that both input address 2NAMu8JCTLXtTv2LRQktByt1EoKaJaVmDAj and unlocking script 5106519351935387
must be provided):
```bash
sendcrypto -a 2NDN55zZ6BtStckQWnhGJejBdM5EaGcNn7h -c TBTC -i 2NAMu8JCTLXtTv2LRQktByt1EoKaJaVmDAj -u 5106519351935387 -s 190000 -f 5000
```
Segwit is supported for BTC, LTC and their testnets (TBTC, TLTC). Funds can be sent to bech32 addresses
(native segwit `bc1q...` and taproot `bc1p...`), and with `--address_type` (`-t`) to spend funds from the
nested segwit (`p2sh-p2wpkh`, `3...`), native segwit (`p2wpkh`, `bc1q...`) or taproot (`p2tr`, `bc1p...`)
address of the private key (default is `p2pkh`, the change is sent back to the same address). Taproot address
is derived from the private key according to BIP-86 (key path only, without script tree) and inputs are signed
with Schnorr signatures (BIP-340). This is also available in `sweepaddress`.
Sending 0.25 BTC from the native segwit address of the private key to bech32 address:
```bash
sendcrypto -c BTC -s 25000000 -a bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4 -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp -t p2wpkh
```
By default the transaction is sent to the block explorer API. Adding `--p2p` sends it directly to a node
of the coin peer-to-peer network found using DNS seeds (inputs are still fetched from the API). Particular
nodes can be selected with `--node <HOST>[:<PORT>]` (can be repeated, nodes are tried in order):
```bash
sendcrypto -c BTC -s 25000000 -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp --p2p
sendcrypto -c BTC -s 25000000 -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp --node 203.0.113.5:8333
```
3. Listing address inputs with total amount:
```bash
checkaddress --coin_symbol=<COIN SYMBOL> --address=<ADDRESS> --minimum_input_threshold=<INT> --maximum_input_threshold=<INT> --limit_inputs=<INT>
```
For example:
```bash
checkaddress -c BTC -a 14YK4mzJGo5NKkNnmVJeuEAQftLt795Gec
```
For Ethereum (`ETH`, Sepolia testnet `TETH`) the balance, the nonce (number of sent transactions)
and the number of all transactions (from Blockscout explorer) are shown. Public nodes are used by
default, own node is given with `--node` (can be repeated):
```bash
checkaddress -c ETH -a 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
checkaddress -c ETH -a 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 --node http://localhost:8545
```
4. Translating address between coins:
```bash
transaddress --address=<ADDRESS> --input_symbol=<COIN SYMBOL> --output_symbol=<COIN SYMBOL> --file=<OUTPUT FILE> --output_dir=<DIRECTORY TO STORE QR CODE>
```
Add `--script` (`-s`) when translating P2SH address.
For example to translate Bitcoin address 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG to Dogecoin address we enter:
```bash
transaddress -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -i BTC -o DOGE
```
5. Translating private key in wif format between coins
```bash
transprivkey --private_key=<PRIVATE_KEY> --output_symbol=<COIN SYMBOL> --file=<OUTPUT FILE> --output_dir=<DIRECTORY TO STORE QR CODE>
```
Without `--output_symbol` the integer value of the private key is returned, with `--integer` (`-i`)
the private key is given as integer instead of WIF.
For example to translate Bitcoin private key KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp
to Dogecoin private key we enter:
```bash
transprivkey -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp -o DOGE
```
The same private key gives Ethereum address, `-o ETH` returns the private key in hex format
(Ethereum private keys are translated to other coins as integers with `0x` prefix and `-i`):
```bash
transprivkey -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp -o ETH
transprivkey -p 0x0000000000000000000000000000000000000000000000000000000000000001 -i -o BTC
```
6. Generating address with given pattern and corresponding private key:
```bash
genaddress --pattern=<PATTERN> --symbol=<COIN SYMBOL> --cores=<INT> --output_dir=<DIRECTORY TO STORE QR CODES>
```
Search can be run on many cores with `--cores` (`-c`, default 1). Other options: `--segwit` (`-w`) generates
nested segwit (P2SH-P2WPKH) address, `--uncompressed` (`-u`) uses uncompressed private key and
`--input_script` (`-i`) generates P2SH address for given script.
For example if we want to create address with prefix DDoge for Dogecoin and save corresponding
QR codes to /home/john directory we enter:
```bash
genaddress -p DDoge -s DOGE -d /home/john
```
To generate Bitcoin segwit address starting with 3BTC we enter:
```bash
genaddress -p 3BTC -s BTC -w
```
Native segwit (bech32) vanity addresses are generated with `--address_type p2wpkh` (`-t`), the
pattern is the beginning of the address including `bc1q` (bech32 addresses use only the characters
`023456789acdefghjklmnpqrstuvwxyz`):
```bash
genaddress -s BTC -t p2wpkh -p bc1qxyz -c 4
```
Ethereum vanity addresses start with `0x` followed by hexadecimal digits, the pattern is compared
case insensitively and the address is returned with EIP-55 checksum together with the private key
in hex format:
```bash
genaddress -s ETH -p 0xabc -c 4
```
7. Signing message proving ownership of an address:
```bash
signmessage --coin_symbol=<COIN SYMBOL> --wif_private_key=<PRIVATE KEY> --message=<MESSAGE TO SIGN>
```
For example proving ownership of BTC address 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi:
```bash
signmessage -c BTC -p KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu -m "Hello World!"
```
will return: `H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=`

Messages of segwit addresses are signed according to BIP-137 (like Electrum, Sparrow and Trezor),
the type of the address is selected with `--address_type` (`p2pkh` by default, `p2sh-p2wpkh` or
`p2wpkh`; taproot addresses are not supported):
```bash
signmessage -c BTC -p <PRIVATE KEY> -t p2wpkh -m "Hello World!"
```
`verifymessage` accepts signatures of all these address types, also segwit signatures made with
the header of p2pkh address.

Ethereum messages (`-c ETH`, private key in hex format) are signed like `personal_sign` of
MetaMask (EIP-191), the signature is 65 bytes in hex:
```bash
signmessage -c ETH -p 0xb25c7db31feed9122727bf0939dc769a96564b2de4c4726d035b36ecf1e5b364 -m "I♥SF"
verifymessage -c ETH -a 0x5ce9454909639D2D17A3F753ce7d93fa0b9aB12E -m "I♥SF" -s 0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb33e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c
```

8. Verifying if signed message was created using private key of given address:
```bash
verifymessage --coin_symbol=<COIN SYMBOL> --address=<ADDRESS> --message=<MESSAGE> --signed_message=<SIGNED MESSAGE>
```
For example verifying if `H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=`
is signed `Hello World!` message by owner of BTC address 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi we run:
```bash
verifymessage -c BTC -a 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi -m "Hello World!" -s H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=
```

9. Sending ether (Ethereum and Sepolia testnet `TETH`):
```bash
sendeth --coin_symbol=<ETH OR TETH> --address=<ADDRESS> --value=<ETHER>
```
The private key in hex format is asked without echo (or read from the standard input), so it is
not saved in the shell history, it can be also given with `--private_key` (`-p`). The summary of
the transaction is shown with warnings about probably mistaken fees (max fee per gas lower than
the base fee, more than 10 times the suggested one or max fee higher than the value) and the
transaction is sent after confirmation, `--yes` (`-y`) sends it without asking (required when
the standard input is not a terminal). `--wait` waits until the transaction is mined (at most 300
seconds or the given number of seconds) and shows its status, block and paid fee.
The transaction uses EIP-1559 fees. By default the nonce is the next one of the address, the gas
limit is estimated by the node, the priority fee is the median of the recent blocks and the max fee
per gas is twice the base fee of the next block plus the priority fee, they can be set with
`--nonce`, `--gas_limit`, `--priority_fee` and `--max_fee` (fees in gwei). Only the base fee of
the block is paid (it is burned) together with the priority fee, the rest of the max fee stays on
the address. A pending transaction is replaced by a transaction with its nonce and higher fees.
For example sending 0.01 ether and waiting for confirmation, then sending with the private key
from a file without asking:
```bash
sendeth -c ETH -a 0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed -v 0.01 --wait
sendeth -c ETH -a 0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed -v 0.01 --yes < private_key.txt
```
`--dry_run` prints the signed transaction without sending it, `--node` sends it to own node instead
of the public ones (e.g. `--node http://localhost:8545` for geth, reth or nethermind).

10. Graphical user interface:
```bash
multicrypto-gui --wallet=<WALLET FILE> --auto_lock=<MINUTES> --scale=<SCALE>
```
The wallet is a BIP-39 mnemonic with optional passphrase, keys are derived according to BIP-32
with BIP-44 (p2pkh), BIP-49 (p2sh-p2wpkh), BIP-84 (p2wpkh) and BIP-86 (p2tr) paths and SLIP-44 coin
types, so the addresses can be restored in other wallets (e.g. Electrum, Sparrow). The mnemonic,
accounts, address labels and imported private keys are kept in a single file (by default
`~/.multicrypto/wallet.mcw`) encrypted with XChaCha20-Poly1305 using the key derived from the
password with Argon2id. The passphrase can be left empty, then the mnemonic alone restores the
wallet. When it is set, it works as an additional word of the mnemonic and it is never saved: it is
asked after the password every time the wallet is unlocked, and the fingerprint of the master key
detects a mistyped passphrase. Tabs:
- **Wallet** - account groups (e.g. *Bitcoin #0*) with the accounts of all address types of the
  coin (Taproot, Native SegWit, SegWit, Legacy) and their receiving addresses created on demand
  (New address... asks for the account and the address type and shows the address before adding
  it, Receive... shows the latest address of the account with its QR code), imported private keys (they are not covered by the mnemonic backup), address balances, showing
  private keys and the mnemonic (after entering the password again),
- **Balance** - unspent outputs of the wallet address or any other address (like `checkaddress`),
- **Send** - send funds from one or more wallet addresses (like `sendcrypto`), the transaction is
  shown for confirmation before it is broadcast, the fee rate is entered in sat/vB (Estimate takes it
  from the block explorer), the change of HD accounts goes to the next change address (…/1/i), of
  imported keys back to the source address,
- **Sweep** - send all unspent outputs of the wallet address or of an external private key (e.g.
  a paper wallet, the key is not saved in the wallet) in batches (like `sweepaddress`) to the same
  address, a wallet address or any other address,
- **Sign / Verify** - sign messages with keys of wallet addresses and verify signatures of any
  address (like `signmessage` and `verifymessage`),
- **Translate** - address of the same public key hash for another coin (like `transaddress`) and
  the private key with its addresses for another coin (like `transprivkey`), which can be added
  to the wallet,
- **Vanity** - search for an address starting with the given pattern (like `genaddress`) in many
  processes, the found key can be added to the wallet.

The account groups are collapsed to one row with the balance of the group, the expanded groups are
kept until the wallet is locked. The testnet coins (TBTC, TLTC) are hidden unless *View → Show
testnets* is checked (remembered in `~/.multicrypto/gui.json`), the Translate and Vanity tabs
show all coins.

In the Balance, Send, Sweep and Sign / Verify tabs the coin is selected first, the lists show the
wallet addresses of this coin and the account, address type, path and label of the selected
address (Send shows them in the columns of its table). The actions of the address in the Wallet
tab (Check UTXO, Send from this address, Sweep this address, Sign message) select its coin.

A new or restored wallet has the first account group (#0) of every coin with SLIP-44 coin type
(BTC, LTC, DOGE, DASH and the testnets TBTC, TLTC), each account with its first receiving address.
New account... adds the next group of the coin with the accounts of all its address types. The
accounts of the group are separate BIP-44/49/84/86 accounts with the same number, so they are
restored in other wallets as usual (e.g. the account of each address type in Sparrow or Ledger
Live). TBTC and TLTC share the SLIP-44 coin type of testnets, so their p2pkh and p2sh-p2wpkh
addresses are the same.

The **Wallet** tab shows also the QR code of the address, and "Translate to another coin" adds the
key of a wallet address as an imported key of another coin. Used accounts and addresses are found
on demand: right-click a coin and choose Scan for used addresses (progress in the status bar), or
use File → Scan for used addresses for the selected coins, so the funds received in another wallet
(e.g. Electrum, Sparrow) are shown. The account groups are checked from #0 to the first one without
transactions in all its address types and the addresses until 20 unused ones (gap limit 20); a
group after an unused one is added with New account... (with its number) and scanned from the
context menu of its account. A single account is scanned quickly from its context menu.

On high resolution screens the interface can be enlarged in *View → Scale* (applied after restart
and remembered in `~/.multicrypto/gui.json`) or for one run with `--scale` (e.g. `--scale=1.5`).

The wallet stays unlocked until File → Lock or closing the application. *View → Auto lock* locks
it after 5, 15, 30 or 60 minutes of inactivity (remembered in `~/.multicrypto/gui.json`),
`--auto_lock=<MINUTES>` sets it for one run. Python cannot reliably remove data from memory, so
the keys of the unlocked wallet stay in memory of the process until it is locked. Keep the mnemonic and the passphrase (if set) written down separately - the funds cannot be
recovered without both of them.

### Supported coins
| Coin | Symbol | Address generation | P2PKH transactions | P2SH transactions | Segwit transactions |
| --- | --- | --- | --- | --- | --- |
| Bitcoin | BTC | Yes | Yes | Yes | Yes |
| Dash | DASH | Yes | Yes | Yes | No |
| Dogecoin | DOGE | Yes | No | No | No |
| Litecoin | LTC | Yes | Yes | Yes | Yes |
| Bitcoin testnet | TBTC | Yes | Yes | Yes | Yes |
| Litecoin testnet | TLTC | Yes | Yes | Yes | Yes |

Transactions require a block explorer API, coins without it support only address generation and translation.
Only coins accepting legacy (version 1) transactions with Bitcoin signature hashes are supported. Coins based
on Zcash (e.g. ZEC, BTCZ, ZERO) require Overwinter/Sapling transactions and coins with SIGHASH_FORKID
(e.g. BCH, BTG) require BIP-143 signature hashes, so they are not supported.
Segwit spending is supported from P2SH-P2WPKH, P2WPKH and taproot P2TR (key path) addresses, spending from
P2WSH addresses and taproot script path is not supported (sending to them works).

### Ethereum
| Coin | Symbol | Chain id | Address generation | Transactions |
| --- | --- | --- | --- | --- |
| Ethereum | ETH | 1 | Yes | Yes |
| Ethereum Sepolia testnet | TETH | 11155111 | Yes | Yes |

Ethereum coins are defined in `ethereum_coins` in `multicrypto/coins.py`, separately from the coins
with unspent outputs. Commands `checkaddress`, `genaddress`, `signmessage`, `verifymessage`,
`transprivkey` and `sendeth` support them, the GUI does not support them yet. Transactions sending ether use EIP-1559 (type 2) format, transactions
calling contracts (e.g. tokens) are not supported. Keccak-256 and RLP are implemented in pure Python
(`multicrypto.keccak`, `multicrypto.rlp`), so there are no new dependencies.

Nodes are used through JSON-RPC: requests go to the first public node from `rpcs` which responds
(unavailable and rate limited nodes are skipped), the chain id of the node is checked before signing.
The number of all transactions of an address comes from Blockscout explorer, which does not need
an API key (Etherscan requires it). Direct connection to the peer-to-peer network of Ethereum
(devp2p) is not supported.
```python
from multicrypto.coins import ethereum_coins
from multicrypto.ethereum import parse_ether, parse_private_key
from multicrypto.ethereum_api import broadcast_transaction, get_rpc, prepare_transfer

coin = ethereum_coins['TETH']
rpc = get_rpc(coin)  # or get_rpc(coin, ['http://localhost:8545'])
prepared = prepare_transfer(
    coin, rpc, parse_private_key('<HEX PRIVATE KEY>'), '<ADDRESS>', parse_ether('0.01')
)
print(prepared.transaction, prepared.signed.raw_hex)
transaction_hash = broadcast_transaction(rpc, prepared)
```

### Peer-to-peer network
Module `multicrypto.network` connects directly to nodes of the coin network (without block explorer),
fetches addresses of their peers and broadcasts raw transactions. It is available for coins with
`network` definition: BTC, DASH, DOGE, LTC, TBTC, TLTC.
```python
from multicrypto.coins import coins
from multicrypto.network import Node, discover_nodes

nodes = discover_nodes(coins['BTC'])  # nodes found using DNS seeds
with Node(coins['BTC'], nodes[0].host, nodes[0].port) as node:
    peers = node.get_peers()
    transaction_id = node.send_transaction('<RAW TRANSACTION HEX>')
```

## Development
The project is managed with [uv](https://docs.astral.sh/uv/). Dependencies are pinned in
`uv.lock` and the development Python version in `.python-version`.

### Setup
Install uv (the version used in CI is 0.13.0):
```bash
curl -LsSf https://astral.sh/uv/0.13.0/install.sh | sh
```
Create the virtual environment in `.venv` and install the package with all development
dependencies exactly as locked:
```bash
uv sync --locked
```
uv downloads the required Python version automatically if it is not installed.
Run `uv sync` again after pulling changes that modify `pyproject.toml` or `uv.lock`.

### Running commands
`uv run` executes commands inside the project environment, no activation is needed:
```bash
uv run checkaddress -c BTC -a 14YK4mzJGo5NKkNnmVJeuEAQftLt795Gec
```
If you prefer an activated shell:
```bash
source .venv/bin/activate
```

### Tests
Run tests and check report htmlcov/index.html:
```bash
uv run python -m pytest --cov=./ --cov-report=html
```
Run tests with another supported Python version in a temporary environment
(`.venv` stays untouched):
```bash
uv run --isolated --python 3.10 python -m pytest
```
Run tests in Docker (Python from the base image):
```bash
docker build -t mc .
docker container run mc
```
Run linter and formatter:
```bash
uv run ruff check .
uv run ruff format .
```

### Managing dependencies
```bash
uv add pypng                           # add runtime dependency
uv add --dev pytest-mock               # add development dependency
uv remove pypng                        # remove dependency
uv lock --upgrade-package pyqrcode     # upgrade single locked package
```
Always commit `pyproject.toml` together with the updated `uv.lock`.

## Adding new coin
1. Add new entry in `multicrypto/coins.py`. Prefix bytes are usually defined in chainparams.cpp or
base58.h files.

Exemplary for Dash we have:
```python
'DASH': {
    'name': 'dash',
    'message_prefix': 'DarkCoin',
    'slip44': 5,
    'address_prefix_bytes': b'\x4c',
    'secret_prefix_bytes': b'\xcc',
    'script_prefix_bytes': b'\x10',
    'apis': [{'url': 'https://insight.dash.org/insight-api'}],
}
```
Optional `address_types` lists address types which can be derived from a private key and spent
(only `p2pkh` by default). Segwit coins define also `bech32_hrp` (human readable part of bech32 addresses
from chainparams.cpp), for Bitcoin:
```python
'bech32_hrp': 'bc',
'address_types': (P2PKH, P2SH_P2WPKH, P2WPKH, P2TR),
```
Entries in `apis` use the Insight API by default. Block explorers with the Esplora API (e.g.
mempool.space, blockstream.info) need `'type': 'esplora'`, for Bitcoin:
```python
'apis': [
    {'url': 'https://mempool.space/api', 'type': 'esplora'},
    {'url': 'https://blockstream.info/api', 'type': 'esplora'},
]
```
Optional `network` entry enables `multicrypto.network`. Values come from chainparams.cpp
(`pchMessageStart`, `nDefaultPort`, `vSeeds`) and version.h (`PROTOCOL_VERSION`):
```python
'network': {
    'magic': b'\xbf\x0c\x6b\xbd',
    'port': 9999,
    'protocol_version': 70240,
    'seeds': ['dnsseed.dash.org'],
}
```
2. Update this readme with new supported coin and add appropriate tests
3. Create pull request
