import argparse
import logging
import sys

from multicrypto import ethereum
from multicrypto.coins import P2PKH, P2SH_P2WPKH, P2WPKH, coins, ethereum_coins
from multicrypto.ecdsa import sign_message
from multicrypto.validators import check_any_coin_symbol


logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Sign message using ECDSA (elliptic curve digital signature algorithm) and '
        'bitcoin standard secp256k1 curve. Signatures of segwit addresses follow BIP-137, '
        'Ethereum messages are signed like personal_sign (EIP-191).'
    )
    parser.add_argument('-m', '--message', type=str, required=True, help='Message to be signed')
    parser.add_argument(
        '-c', '--coin_symbol', type=check_any_coin_symbol, required=True, help='Coin symbol'
    )
    parser.add_argument(
        '-p',
        '--wif_private_key',
        type=str,
        required=True,
        help='Private key in WIF format (in hex format for Ethereum) which will be used to sign '
        'message',
    )
    parser.add_argument(
        '-t',
        '--address_type',
        type=str,
        choices=(P2PKH, P2SH_P2WPKH, P2WPKH),
        default=P2PKH,
        help='Type of the address of the private key: p2pkh (legacy), p2sh-p2wpkh (nested '
        f'segwit) or p2wpkh (native segwit). Default is {P2PKH}. Not used for Ethereum',
    )
    return parser.parse_args()


def sign_ethereum_message(args) -> str:
    if args.address_type != P2PKH:
        raise ValueError('Ethereum addresses have no address types')
    private_key = ethereum.parse_private_key(args.wif_private_key)
    return ethereum.sign_message(args.message, private_key)


def main():
    args = get_args()
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    try:
        if args.coin_symbol in ethereum_coins:
            signature = sign_ethereum_message(args)
        else:
            signature = sign_message(
                coins[args.coin_symbol], args.message, args.wif_private_key, args.address_type
            ).decode()
    except ValueError as error:
        logger.error(error)
        return
    print(signature)


if __name__ == '__main__':
    main()
