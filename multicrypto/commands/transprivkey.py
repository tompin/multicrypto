import argparse
import logging

from multicrypto.address import (
    translate_private_key,
    validate_base58,
    get_private_key_from_wif_format,
    convert_private_key_to_address,
    convert_private_key_to_wif_format,
)
from multicrypto import ethereum
from multicrypto.coins import coins, ethereum_coins
from multicrypto.utils import save_qrcode, get_integer
from multicrypto.validators import check_any_coin_symbol

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(
        description='Translates private key between different coins. '
        'Without specifying output symbol it will return '
        'integer value of the private key. Ethereum private keys are in hex format, they are '
        'translated to other coins as integers (-i) with 0x prefix'
    )
    parser.add_argument(
        '-p',
        '--private_key',
        type=str,
        required=True,
        help='Private key which we want to translate',
    )
    parser.add_argument(
        '-o',
        '--output_symbol',
        type=check_any_coin_symbol,
        required=False,
        # argparse converts a default string with the type, so the default is not an empty string
        default=None,
        help='Symbol of the coin for which we want to know corresponding translated private key',
    )
    parser.add_argument(
        '-f',
        '--file',
        type=str,
        required=False,
        default=None,
        help='Store script output in the provided file',
    )
    parser.add_argument(
        '-d',
        '--output_dir',
        type=str,
        required=False,
        help='Directory where translated private key will be stored',
    )
    parser.add_argument(
        '-i', '--integer', action='store_true', help='Private key will be treated as integer'
    )
    return parser.parse_args()


def translate(args):
    output_coin_symbol = args.output_symbol or ''
    private_key = args.private_key
    file_name = args.file

    if file_name:
        file_handler = logging.FileHandler(file_name)
        logger.addHandler(file_handler)

    if not output_coin_symbol:
        translated_private_key, compressed = get_private_key_from_wif_format(private_key)
        return translated_private_key, compressed, ''

    try:
        if args.integer:
            int_private_key = get_integer(private_key)
            wif_private_key = convert_private_key_to_wif_format(int_private_key, b'\x80')
        else:
            wif_private_key = private_key
        validate_base58(wif_private_key)
    except ValueError as exc:
        logger.error(exc)
        return '', '', ''

    if output_coin_symbol in ethereum_coins:
        int_private_key, compressed = get_private_key_from_wif_format(wif_private_key)
        address = ethereum.private_key_to_address(int_private_key)
        return ethereum.format_private_key(int_private_key), compressed, address

    output_private_key_prefix_bytes = coins[output_coin_symbol]['secret_prefix_bytes']
    output_address_prefix_bytes = coins[output_coin_symbol]['address_prefix_bytes']
    translated_private_key = translate_private_key(wif_private_key, output_private_key_prefix_bytes)
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    address = convert_private_key_to_address(private_key, output_address_prefix_bytes, compressed)
    return translated_private_key, compressed, address


def main():
    args = get_args()
    translated_private_key, compressed, address = translate(args)
    print(
        f'Private key: {translated_private_key}, compressed: {compressed}, '
        f'address: {address}, coin symbol: {args.output_symbol or None}'
    )
    if args.output_dir:
        save_qrcode(address, args.output_dir, error_correct='L')
        save_qrcode(translated_private_key, args.output_dir, f'{address}_private_key.png')
        print(f'QR codes were saved in directory {args.output_dir}')


if __name__ == '__main__':
    main()
