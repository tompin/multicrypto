import argparse
import logging
import sys

from multicrypto.address import validate_address, validate_wif_private_key, \
    convert_wif_private_key_to_address
from multicrypto.coins import coins
from multicrypto.network import get_utxo_from_private_keys, send_utxos
from multicrypto.validators import check_positive, check_coin_symbol

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Send cryptocurrency to specified address. Main purpose of this command is to '
                    'combine many small inputs into larger ones. There is no way to specify amount '
                    'that will be send, but we can define which inputs we want to use. This command'
                    ' could create many transactions depending how many inputs our address have. '
                    'For example if address has 1000 inputs which we want to sweep and we use '
                    'default batch_size parameter which is 200, this command should create 5 '
                    'transactions. Supported coins are: {}'.format(
                        ','.join(coin for coin in coins if coins[coin].get('apis'))))
    parser.add_argument('-p', '--wif_private_key', type=str, required=True,
                        help='Private key in WIF format which will be used to send funds from')
    parser.add_argument('-a', '--address', type=str, required=False,
                        help='Address to which we want to send. By default it is sending to itself'
                             ' (destination address is the same as source address)')
    parser.add_argument('-c', '--coin_symbol', type=check_coin_symbol, required=True,
                        help='Symbol of the coin for which we want to make money transfer')
    parser.add_argument('-f', '--fee', type=check_positive, required=False, default=10000,
                        help='Transaction fee which will be used in each transaction')
    parser.add_argument('-n', '--minimum_input_threshold', type=check_positive, required=False,
                        default=None, help='Use only inputs containing satoshis equal or above the '
                                           'specified threshold')
    parser.add_argument('-x', '--maximum_input_threshold', type=check_positive, required=False,
                        default=None, help='Use only inputs containing satoshis below or equal to '
                                           'the specified threshold')
    parser.add_argument('-b', '--batch_size', type=check_positive, required=False, default=200,
                        help='Specify limit for number of inputs that will be used in transaction')
    return parser.parse_args()


def sweep_address(args):
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    coin_symbol = args.coin_symbol
    destination_address = args.address
    wif_private_key = args.wif_private_key
    fee = args.fee
    minimum_input_threshold = args.minimum_input_threshold
    maximum_input_threshold = args.maximum_input_threshold
    batch_size = args.batch_size
    if minimum_input_threshold and maximum_input_threshold and \
            minimum_input_threshold > maximum_input_threshold:
        logger.error('Minimum input threshold cannot be bigger than maximum input value!')
        return
    try:
        coin = coins[coin_symbol]
        validate_wif_private_key(wif_private_key, coin_symbol)
        if destination_address:
            validate_address(destination_address, coin_symbol)
        else:
            destination_address = convert_wif_private_key_to_address(
                wif_private_key, coin['address_prefix_bytes'])
    except Exception as e:
        logger.error(e)
        return
    if not coin.get('apis'):
        logger.error('No api has been defined for the coin {}'.format(coin_symbol))
        return
    try:
        utxos = get_utxo_from_private_keys(
            coin=coin,
            wif_private_keys=[wif_private_key],
            minimum_input_threshold=minimum_input_threshold,
            maximum_input_threshold=maximum_input_threshold)
        utxos = list(utxos)
        batches_counter = 1 + len(utxos) // batch_size
        for i in range(batches_counter):
            batch_utxos = utxos[batch_size * i: batch_size * (i + 1)]
            satoshis = sum(utxo['satoshis'] for utxo in batch_utxos)
            if satoshis < fee:
                raise Exception('Fee {} is larger than sum of batch inputs {}'.format(
                    fee, satoshis))
            result = send_utxos(coin, batch_utxos, destination_address, satoshis - fee, fee)
            print(result)
    except Exception as e:
        logger.exception(e)


def main():
    args = get_args()
    sweep_address(args)


if __name__ == '__main__':
    main()
