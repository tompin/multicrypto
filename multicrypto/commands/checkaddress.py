import argparse
import logging
import sys

from multicrypto.address import validate_address
from multicrypto.coins import coins, validate_coin_symbol
from multicrypto.network import get_utxo_from_address
from multicrypto.utils import check_positive

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Send cryptocurrency to specified address. Supported coins are: {}'.format(
            ','.join(coin['name'].title() for coin in coins.values() if coin.get('api'))))
    parser.add_argument('-a', '--address', type=str, required=True,
                        help='Address to which we want to send')
    parser.add_argument('-c', '--coin_symbol', type=str, required=True, help='Symbol of the coin \
                        for which we want to make money transfer')
    parser.add_argument('-n', '--minimum_input_threshold', type=check_positive, required=False,
                        default=None, help='Use only inputs containing satoshis equal or above the '
                                           'specified threshold')
    parser.add_argument('-x', '--maximum_input_threshold', type=check_positive, required=False,
                        default=None, help='Use only inputs containing satoshis below or equal to '
                                           'the specified threshold')
    parser.add_argument('-l', '--limit_inputs', type=check_positive, required=False, default=None,
                        help='Specify limit for number of inputs that will be used')
    return parser.parse_args()


def check_address(args):
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    coin_symbol = args.coin_symbol.upper()
    address = args.address
    minimum_input_threshold = args.minimum_input_threshold
    maximum_input_threshold = args.maximum_input_threshold
    limit_inputs = args.limit_inputs
    if (minimum_input_threshold and maximum_input_threshold and
            minimum_input_threshold > maximum_input_threshold):
        logger.error('Minimum input threshold cannot be bigger than maximum input value!')
        return
    try:
        validate_coin_symbol(coin_symbol)
        validate_address(address, coin_symbol)
    except Exception as e:
        logger.error(e)
        return
    if not coins[coin_symbol].get('api'):
        logger.error('No api has been defined for the coin {}'.format(coin_symbol))
        return

    try:
        utxos = get_utxo_from_address(coins[coin_symbol], address, minimum_input_threshold,
                                      maximum_input_threshold, limit_inputs)
    except Exception as e:
        logger.error(e)
        return
    return utxos


def main():
    args = get_args()
    utxos = check_address(args)
    coin_symbol = args.coin_symbol.upper()
    print('{} Address {}'.format(coin_symbol, args.address))
    sum_satoshis = 0
    sum_amount = 0
    for utxo in utxos:
        print('txid: {}, confirmations: {:8}, satoshis: {:16}, amount: {:9.8f} {}'.format(
            utxo['txid'], utxo['confirmations'], utxo['satoshis'], utxo['amount'], coin_symbol))
        sum_satoshis += utxo['satoshis']
        sum_amount += utxo['amount']
    print('-' * 140)
    print(' ' * 96, 'satoshis: {:16}, amount: {:9.8f} {}'.format(
        sum_satoshis, sum_amount, coin_symbol))


if __name__ == '__main__':
    main()
