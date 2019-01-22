import argparse
import json
import logging
import sys

from multicrypto.address import validate_address, validate_wif_private_key
from multicrypto.coins import coins
from multicrypto.network import send_from_private_keys
from multicrypto.scripts import validate_hex_script
from multicrypto.validators import check_coin_symbol, check_non_negative, check_positive

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Send cryptocurrency to specified address. Supported coins are: {}'.format(
            ','.join(coin['name'].title() for coin in coins.values() if coin.get('apis'))))
    parser.add_argument('-p', '--wif_private_keys', type=str, required=False,
                        help='Comma separated private keys in WIF format which will be used'
                             ' to send funds from')
    parser.add_argument('-a', '--address', type=str, required=True,
                        help='Address to which we want to send funds')
    parser.add_argument('-u', '--unlocking_scripts', type=str, required=False, default=None,
                        help='Unlocking scripts in HEX format, which will be used to spent inputs')
    parser.add_argument('-i', '--input_addresses', type=str, required=False, default=None,
                        help='Comma separated list of addresses from which funds will be sent')
    parser.add_argument('-c', '--coin_symbol', type=check_coin_symbol, required=True,
                        help='Symbol of the coin for which we want to make money transfer')
    parser.add_argument('-s', '--satoshis', type=check_positive, required=True,
                        help='How many satoshis you want to send')
    parser.add_argument('-f', '--fee', type=check_non_negative, required=False, default=10000,
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
    destination_address = args.address
    input_addresses = args.input_addresses.split(',') if args.input_addresses else []
    unlocking_scripts = args.unlocking_scripts.split(',') if args.unlocking_scripts else []
    wif_private_keys = args.wif_private_keys.split(',') if args.wif_private_keys else []
    satoshis = args.satoshis
    fee = args.fee
    minimum_input_threshold = args.minimum_input_threshold
    maximum_input_threshold = args.maximum_input_threshold
    limit_inputs = args.limit_inputs
    if (minimum_input_threshold and maximum_input_threshold and
            minimum_input_threshold > maximum_input_threshold):
        logger.error('Minimum input threshold cannot be bigger than maximum input value!')
        return
    if not wif_private_keys and not input_addresses:
        logger.error('You must provide wif_private_keys or input_addresses!')
        return
    if len(unlocking_scripts) != len(input_addresses):
        logger.error('Number of unlocking scripts must match number of input addresses!')
        return
    try:
        if destination_address:
            validate_address(destination_address, coin_symbol)
        for wif_private_key in wif_private_keys:
            validate_wif_private_key(wif_private_key, coin_symbol)
        for unlocking_script in unlocking_scripts:
            validate_hex_script(unlocking_script)
    except Exception as e:
        logger.error(e)
        return
    if not coins[coin_symbol].get('apis'):
        logger.error('No api has been defined for the coin {}'.format(coin_symbol))
        return

    result = send_from_private_keys(
        coin=coins[coin_symbol],
        wif_private_keys=wif_private_keys,
        input_addresses=input_addresses,
        unlocking_scripts=unlocking_scripts,
        destination_address=destination_address,
        satoshis=satoshis,
        fee=fee,
        minimum_input_threshold=minimum_input_threshold,
        maximum_input_threshold=maximum_input_threshold,
        limit_inputs=limit_inputs)

    return result


def main():
    args = get_args()
    try:
        result = send_crypto(args)
        print(result)
        json.loads(result)
    except Exception as e:
        logger.exception('Error: {}'.format(e))


if __name__ == '__main__':
    main()
