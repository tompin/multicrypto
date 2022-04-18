import argparse
import logging
import sys

from multicrypto.address import validate_address
from multicrypto.coins import coins, get_coins_with_api
from multicrypto.network import get_utxo_from_address
from multicrypto.validators import check_positive, check_coin_symbol

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description=(
            f'Send cryptocurrency to specified address. '
            f'Supported coins are: {get_coins_with_api()}.'
        )
    )
    parser.add_argument(
        '-a', '--address', type=str, required=True, help='Address to which we want to send'
    )
    parser.add_argument(
        '-c',
        '--coin_symbol',
        type=check_coin_symbol,
        required=True,
        help='Symbol of the coin for which we want to make money transfer',
    )
    parser.add_argument(
        '-n',
        '--minimum_input_threshold',
        type=check_positive,
        required=False,
        default=None,
        help='Use only inputs containing satoshis equal or above the ' 'specified threshold',
    )
    parser.add_argument(
        '-x',
        '--maximum_input_threshold',
        type=check_positive,
        required=False,
        default=None,
        help='Use only inputs containing satoshis below or equal to ' 'the specified threshold',
    )
    parser.add_argument(
        '-l',
        '--limit_inputs',
        type=check_positive,
        required=False,
        default=None,
        help='Specify limit for number of inputs that will be used',
    )
    return parser.parse_args()


def check_address(args):
    coin_symbol = args.coin_symbol
    address = args.address
    minimum_input_threshold = args.minimum_input_threshold
    maximum_input_threshold = args.maximum_input_threshold
    limit_inputs = args.limit_inputs
    if (
        minimum_input_threshold
        and maximum_input_threshold
        and minimum_input_threshold > maximum_input_threshold
    ):
        raise Exception('Minimum input threshold cannot be bigger than maximum input value!')

    validate_address(address, coin_symbol)
    if not coins[coin_symbol].get('apis'):
        raise Exception(f'No api has been defined for the coin {coin_symbol}')

    utxos = get_utxo_from_address(
        coins[coin_symbol], address, minimum_input_threshold, maximum_input_threshold, limit_inputs
    )
    return utxos


def main():
    args = get_args()
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    utxos = check_address(args)
    coin_symbol = args.coin_symbol.upper()
    print(f'{coin_symbol} address {args.address}')
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


if __name__ == '__main__':
    main()
