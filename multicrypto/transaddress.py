import argparse
import logging

from multicrypto.address import translate_address
from multicrypto.coins import coins, validate_coin_symbol

logger = logging.getLogger(__name__)


def get_args():
    parser = argparse.ArgumentParser(description='Translates addresses between different coins')
    parser.add_argument('-a', '--address', type=str, required=True,
                        help='Address which we want to translate')
    parser.add_argument('-i', '--input_symbol', type=str, required=True,
                        help='Symbol of the coin for which address we want to translate')
    parser.add_argument('-o', '--output_symbol', type=str, required=True, help='Symbol of the coin \
                        for which we want to know translated corresponding address')
    parser.add_argument('-f', '--file', type=str, required=False, default=None,
                        help='Store output in the provided file')
    parser.add_argument('-s', '--script', action='store_true',
                        help='Add this option when translating P2SH (pay to script hash) address')
    return parser.parse_args()


def translate(args):
    input_coin_symbol = args.input_symbol.upper()
    output_coin_symbol = args.output_symbol.upper()
    address = args.address
    file_name = args.file
    is_script_address = args.script

    if file_name:
        file_handler = logging.FileHandler(file_name)
        logger.addHandler(file_handler)
    try:
        validate_coin_symbol(input_coin_symbol)
        validate_coin_symbol(output_coin_symbol)
    except Exception as e:
        logger.error(e)
        return

    if is_script_address:
        input_address_prefix_bytes = coins[input_coin_symbol]['script_prefix_bytes']
        output_address_prefix_bytes = coins[output_coin_symbol]['script_prefix_bytes']
    else:
        input_address_prefix_bytes = coins[input_coin_symbol]['address_prefix_bytes']
        output_address_prefix_bytes = coins[output_coin_symbol]['address_prefix_bytes']
    translated_address = translate_address(
        address, input_address_prefix_bytes, output_address_prefix_bytes)
    return translated_address


def main():
    args = get_args()
    translated_address = translate(args)
    print('{} ({}) -> {} ({})'.format(
        args.address, args.input_symbol, translated_address, args.output_symbol))


if __name__ == '__main__':
    main()
