import argparse
import logging
import os

from multicrypto.address import translate_private_key, validate_base58, \
    get_private_key_from_wif_format, convert_private_key_to_address, \
    convert_private_key_to_wif_format
from multicrypto.coins import coins, validate_coin_symbol
from multicrypto.utils import get_qrcode_image

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(description='Translates private key between different coins. '
                                                 'Without specifying output symbol it will return integer '
                                                 'value of the private key')
    parser.add_argument('-p', '--private_key', type=str, required=True,
                        help='Private key which we want to translate')
    parser.add_argument('-o', '--output_symbol', type=str, required=False, default='',
                        help='Symbol of the coin for which we want to know corresponding '
                             'translated private key')
    parser.add_argument('-f', '--file', type=str, required=False, default=None,
                        help='Store script output in the provided file')
    parser.add_argument('-d', '--output_dir', type=str, required=False,
                        help='Directory where translated private key will be stored')
    return parser.parse_args()


def translate(args):
    output_coin_symbol = args.output_symbol.upper()
    private_key = args.private_key
    file_name = args.file

    if file_name:
        file_handler = logging.FileHandler(file_name)
        logger.addHandler(file_handler)

    if not output_coin_symbol:
        translated_private_key, compressed = get_private_key_from_wif_format(private_key)
        return translated_private_key, compressed, ''

    try:
        validate_coin_symbol(output_coin_symbol)
        if private_key.isdigit() and ('0' in private_key or len(private_key) > 52):
            wif_private_key = convert_private_key_to_wif_format(int(private_key), b'\x80')
        else:
            wif_private_key = private_key
        validate_base58(wif_private_key)
    except Exception as e:
        logger.error(e)
        return '', ''

    output_private_key_prefix_bytes = coins[output_coin_symbol]['secret_prefix_bytes']
    output_address_prefix_bytes = coins[output_coin_symbol]['address_prefix_bytes']
    translated_private_key = translate_private_key(wif_private_key, output_private_key_prefix_bytes)
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    address = convert_private_key_to_address(private_key, output_address_prefix_bytes, compressed)
    return translated_private_key, compressed, address


def main():
    args = get_args()
    translated_private_key, compressed, address = translate(args)
    print('Private key: {}, compressed: {}, address: {}, coin symbol: {}'.format(
        translated_private_key, compressed, address, args.output_symbol or None))
    if args.output_dir:
        address_image = get_qrcode_image(address, error_correct='low')
        address_image.save(os.path.join(args.output_dir, address + '.png'))
        private_key_image = get_qrcode_image(translated_private_key, error_correct='high')
        private_key_image.save(os.path.join(args.output_dir, address + '_private_key.png'))
        print('QR codes were saved in directory {}'.format(args.output_dir))


if __name__ == '__main__':
    main()
