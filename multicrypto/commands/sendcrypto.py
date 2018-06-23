import argparse
import json
import logging
import sys

from multicrypto.address import validate_address, validate_wif_private_key
from multicrypto.coins import coins, validate_coin_symbol
from multicrypto.network import send
from multicrypto.utils import check_positive

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Send cryptocurrency to specified address. Supported coins are: {}'.format(
            ','.join(coin['name'].title() for coin in coins.values() if coin.get('api'))))
    parser.add_argument('-p', '--wif_private_keys', type=str, required=True,
                        help='Comma separated private keys in WIF format which will be used'
                             ' to send funds from')
    parser.add_argument('-a', '--address', type=str, required=True,
                        help='Address to which we want to send')
    parser.add_argument('-c', '--coin_symbol', type=str, required=True, help='Symbol of the coin \
                        for which we want to make money transfer')
    parser.add_argument('-s', '--satoshis', type=check_positive, required=True,
                        help='How many satoshis you want to send')
    parser.add_argument('-f', '--fee', type=check_positive, required=False, default=10000,
                        help='Transaction fee')
    parser.add_argument('-n', '--minimum_input_threshold', type=check_positive, required=False,
                        default=None, help='Use only inputs containing satoshis equal or above the '
                                           'specified threshold')
    parser.add_argument('-x', '--maximum_input_threshold', type=check_positive, required=False,
                        default=None, help='Use only inputs containing satoshis below or equal to '
                                           'the specified threshold')
    parser.add_argument('-l', '--limit_inputs', type=check_positive, required=False, default=None,
                        help='Specify limit for number of inputs that will be used in transaction')
    return parser.parse_args()


def send_crypto(args):
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    coin_symbol = args.coin_symbol.upper()
    address = args.address
    wif_private_keys = args.wif_private_keys.split(',')
    satoshis = args.satoshis
    fee = args.fee
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
        for wif_private_key in wif_private_keys:
            validate_wif_private_key(wif_private_key, coin_symbol)
    except Exception as e:
        logger.error(e)
        return
    if not coins[coin_symbol].get('api'):
        logger.error('No api has been defined for the coin {}'.format(coin_symbol))
        return

    try:
        result = send(coins[coin_symbol], wif_private_keys, address, satoshis, fee,
                      minimum_input_threshold, maximum_input_threshold, limit_inputs)
    except Exception as e:
        logger.error(e)
        return

    return result


def main():
    args = get_args()
    result = send_crypto(args)
    print(result)
    try:
        json.loads(result)
    except Exception as e:
        logger.error('Some error occured. Most likey too many inputs were used. Try to limit number'
                     ' of inputs by using --minimum_input_threshold, --maximum_input_threshold and '
                     '--limit_inputs parameters. Check "sendcrypto help" for more information.')


if __name__ == '__main__':
    main()
