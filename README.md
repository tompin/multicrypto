# README

[![Build Status](https://travis-ci.org/tompin/multicrypto.svg?branch=master)](https://travis-ci.org/tompin/multicrypto)
[![Coverage Status](https://coveralls.io/repos/github/tompin/multicrypto/badge.svg?branch=master)](https://coveralls.io/github/tompin/multicrypto?branch=master)
[![Latest Version](https://pypip.in/version/multicrypto/badge.svg)](https://pypi.python.org/pypi/multicrypto/)
[![Python Version](https://img.shields.io/pypi/pyversions/multicrypto.svg")](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Experimental Tool for translating and creating custom look addresses for various cryptocurrencies.

Address translation produce address for different coin, which will have the same private key as address
which is being translated. Of course private key is not needed or revealed during translation.

Creating address gives us possibility to generate private key and corresponding address with
specified prefix.

Supported coins are:
* Bitcoin (BTC)
* Bitcoin Cash (BCH)
* Bitcoin Gold (BTG)
* Bitcoin Hush (BTCH)
* Bitcoin Private (BTCP)
* BitcoinZ (BTCZ)
* Bitstar (BITS)
* Crave (CRAVE)
* Dash (DASH)
* Diamond (DMD)
* Dogecoin (DOGE)
* Elite (1337)
* Hush (HUSH)
* Komodo (KMD)
* Litecoin (LTC)
* Mooncoin (MOON)
* Qtum (QTUM)
* Snow Gem (SNG)
* Sirius (SIRX)
* Smartcash (SMART)
* Unify (UNIFY)
* Unobtanium (UNO)
* Vertcoin (VTC)
* Zcash (ZCH)
* Zclassic (ZCL)
* Zeitcoin (ZEIT)
* ZenCash (ZEN)
* Zero (ZERO)
* Zoin (ZOIN)

If you find this tool useful please donate to BTC address: 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG
## INSTALLATION

If you don't have Python 3 install it by following instructions from python.org. 
Supported Python versions are 3.4, 3.5, 3.6, 3.7. Then Run:
```bash
pip3 install multicrypto
```
### Additional packages on Ubuntu
```bash
sudo apt-get install build-essential python3-dev libgmp3-dev
```
## USAGE

### Run

 1. Translating address between coins:
  ```bash
  transaddress --address=<ADDRESS> --input_symbol=<COIN SYMBOL> --output_symbol=<COIN SYMBOL>
  ```
  For example to translate Bitcoin address 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG to Hush address we enter:
  ```bash
  transaddress -a 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG -i BTC -o HUSH
  ```
 2. Translating private key in wif format between coins
  ```bash
  transprivkey --private_key=<ADDRESS> --output_symbol=<COIN SYMBOL>
  ```
  For example to translate Bitcoin private key KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp
   to Hush private key we enter:
  ```bash
  transprivkey -p KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp -o HUSH
  ```
 3. Generating address with given pattern and corresponding private key:
  ```bash
 genaddress --pattern=<PATTERN> --symbol=<COIN SYMBOL>
 ```
 For example for Hush coin and prefix t1aaaa we enter:
  ```bash
 genaddress -p t1aaaa -s Hush
 ```
 For Bitcoin segwit address we put:
 ```bash
 genaddress -p 3BTC -s BTC -w
 ```
### Import
Created private key should be imported using bitcoin-cli program 
or corresponding tool (importing in Qt wallet doesn't always work)
```bash
  bitcoin-cli importprivkey <GENERATED_PRIV_KEY>
```
To verify the key was imported check:
```bash
 bitcoin-cli dumpprivkey <GENERATED_ADDRESS>
```
## Tests
Install pytest ,pytest-cov and tox packages:
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
