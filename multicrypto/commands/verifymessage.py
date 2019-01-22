import argparse
import base64
import logging
import sys

from multicrypto.coins import coins
from multicrypto.ecdsa import verify_message, add_magic_prefix
from multicrypto.ellipticcurve import secp256k1
from multicrypto.validators import check_coin_symbol


logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Verify message using ECDSA (elliptic curve digital signature algorithm) and '
                    'bitcoin standard secp256k1 curve')
    parser.add_argument('-c', '--coin_symbol', type=check_coin_symbol, required=True,
                        help='Coin symbol')
    parser.add_argument('-m', '--message', type=str, required=True,
                        help='Message which was signed')
    parser.add_argument('-s', '--signed_message', type=str, required=True,
                        help='Signed message')
    parser.add_argument('-a', '--address', type=str, required=True,
                        help='Address used to sign the message')
    return parser.parse_args()


def main():
    args = get_args()
    coin = coins[args.coin_symbol]
    signed_message = args.signed_message.encode()
    message_with_magic_prefix = None
    if args.message:
        message_with_magic_prefix = add_magic_prefix(args.message, coin).encode()

    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    try:
        decoded_message = base64.b64decode(signed_message)
    except Exception as e:
        logger.error(e)
        return
    v = decoded_message[0]
    curve = secp256k1
    signature = decoded_message[1:]
    if len(signature) != 2 * curve.bytes_size:
        logger.error('Invalid message length')
        return
    r = int.from_bytes(signature[:curve.bytes_size], byteorder='big')
    s = int.from_bytes(signature[curve.bytes_size:], byteorder='big')
    print(verify_message(coin, message_with_magic_prefix, v, (r, s), args.address))


if __name__ == '__main__':
    main()
