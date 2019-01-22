# README

[![Build Status](https://travis-ci.org/tompin/multicrypto.svg?branch=master)](https://travis-ci.org/tompin/multicrypto)
[![Coverage Status](https://coveralls.io/repos/github/tompin/multicrypto/badge.svg?branch=master)](https://coveralls.io/github/tompin/multicrypto?branch=master)
[![Latest Version](https://pypip.in/version/multicrypto/badge.svg)](https://pypi.python.org/pypi/multicrypto/)
[![Python Version](https://img.shields.io/pypi/pyversions/multicrypto.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Bitcoin donation](https://img.balancebadge.io/btc/1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG.svg?label=Donations&color=ffb121)](https://blockchain.info/address/1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG)
   
Experimental, pure python, tool for sending cryptocurrency, creating custom look addresses, 
translating addresses and private keys between different coins or check address balance.

## INSTALLATION

### Additional packages needed on Ubuntu
```bash
sudo apt-get install build-essential python3-setuptools python3-wheel python3-dev python3-pip
```

If you don't have Python 3, install it by following instructions from python.org. 
Supported Python versions are 3.5, 3.6, 3.7. Then Run:
```bash
pip3 install multicrypto
```

The package contains below commands:
 1. `sweepaddress`
 2. `sendcrypto`
 3. `checkaddress`
 4. `transaddress`
 5. `transprivkey`
 6. `genaddress`
 7. `signmessage`
 8. `verifymessage`

## USAGE
Before running any commands it is advised to disable shell history. For example on linux it should be enough to run:
```bash
unset HISTFILE
```
### Run

 1. Combining many small inputs to larger ones.
 ```bash
 sweepaddress --coin_symbol=<COIN_SYMBOL> --address=<ADDRESS> --private_key=<PRIVATE KEY> --minimum_input_threshold=<INT> --maximum_input_threshold=<INT>
 ```
 After mining some currency for longer period we could end up with address having a lot of small inputs. 
 In such case it is very likely it will be not possible to send the funds in one transaction and it could
  be difficult to cope with. Let say for Zen Cash we have private key of the address which inputs 
  we want to combine, but we want only combine inputs which are smaller than 0.1 ZEN:
  ```bash
 sweepaddress -c ZEN -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp --maximum_input_threshold==10000000
 ```
 This will create appropriate number of transactions (by default one transaction for each 200 inputs, you can 
 override this value by setting parameter --batch_size, but setting it too high will result in too big transaction error),
 transaction fee will be set to default 0.00001 ZEN (you can override it using --fee parameter) and the
 funds will be sent back to original address (you can override the output address using --address parameter).

 2. Sending funds:
 ```bash
 sendcrypto --coin_symbol=<COIN_SYMBOL> --satoshis=<INT> --address=<ADDRESS> --private_key=<PRIVATE KEY> --minimum_input_threshold=<INT> --maximum_input_threshold=<INT>
 ```
 Sending (P2PKH) 0.25 BTC to address 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG with default fee 10000 satoshis
 and only using inputs containing not more than 100000 satoshis:
 ```bash
 sendcrypto -c BTC -s 25000000 -x 100000 -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp
 ```

 Sending (P2PSH) 0.0019 BTC on testnet to address 2NDN55zZ6BtStckQWnhGJejBdM5EaGcNn7h with fee 5000 satoshis
 (notice that both input address 2NAMu8JCTLXtTv2LRQktByt1EoKaJaVmDAj and unlocking script 5106519351935387
 must be provided):
 ```bash
 sendcrypto -a 2NDN55zZ6BtStckQWnhGJejBdM5EaGcNn7h -c TBTC -i 2NAMu8JCTLXtTv2LRQktByt1EoKaJaVmDAj -u 5106519351935387 -s 190000 -f 5000
 ```
 3. Listing address inputs with total amount:
 ```bash
 checkaddress --coin_symbol=<COIN_SYMBOL> --address=<ADDRESS> --minimum_input_threshold=<INT> --maximum_input_threshold=<INT>
 ``` 
 For example:
 ```bash
 checkaddress -c BTC -a 14YK4mzJGo5NKkNnmVJeuEAQftLt795Gec
 ```
 4. Translating address between coins:
  ```bash
  transaddress --address=<ADDRESS> --input_symbol=<COIN SYMBOL> --output_symbol=<COIN SYMBOL>
  ```
  For example to translate Bitcoin address 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG to Hush address we enter:
  ```bash
  transaddress -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -i BTC -o HUSH
  ```
 5. Translating private key in wif format between coins
  ```bash
  transprivkey --private_key=<PRIVATE_KEY> --output_symbol=<COIN SYMBOL>
  ```
  For example to translate Bitcoin private key KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp
   to Hush private key we enter:
  ```bash
  transprivkey -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp -o HUSH
  ```
 6. Generating address with given pattern and corresponding private key:
  ```bash
 genaddress --pattern=<PATTERN> --symbol=<COIN SYMBOL> --output_dir=<DIRECTORY TO STORE QR CODES>
 ```
 For example if we want to create address with prefix t1aaaa for Hush coin and save corresponding
 QR codes to /home/john directory we enter:
  ```bash
 genaddress -p t1aaaa -s Hush -d /home/john
 ```
 To generate Bitcoin segwit address starting with 3BTC we enter:
 ```bash
 genaddress -p 3BTC -s BTC -w
 ```
7. Signing message proving ownership of an address:
  ```bash
 signmessage --coin_symbol=<COIN SYMBOL> --private_key=<PRIVATE_KEY> --message='Interesting message'
 ```
 For example proving ownership of BTC address 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi:
 ```bash
 signmessage -c BTC -p KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu -m "Hello World!"
 ```
 will return: `H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=` 
 8. Verifying if signed message was created using private key of given address:
  ```bash
 verifymessage --coin_symbol=<COIN_SYMBOL> --address=<ADDRESS> --message=<MESSAGE> --signed_message=<SIGNED MESSAGE>
 ```
 For example verifying if `H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=`
  is signed `Hello World!` message by owner of BTC address 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi we run:
 ```bash
 verifymessage -c BTC -a 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi -m "Hello World!" -s H7Ul0s8Za640duU2MhsifCX1H3Ma2NKRtLvtLYye6mFpZTW0fgXbM//bXq1yeXLHphXi8BUjtBsBHy0zrZjCYsQ=
 ``` 
### Import
Created private key should be imported using bitcoin-cli program 
or corresponding tool (importing in Qt wallet doesn't always work
```bash
  bitcoin-cli importprivkey <GENERATED_PRIV_KEY>
```
To verify the key was imported successfully:
```bash
 bitcoin-cli dumpprivkey <GENERATED_ADDRESS>
```

### Supported coins
| Coin | Symbol | Address generation | P2PKH transactions | P2SH transactions |
| --- | --- | --- | --- | --- |
| Bitcoin | BTC | Yes | Yes | Yes |
| Bitcoin Gold | BTG | Yes | No | No |
| Bitcoin Hush | BTCH | Yes | No | No |
| Bitcoin Private | BTCP | Yes | Yes | Yes |
| BitcoinZ | BTCZ | Yes | Yes | Yes |
| Bitstar | BITS | Yes | No | No |
| Buck | BUCK | Yes | No | No |
| Crave | CRAVE | Yes | No | No |
| Dash | DASH | Yes | Yes | Yes |
| Diamond | DMD | Yes | No | No |
| Dogecoin | DOGE | Yes | No | No |
| Elite | 1337 | Yes | No | No |
| Hush | HUSH | Yes | Yes | Yes |
| Komodo | KMD | Yes | Yes | Yes |
| Litecoin | LTC | Yes | Yes | Yes |
| Mooncoin | MOON | Yes | No | No |
| Qtum | QTUM | Yes | No | No |
| Safecoin | SAFE | Yes | Yes | Yes |
| Snow Gem | SNG | Yes | Yes | Yes |
| Sirius | SIRX | Yes | No | No |
| Smartcash | SMART | Yes | No | No |
| Unify | UNIFY | Yes | No | No |
| Unobtanium | UNO | Yes | No | No |
| Vertcoin | VTC | Yes | No | No |
| Zcash | ZEC | Yes | Yes | Yes |
| Zclassic | ZCL | Yes | Yes | Yes |
| Zeitcoin | ZEIT | Yes | No | No |
| ZenCash | ZEN | Yes | Yes | Yes |
| Zero | ZERO | Yes | Yes | Yes |
| Zoin | ZOIN | Yes | No | No |

## Tests
Install pytest, pytest-cov and tox packages:
```bash
 pip3 install -r requirements_dev.txt
```
Run tests and check report htmlcov/index.html:
```bash
 python3 -m pytest --cov=./ --cov-report=html
```
To run tests on various python versions run:
```bash
tox
```

## Adding new coin
1. Add new entry in `settings.py`. Prefix bytes are usually defined in chainparams.cpp or 
base58.h files.
 Exemplary for Zen we have:
```bash
'ZEN': {'name': 'zen cash', 'address_prefix_bytes': b'\x20\x89', 'secret_prefix_bytes': b'\x80'}
```
2. Update this readme with new supported coin
3. Create pull request
