import argparse
import logging
import sys

from multicrypto.coins import coins
from multicrypto.ecdsa import sign_message
from multicrypto.validators import check_coin_symbol


logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Sign message using ECDSA (elliptic curve digital signature algorithm) and '
                    'bitcoin standard secp256k1 curve')
    parser.add_argument('-m', '--message', type=str, required=True,
                        help='Message to be signed')
    parser.add_argument('-c', '--coin_symbol', type=check_coin_symbol, required=True,
                        help='Coin symbol')
    parser.add_argument('-p', '--wif_private_key', type=str, required=True,
                        help='Private key in WIF format which will be used to sign message')
    return parser.parse_args()


def main():
    args = get_args()
    coin = coins[args.coin_symbol]
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    print(sign_message(coin, args.message, args.wif_private_key).decode())


if __name__ == '__main__':
    main()
