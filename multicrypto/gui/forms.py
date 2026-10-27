"""Parsing and validation of the GUI forms, independent of Qt to be testable without GUI."""

import json
import logging
import secrets
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple, Union

from multicrypto.address import validate_address
from multicrypto.api import InsufficientFundsError, PreparedTransaction, get_utxo_from_address
from multicrypto.coins import P2TR, coins
from multicrypto.network import NetworkError, PeerAddress, parse_node_address
from multicrypto.wallet import WalletAddress, WalletError, check_entry, check_new_password

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


def coins_with_api() -> List[str]:
    return sorted(symbol for symbol, coin in coins.items() if coin.get('apis'))


def address_description(address: WalletAddress) -> str:
    location = address.path or 'imported'
    return (
        f'{address.label} · {address.coin} {address.address_type} · {location} · {address.address}'
    )


def coins_with_slip44() -> List[str]:
    return sorted(symbol for symbol, coin in coins.items() if 'slip44' in coin)


def check_passphrase_confirmation(passphrase: str, confirmation: str) -> None:
    if not passphrase:
        raise ValueError('Passphrase cannot be empty')
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
    """Return the sum of unspent outputs (or the error message) for the address ids."""
    balances: Dict[str, Union[int, str]] = {}
    for address in addresses:
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


def describe_transaction(
    prepared: PreparedTransaction,
    coin_symbol: str,
    source_addresses: List[str],
    broadcast_target: str,
) -> List[Tuple[str, str]]:
    """Rows of the summary shown before the transaction is broadcast."""
    destination, *change = prepared.outputs
    fee = f'{format_amount(prepared.fee)} {coin_symbol}'
    if prepared.change_added_to_fee:
        fee += f' + {prepared.change_added_to_fee} satoshis of change below the dust threshold'
    if change:
        change_text = (
            f'{format_amount(change[0]["satoshis"])} {coin_symbol} to {change[0]["address"]}'
        )
    else:
        change_text = 'none'
    inputs_text = f'{len(prepared.inputs)} ({format_amount(prepared.input_satoshis)} {coin_symbol})'
    return [
        ('From', '\n'.join(source_addresses)),
        ('To', destination['address']),
        ('Amount', f'{format_amount(destination["satoshis"])} {coin_symbol}'),
        ('Fee', fee),
        ('Change', change_text),
        ('Inputs', inputs_text),
        ('Size', f'{len(prepared.raw_transaction) // 2} bytes'),
        ('Broadcast', broadcast_target),
    ]


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
        f'fee: {amount(transaction.fee)}, size: {len(transaction.raw_transaction) // 2} bytes'
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


def describe_error(error: BaseException) -> str:
    """Return the message shown to the user, unexpected errors are logged with the traceback."""
    if isinstance(error, EXPECTED_ERRORS):
        return str(error) or type(error).__name__
    logger.error('Unexpected error', exc_info=error)
    return f'Unexpected error {type(error).__name__}: {error}'
