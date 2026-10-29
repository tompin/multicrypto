import argparse
import logging
import sys

from multicrypto import ethereum
from multicrypto.coins import coins, ethereum_coins
from multicrypto.ecdsa import verify_signature
from multicrypto.validators import check_any_coin_symbol


logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Verify message using ECDSA (elliptic curve digital signature algorithm) and '
        'bitcoin standard secp256k1 curve. Signatures of segwit addresses follow BIP-137, '
        'Ethereum signatures are in hex like signatures of personal_sign (EIP-191).'
    )
    parser.add_argument(
        '-c', '--coin_symbol', type=check_any_coin_symbol, required=True, help='Coin symbol'
    )
    parser.add_argument('-m', '--message', type=str, required=True, help='Message which was signed')
    parser.add_argument('-s', '--signed_message', type=str, required=True, help='Signed message')
    parser.add_argument(
        '-a', '--address', type=str, required=True, help='Address used to sign the message'
    )
    return parser.parse_args()


def main():
    args = get_args()
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    try:
        if args.coin_symbol in ethereum_coins:
            valid = ethereum.verify_message(args.message, args.signed_message, args.address)
        else:
            valid = verify_signature(
                coins[args.coin_symbol], args.message, args.signed_message, args.address
            )
    except ValueError as error:
        logger.error(error)
        return
    print(valid)


if __name__ == '__main__':
    main()
