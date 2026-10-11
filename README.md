# README

[![Coverage Status](https://coveralls.io/repos/github/tompin/multicrypto/badge.svg?branch=master)](https://coveralls.io/github/tompin/multicrypto?branch=master)
[![Latest Version](https://img.shields.io/pypi/v/multicrypto.svg)](https://pypi.python.org/pypi/multicrypto/)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Highly experimental, pure python tool for cryptocurrencies.
Please notice that coins could change their protocols so make sure the coin parameters are not outdated.

## INSTALLATION

Python 3.8 or newer is required. If you don't have it, install it by following instructions from
python.org. Then run (using pip for Python 3):
```bash
pip install multicrypto
```

The package contains below commands:
 1. `sweepaddress` - combines many inputs into one
 2. `sendcrypto` - creates raw transaction and send it to block explorer api (Insight or Esplora)
 3. `checkaddress` - checks address balance using block explorer api (Insight or Esplora)
 4. `transaddress` - translates address to different coin format (resulting address will have the same private key) 
 5. `transprivkey` - translates WIF private key to different coin format
 6. `genaddress` - generates vanity address for given coin
 7. `signmessage`- signs message using ECDSA
 8. `verifymessage` - verifies ECDSA signed message

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
be difficult to cope with. Let say for Horizen we have private key of the address which inputs 
we want to combine, but we want only combine inputs which are smaller than 0.1 ZEN:
```bash
sweepaddress -c ZEN -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp --maximum_input_threshold=10000000
```
This will create appropriate number of transactions (by default one transaction for each 50 inputs, you can
override this value by setting parameter --batch_size, but setting it too high will result in too big transaction error),
transaction fee will be set to default 10000 satoshis (0.0001 ZEN) per transaction (you can override it using
--fee parameter) and the funds will be sent back to original address (you can override the output address
using --address parameter). Inputs can be also filtered with --minimum_input_threshold.
2. Sending funds:
```bash
sendcrypto --coin_symbol=<COIN_SYMBOL> --satoshis=<INT> --address=<ADDRESS> --wif_private_keys=<PRIVATE KEYS> --fee=<INT> --minimum_input_threshold=<INT> --maximum_input_threshold=<INT> --limit_inputs=<INT>
```
Funds can be sent from many addresses at once by providing comma separated private keys. The default fee
is 10000 satoshis, `--limit_inputs` (`-l`) limits the number of inputs used in the transaction and the change
is sent back to the address of the last used input.
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
nested segwit (`p2sh-p2wpkh`, `3...`) or native segwit (`p2wpkh`, `bc1q...`) address of the private key
(default is `p2pkh`, the change is sent back to the same address). This is also available in `sweepaddress`.
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
4. Translating address between coins:
```bash
transaddress --address=<ADDRESS> --input_symbol=<COIN SYMBOL> --output_symbol=<COIN SYMBOL> --file=<OUTPUT FILE> --output_dir=<DIRECTORY TO STORE QR CODE>
```
Add `--script` (`-s`) when translating P2SH address.
For example to translate Bitcoin address 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG to Zcash address we enter:
```bash
transaddress -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -i BTC -o ZEC
```
5. Translating private key in wif format between coins
```bash
transprivkey --private_key=<PRIVATE_KEY> --output_symbol=<COIN SYMBOL> --file=<OUTPUT FILE> --output_dir=<DIRECTORY TO STORE QR CODE>
```
Without `--output_symbol` the integer value of the private key is returned, with `--integer` (`-i`)
the private key is given as integer instead of WIF.
For example to translate Bitcoin private key KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp
to Zcash private key we enter:
```bash
transprivkey -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp -o ZEC
```
6. Generating address with given pattern and corresponding private key:
```bash
genaddress --pattern=<PATTERN> --symbol=<COIN SYMBOL> --cores=<INT> --output_dir=<DIRECTORY TO STORE QR CODES>
```
Search can be run on many cores with `--cores` (`-c`, default 1). Other options: `--segwit` (`-w`) generates
nested segwit (P2SH-P2WPKH) address, `--uncompressed` (`-u`) uses uncompressed private key and
`--input_script` (`-i`) generates P2SH address for given script.
For example if we want to create address with prefix t1aaaa for Zcash coin and save corresponding
QR codes to /home/john directory we enter:
```bash
genaddress -p t1aaaa -s ZEC -d /home/john
```
To generate Bitcoin segwit address starting with 3BTC we enter:
```bash
genaddress -p 3BTC -s BTC -w
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

8. Verifying if signed message was created using private key of given address:
```bash
verifymessage --coin_symbol=<COIN SYMBOL> --address=<ADDRESS> --message=<MESSAGE> --signed_message=<SIGNED MESSAGE>
```
For example verifying if `H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=`
is signed `Hello World!` message by owner of BTC address 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi we run:
```bash
verifymessage -c BTC -a 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi -m "Hello World!" -s H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=
```

### Supported coins
| Coin | Symbol | Address generation | P2PKH transactions | P2SH transactions | Segwit transactions |
| --- | --- | --- | --- | --- | --- |
| Bitcoin | BTC | Yes | Yes | Yes | Yes |
| Bitcoin Gold | BTG | Yes | Yes | Yes | No |
| Bitcoin Hush | BTCH | Yes | Yes | Yes | No |
| BitcoinZ | BTCZ | Yes | Yes | Yes | No |
| Dash | DASH | Yes | Yes | Yes | No |
| Dogecoin | DOGE | Yes | No | No | No |
| Litecoin | LTC | Yes | Yes | Yes | Yes |
| Safecoin | SAFE | Yes | Yes | Yes | No |
| TENT | TENT | Yes | Yes | Yes | No |
| Smartcash | SMART | Yes | No | No | No |
| Zcash | ZEC | Yes | Yes | Yes | No |
| Zclassic | ZCL | Yes | No | No | No |
| Zeitcoin | ZEIT | Yes | No | No | No |
| Horizen | ZEN | Yes | Yes | Yes | No |
| Zero | ZERO | Yes | Yes | Yes | No |
| Bitcoin testnet | TBTC | Yes | Yes | Yes | Yes |
| Bitcoin Cash testnet | TBCH | Yes | Yes | Yes | No |
| Litecoin testnet | TLTC | Yes | Yes | Yes | Yes |

Transactions require a block explorer API, coins without it support only address generation and translation.
Segwit spending is supported from P2SH-P2WPKH and P2WPKH addresses, spending from taproot (P2TR) and
P2WSH addresses is not supported (sending to them works).

### Peer-to-peer network
Module `multicrypto.network` connects directly to nodes of the coin network (without block explorer),
fetches addresses of their peers and broadcasts raw transactions. It is available for coins with
`network` definition: BTC, BTG, DASH, DOGE, LTC, TBTC, TLTC, ZEC, ZEN.
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
uv run checkaddress -c ZEC -a t1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt
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
uv run --isolated --python 3.8 python -m pytest
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
uv add requests                    # add runtime dependency
uv add --dev pytest-mock           # add development dependency
uv remove requests                 # remove dependency
uv lock --upgrade-package requests # upgrade single locked package
```
Always commit `pyproject.toml` together with the updated `uv.lock`.

## Adding new coin
1. Add new entry in `multicrypto/coins.py`. Prefix bytes are usually defined in chainparams.cpp or
base58.h files.

Exemplary for Horizen we have:
```python
'ZEN': {
    'name': 'horizen',
    'address_prefix_bytes': b'\x20\x89',
    'secret_prefix_bytes': b'\x80',
    'script_prefix_bytes': b'\x1c\xbd',
    'params': {'check_block_at_height': True},
    'apis': [
        {'url': 'https://explorer.zensystem.io/insight-api-zen'}
    ]
}
```
Optional `address_types` lists address types which can be derived from a private key and spent
(only `p2pkh` by default). Segwit coins define also `bech32_hrp` (human readable part of bech32 addresses
from chainparams.cpp), for Bitcoin:
```python
'bech32_hrp': 'bc',
'address_types': (P2PKH, P2SH_P2WPKH, P2WPKH),
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
    'magic': b'\x63\x61\x73\x68',
    'port': 9033,
    'protocol_version': 170002,
    'seeds': ['dnsseed.horizen.global', 'dnsseed.zensystem.io'],
}
```
2. Update this readme with new supported coin and add appropriate tests
3. Create pull request
