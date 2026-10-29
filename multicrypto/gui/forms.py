"""Parsing and validation of the GUI forms, independent of Qt to be testable without GUI."""

import json
import logging
import secrets
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple, Union

from multicrypto import ethereum
from multicrypto.address import (
    convert_private_key_to_coin_address,
    convert_private_key_to_wif_format,
    detect_address_kind,
    get_private_key_from_wif_format,
    translate_address,
    translate_private_key,
    validate_address,
)
from multicrypto.api import InsufficientFundsError, PreparedTransaction, get_utxo_from_address
from multicrypto.base58 import BASE58_ALPHABET, base58_to_bytes
from multicrypto.coins import (
    ETHEREUM,
    P2PKH,
    P2SH_P2WPKH,
    P2TR,
    P2WPKH,
    coins,
    ethereum_coins,
    get_address_types,
    get_any_coin,
    is_ethereum,
)
from multicrypto.ellipticcurve import secp256k1
from multicrypto.ethereum_api import PreparedEthereumTransaction, get_rpc
from multicrypto.network import NetworkError, PeerAddress, parse_node_address
from multicrypto.utils import double_sha256, get_integer
from multicrypto.vanity import validate_vanity_pattern
from multicrypto.wallet import (
    Wallet,
    WalletAddress,
    WalletError,
    check_entry,
    check_new_password,
)

logger = logging.getLogger(__name__)

SATOSHIS_PER_COIN = 10**8
# Errors shown to the user with their message, other errors are unexpected
EXPECTED_ERRORS = (ValueError, OSError, WalletError, InsufficientFundsError, NetworkError)


def parse_amount(text: str) -> int:
    """Convert amount in coin units, e.g. 0.25, to satoshis."""
    try:
        amount = Decimal(text.strip().replace(',', '.'))
    except InvalidOperation:
        raise ValueError(f'Incorrect amount: {text}') from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError('Amount must be greater than zero')
    satoshis = amount * SATOSHIS_PER_COIN
    if satoshis != satoshis.to_integral_value():
        raise ValueError('Amount can have at most 8 decimal places')
    return int(satoshis)


def format_amount(satoshis: int) -> str:
    return f'{Decimal(satoshis) / SATOSHIS_PER_COIN:.8f}'


def parse_int(text: str, name: str, minimum: int = 1) -> int:
    try:
        value = int(text.strip())
    except ValueError:
        raise ValueError(f'{name} must be an integer') from None
    if value < minimum:
        raise ValueError(f'{name} must be at least {minimum}')
    return value


