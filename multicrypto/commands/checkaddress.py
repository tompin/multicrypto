import argparse
import logging
import sys
from typing import List, Dict, Any

from multicrypto.address import validate_address
from multicrypto.api import get_utxo_from_address
from multicrypto.coins import coins, get_coins_with_api
from multicrypto.validators import check_positive, check_coin_symbol

logger = logging.getLogger(__name__)


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            f'Check unspent outputs of the cryptocurrency address. '
            f'Supported coins are: {get_coins_with_api()}.'
        )
    )
    parser.add_argument('-a', '--address', type=str, required=True, help='Address to check')
    parser.add_argument(
        '-c', '--coin_symbol', type=check_coin_symbol, required=True, help='Symbol of the coin'
    )
    parser.add_argument(
        '-n',
        '--minimum_input_threshold',
        type=check_positive,
        required=False,
        default=None,
        help='Minimum input threshold in satoshis',
    )
    parser.add_argument(
        '-x',
        '--maximum_input_threshold',
        type=check_positive,
        required=False,
        default=None,
        help='Maximum input threshold in satoshis',
    )
    parser.add_argument(
        '-l',
        '--limit_inputs',
        type=check_positive,
        required=False,
        default=None,
        help='Limit the number of inputs used',
    )
    return parser.parse_args()


def check_address(args: argparse.Namespace) -> List[Dict[str, Any]]:
    coin_symbol = args.coin_symbol
    address = args.address
    min_threshold = args.minimum_input_threshold
    max_threshold = args.maximum_input_threshold
    limit_inputs = args.limit_inputs

    if min_threshold and max_threshold and min_threshold > max_threshold:
        raise ValueError('Minimum input threshold cannot be bigger than maximum input value!')

    validate_address(address, coin_symbol)

    coin_data = coins.get(coin_symbol)
    if not coin_data or not coin_data.get('apis'):
        raise ValueError(f'No API has been defined for the coin {coin_symbol}')

    utxos = get_utxo_from_address(coin_data, address, min_threshold, max_threshold, limit_inputs)
    return utxos


def display_utxos(utxos: List[Dict[str, Any]], coin_symbol: str, address: str) -> None:
    coin_symbol = coin_symbol.upper()
    print(f'{coin_symbol} address {address}')
    sum_satoshis = 0
    sum_amount = 0
    for utxo in utxos:
        print(
            f'txid: {utxo["txid"]}, confirmations: {utxo["confirmations"]:8}, '
            f'satoshis: {utxo["satoshis"]:16}, amount: {utxo["amount"]:9.8f} {coin_symbol}'
        )
        sum_satoshis += utxo['satoshis']
        sum_amount += utxo['amount']
    print('-' * 140)
    print(
        f'{len(utxos):9} inputs {" " * 79} satoshis: {sum_satoshis:16}, '
        f'amount: {sum_amount:9.8f} {coin_symbol}'
    )


def main():
    args = get_args()
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    utxos = check_address(args)
    display_utxos(utxos, args.coin_symbol, args.address)


if __name__ == '__main__':
    main()