def parse_thresholds(
    minimum_text: str, maximum_text: str, limit_text: str
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Parse optional filters of the inputs, empty text means no filter."""
    minimum, maximum, limit = (
        parse_int(text, name) if text.strip() else None
        for text, name in (
            (minimum_text, 'Minimum input'),
            (maximum_text, 'Maximum input'),
            (limit_text, 'Limit of inputs'),
        )
    )
    if minimum and maximum and minimum > maximum:
        raise ValueError('Minimum input cannot be bigger than maximum input')
    return minimum, maximum, limit


def parse_address(text: str, coin_symbol: str) -> str:
    """Validate the address of the coin and return it without surrounding whitespace."""
    address = text.strip()
    if not address:
        raise ValueError('Enter the address')
    if is_ethereum(coin_symbol):
        return ethereum.validate_address(address)
    try:
        validate_address(address, coin_symbol)
    except ValueError:
        raise
    except Exception:  # base58 decoding raises KeyError, unknown prefix raises Exception
        raise ValueError(f'Incorrect address {address} for {coin_symbol}') from None
    return address


def check_password_confirmation(password: str, confirmation: str) -> None:
    check_new_password(password)
    if password != confirmation:
        raise ValueError('Passwords do not match')


def check_sources(entries: List[WalletAddress]) -> Tuple[str, str]:
    """Check that the entries can be spent in one transaction, return coin and address type."""
    if not entries:
        raise ValueError('Select at least one source address')
    kinds = {(entry.coin, entry.address_type) for entry in entries}
    if len(kinds) > 1:
        raise ValueError('All source addresses must have the same coin and address type')
    return kinds.pop()


def parse_nodes(text: str, default_port: int) -> List[PeerAddress]:
    """Parse nodes in host[:port] format separated with commas or whitespace."""
    return [parse_node_address(node, default_port) for node in text.replace(',', ' ').split()]


def extract_txid(result: str) -> str:
    """Return the transaction id from the broadcast result, which is JSON on success."""
    try:
        return json.loads(result)['txid']
    except (ValueError, KeyError, TypeError):
        raise ValueError(f'Transaction was not accepted: {result}') from None


def is_testnet(coin_symbol: str) -> bool:
    return 'testnet' in get_any_coin(coin_symbol)['name']


def all_coins() -> List[str]:
    return sorted([*coins, *ethereum_coins])


def coins_with_api() -> List[str]:
    """Coins with unspent outputs and block explorer API."""
    return sorted(symbol for symbol, coin in coins.items() if coin.get('apis'))


def all_coins_with_api() -> List[str]:
    """Coins with API, Ethereum coins use nodes and block explorers."""
    ethereum_symbols = [symbol for symbol, coin in ethereum_coins.items() if coin.get('rpcs')]
    return sorted(coins_with_api() + ethereum_symbols)


ADDRESS_TYPE_NAMES = {
    P2TR: 'Taproot',
    P2WPKH: 'Native SegWit',
    P2SH_P2WPKH: 'SegWit',
    P2PKH: 'Legacy',
    ETHEREUM: 'Ethereum',
}


def address_type_name(address_type: str) -> str:
    if address_type == ETHEREUM:
        return ADDRESS_TYPE_NAMES[ETHEREUM]
    return f'{ADDRESS_TYPE_NAMES[address_type]} ({address_type})'


def address_details(wallet: Wallet, address: WalletAddress) -> List[Tuple[str, str]]:
    """Account, address type, path and label of the wallet address."""
    if address.account_id is None:
        account = 'Imported key'
    else:
        hd_account = wallet.get_account(address.account_id)
        account = wallet.get_group(hd_account.coin, hd_account.account).label
    return [
        ('Account', account),
        ('Address type', address_type_name(address.address_type)),
        ('Path', address.path or '—'),
        ('Label', address.label),
    ]


def coins_with_slip44() -> List[str]:
    return sorted(
        symbol for symbol, coin in {**coins, **ethereum_coins}.items() if 'slip44' in coin
    )


def scannable_coins() -> List[str]:
    """Coins whose HD accounts can be scanned for used addresses, Ethereum coins with the block
    explorer."""
    return sorted(set(coins_with_slip44()) & set(all_coins_with_api()))


def format_coin_amount(coin_symbol: str, units: int) -> str:
    """Amount in satoshis, or in wei for Ethereum coins, in coin units."""
    if is_ethereum(coin_symbol):
        return ethereum.format_ether(units)
    return format_amount(units)


def key_entry_address(coin_symbol: str, key: str, address_type: str) -> str:
    """Address of the private key entered for the coin: hex for Ethereum, WIF for other coins."""
    if is_ethereum(coin_symbol):
        return ethereum.private_key_to_address(ethereum.parse_private_key(key))
    return check_entry(coin_symbol, key, address_type)


def add_private_key(
    wallet: Wallet, label: str, coin_symbol: str, key: str, address_type: str
) -> WalletAddress:
    if is_ethereum(coin_symbol):
        return wallet.add_ethereum_key(label, coin_symbol, key)
    return wallet.add_wif(label, coin_symbol, key, address_type)


def check_passphrase_confirmation(passphrase: str, confirmation: str) -> None:
    if passphrase != confirmation:
        raise ValueError('Passphrases do not match')


def choose_word_positions(word_count: int, count: int = 3) -> List[int]:
    """Random positions (from 1) of the words entered to confirm the written mnemonic."""
    return sorted(secrets.SystemRandom().sample(range(1, word_count + 1), count))


def check_confirmation_words(mnemonic: str, answers: Dict[int, str]) -> None:
    words = mnemonic.split()
    for position, answer in sorted(answers.items()):
        if answer.strip().lower() != words[position - 1]:
            raise ValueError(f'Word {position} is not correct, check the written mnemonic')


def fetch_balances(addresses: List[WalletAddress]) -> Dict[str, Union[int, str]]:
    """Return the sum of unspent outputs, or the balance in wei of Ethereum addresses (or
    the error message) for the address ids."""
    balances: Dict[str, Union[int, str]] = {}
    rpcs = {}
    for address in addresses:
        if is_ethereum(address.coin):
            if address.coin not in rpcs:
                rpcs[address.coin] = get_rpc(ethereum_coins[address.coin])
            try:
                balances[address.id] = rpcs[address.coin].get_balance(address.address)
            except EXPECTED_ERRORS as error:
                balances[address.id] = f'error: {error}'
            continue
        coin = coins[address.coin]
        if not coin.get('apis'):
            balances[address.id] = 'no API'
            continue
        try:
            utxos = get_utxo_from_address(coin, address.address)
        except EXPECTED_ERRORS as error:
            balances[address.id] = f'error: {error}'
        else:
            balances[address.id] = sum(utxo['satoshis'] for utxo in utxos)
    return balances


HIGH_FEE_RATE = 1000  # sat/vB, the confirmation shows a warning above it


def parse_fee_rate(text: str) -> float:
    """Fee rate in satoshis per virtual byte with at most one decimal place."""
    value = text.strip().replace(',', '.')
    if not value:
        raise ValueError('Enter the fee rate or press Estimate')
    try:
        rate = Decimal(value)
    except InvalidOperation:
        raise ValueError(f'Incorrect fee rate: {text}') from None
    if not rate.is_finite() or rate <= 0:
        raise ValueError('Fee rate must be greater than zero')
    if rate != rate.quantize(Decimal('0.1')):
        raise ValueError('Fee rate can have at most one decimal place')
    return float(rate)


def _vsize(prepared: PreparedTransaction) -> int:
    return prepared.vsize or len(prepared.raw_transaction) // 2


def _fee_rate(prepared: PreparedTransaction) -> float:
    return (prepared.fee + prepared.change_added_to_fee) / _vsize(prepared)


def describe_transaction(
    prepared: PreparedTransaction,
    coin_symbol: str,
    source_addresses: List[str],
    broadcast_target: str,
    change_path: Optional[str] = None,
) -> List[Tuple[str, str]]:
    """Rows of the summary shown before the transaction is broadcast."""
    destination, *change = prepared.outputs
    fee = (
        f'{format_amount(prepared.fee)} {coin_symbol} '
        f'({prepared.fee} satoshis, {_fee_rate(prepared):.1f} sat/vB)'
    )
    if prepared.change_added_to_fee:
        fee += f' + {prepared.change_added_to_fee} satoshis of change below the dust threshold'
    if change:
        change_text = (
            f'{format_amount(change[0]["satoshis"])} {coin_symbol} to {change[0]["address"]}'
        )
        if change_path:
            change_text += f' ({change_path})'
    else:
        change_text = 'none'
    inputs_text = f'{len(prepared.inputs)} ({format_amount(prepared.input_satoshis)} {coin_symbol})'
    rows = [
        ('From', '\n'.join(source_addresses)),
        ('To', destination['address']),
        ('Amount', f'{format_amount(destination["satoshis"])} {coin_symbol}'),
        ('Fee', fee),
        ('Change', change_text),
        ('Inputs', inputs_text),
        ('Size', f'{_vsize(prepared)} vB ({len(prepared.raw_transaction) // 2} bytes)'),
        ('Broadcast', broadcast_target),
    ]
    if _fee_rate(prepared) > HIGH_FEE_RATE:
        rows.append(('Warning', f'Fee rate is above {HIGH_FEE_RATE} sat/vB'))
    return rows


def parse_ether_amount(text: str) -> int:
    """Amount in ether, e.g. 0.25, in wei."""
    value = text.strip().replace(',', '.')
    if not value:
        raise ValueError('Enter the amount')
    wei = ethereum.parse_ether(value)
    if wei <= 0:
        raise ValueError('Amount must be greater than zero')
    return wei


def parse_gwei_field(text: str, name: str) -> Optional[int]:
    """Fee per gas in gwei in wei, None for the empty field (the fee is suggested)."""
    value = text.strip().replace(',', '.')
    if not value:
        return None
    try:
        return ethereum.parse_gwei(value)
    except ValueError as error:
        raise ValueError(f'{name}: {error}') from None


def parse_rpc_nodes(text: str) -> List[str]:
    """URLs of JSON-RPC of Ethereum nodes separated with commas or whitespace."""
    urls = text.replace(',', ' ').split()
    for url in urls:
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f'URL of the node {url} must start with http:// or https://')
    return urls


def describe_ethereum_transaction(
    prepared: PreparedEthereumTransaction, coin_symbol: str, broadcast_target: str
) -> List[Tuple[str, str]]:
    """Rows of the summary shown before the Ethereum transaction is broadcast."""
    transaction = prepared.transaction

    def ether(wei: int) -> str:
        return f'{ethereum.format_ether(wei)} {coin_symbol}'

    rows = [
        ('From', prepared.sender),
        ('To', transaction.to),
        ('Amount', ether(transaction.value)),
        ('Nonce', str(transaction.nonce)),
        ('Gas limit', str(transaction.gas_limit)),
        ('Max fee per gas', f'{ethereum.format_gwei(transaction.max_fee_per_gas)} gwei'),
        (
            'Priority fee per gas',
            f'{ethereum.format_gwei(transaction.max_priority_fee_per_gas)} gwei',
        ),
        ('Max fee', ether(transaction.max_fee)),
        ('Balance after', f'at least {ether(prepared.balance - prepared.max_total)}'),
        ('Broadcast', broadcast_target),
    ]
    return rows + [('Warning', warning) for warning in prepared.fee_warnings()]


def parse_wif(text: str, coin_symbol: str, address_type: str) -> Tuple[str, str]:
    """Validate the private key in WIF format, return it with its address of the given type."""
    wif = text.strip()
    if not wif:
        raise ValueError('Enter the private key in WIF format')
    return wif, check_entry(coin_symbol, wif, address_type)


def check_signable(address: WalletAddress) -> None:
    if address.address_type == P2TR:
        raise ValueError('Taproot addresses cannot sign messages (BIP-137)')


def describe_sweep(
    prepared: List[PreparedTransaction],
    coin_symbol: str,
    source_address: str,
    destination_address: str,
) -> List[Tuple[str, str]]:
    """Rows of the summary shown before the sweep transactions are broadcast."""

    def amount(satoshis: int) -> str:
        return f'{format_amount(satoshis)} {coin_symbol}'

    batches = '\n'.join(
        f'{number}. inputs: {len(transaction.inputs)}, '
        f'amount: {amount(transaction.outputs[0]["satoshis"])}, '
        f'fee: {amount(transaction.fee)} ({_fee_rate(transaction):.1f} sat/vB), '
        f'size: {_vsize(transaction)} vB'
        for number, transaction in enumerate(prepared, start=1)
    )
    inputs = sum(len(transaction.inputs) for transaction in prepared)
    input_satoshis = sum(transaction.input_satoshis for transaction in prepared)
    return [
        ('From', source_address),
        ('To', destination_address),
        ('Transactions', str(len(prepared))),
        ('Inputs', f'{inputs} ({amount(input_satoshis)})'),
        ('Fee', amount(sum(transaction.fee for transaction in prepared))),
        ('Received', amount(sum(transaction.outputs[0]['satoshis'] for transaction in prepared))),
        ('Batches', batches),
    ]


def translate_address_text(text: str, input_symbol: str, output_symbol: str) -> str:
    """Address of the same public key hash (or script hash) for another coin."""
    address = parse_address(text, input_symbol)
    if detect_address_kind(address, input_symbol) == 'p2sh':
        key = 'script_prefix_bytes'
    else:
        key = 'address_prefix_bytes'
    return translate_address(address, coins[input_symbol][key], coins[output_symbol][key])


def parse_private_key_input(text: str, integer: bool) -> str:
    """Private key in WIF format of any coin, or an integer (decimal or hex starting with 0x)
    converted to WIF of bitcoin with compressed public key."""
    value = text.strip()
    if not value:
        raise ValueError('Enter the private key')
    if integer:
        number = get_integer(value.lower())
        if number is None or not 0 < number < secp256k1.n:
            raise ValueError(
                f'Private key must be an integer from 1 to {secp256k1.n - 1} (decimal or hex)'
            )
        return convert_private_key_to_wif_format(number, coins['BTC']['secret_prefix_bytes'])
    if set(value) - set(BASE58_ALPHABET):
        raise ValueError('Private key in WIF format can contain only base58 characters')
    data = base58_to_bytes(value)
    payload, checksum = data[:-4], data[-4:]
    if len(data) < 5 or double_sha256(payload).digest()[:4] != checksum:
        raise ValueError('Incorrect checksum of the private key')
    compressed = len(payload) == 34 and payload[-1] == 1
    if len(payload) != 33 and not compressed:
        raise ValueError('Incorrect private key')
    private_key, _ = get_private_key_from_wif_format(value)
    if not 0 < private_key < secp256k1.n:
        raise ValueError('Incorrect private key')
    return value


def translated_private_key(wif: str, output_symbol: str) -> str:
    """Private key in WIF format of another coin, or in hex format for Ethereum."""
    if is_ethereum(output_symbol):
        return ethereum.format_private_key(get_private_key_from_wif_format(wif)[0])
    return translate_private_key(wif, coins[output_symbol]['secret_prefix_bytes'])


def translated_key_addresses(wif: str, output_symbol: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Private key of another coin and its addresses of all supported types."""
    translated = translated_private_key(wif, output_symbol)
    private_key, compressed = get_private_key_from_wif_format(wif)
    if is_ethereum(output_symbol):
        return translated, [(ETHEREUM, ethereum.private_key_to_address(private_key))]
    coin = coins[output_symbol]
    address_types = get_address_types(coin) if compressed else (P2PKH,)
    return translated, [
        (
            address_type,
            convert_private_key_to_coin_address(private_key, coin, compressed, address_type),
        )
        for address_type in address_types
    ]


def source_wif(wallet: Wallet, address: WalletAddress) -> str:
    """Private key of the wallet address in WIF format, Ethereum keys as bitcoin WIF with
    compressed public key, so they can be translated to other coins."""
    if is_ethereum(address.coin):
        return convert_private_key_to_wif_format(
            wallet.private_key(address), coins['BTC']['secret_prefix_bytes']
        )
    return wallet.private_key_wif(address)


def parse_vanity_pattern(text: str, coin_symbol: str, address_type: str) -> str:
    pattern = text.strip()
    if not pattern:
        raise ValueError('Enter the beginning of the address')
    return validate_vanity_pattern(pattern, coin_symbol, address_type)


def format_duration(seconds: float) -> str:
    for unit, size in (('days', 86400), ('h', 3600), ('min', 60)):
        if seconds >= size:
            return f'{seconds / size:.0f} {unit}'
    return f'{seconds:.0f} s'


def describe_error(error: BaseException) -> str:
    """Return the message shown to the user, unexpected errors are logged with the traceback."""
    if isinstance(error, EXPECTED_ERRORS):
        return str(error) or type(error).__name__
    logger.error('Unexpected error', exc_info=error)
    return f'Unexpected error {type(error).__name__}: {error}'
