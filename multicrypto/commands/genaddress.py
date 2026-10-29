import argparse
import logging
import time

from multicrypto.coins import P2PKH, P2SH_P2WPKH, coins, ethereum_coins
from multicrypto.scripts import validate_hex_script, convert_script_to_p2sh_address
from multicrypto.utils import save_qrcode
from multicrypto.validators import check_any_coin_symbol
from multicrypto.vanity import VANITY_ADDRESS_TYPES, VanitySearch

logger = logging.getLogger(__name__)
PROGRESS_SECONDS = 10


def get_args():
    parser = argparse.ArgumentParser(description='Multi coin vanity generation script')
    parser.add_argument(
        '-p',
        '--pattern',
        type=str,
        required=False,
        default='',
        help='Beginning of the generated address, e.g. 1Abc, bc1qxyz or 0xabc (Ethereum '
        'addresses are compared case insensitively)',
    )
    parser.add_argument(
        '-s',
        '--symbol',
        type=check_any_coin_symbol,
        required=True,
        help='Symbol of the coin i.e. BTC or ETH',
    )
    parser.add_argument(
        '-i',
        '--input_script',
        type=str,
        required=False,
        help='Generate address based on input script for P2SH transactions',
    )
    parser.add_argument(
        '-c',
        '--cores',
        type=int,
        required=False,
        default=1,
        help='How many cores we would like to use. Default 1 core.',
    )
    parser.add_argument(
        '-u',
        '--uncompressed',
        action='store_true',
        help='Generate address based on uncompressed wif private key format',
    )
    parser.add_argument(
        '-t',
        '--address_type',
        type=str,
        choices=VANITY_ADDRESS_TYPES,
        default=P2PKH,
        help='Type of the generated address: p2pkh (legacy), p2sh-p2wpkh (nested segwit) or '
        f'p2wpkh (native segwit, bech32). Default is {P2PKH}',
    )
    parser.add_argument(
        '-w', '--segwit', action='store_true', help='Generate segwit (P2SH-P2WPKH) address'
    )
    parser.add_argument(
        '-d',
        '--output_dir',
        type=str,
        required=False,
        help='Directory where QR codes with address and private key will be stored',
    )

    return parser.parse_args()


def print_script_address(coin_symbol, input_script, output_dir):
    try:
        validate_hex_script(input_script)
    except ValueError as exc:
        logger.error(exc)
        return
    address = convert_script_to_p2sh_address(
        input_script, coins[coin_symbol]['script_prefix_bytes']
    )
    if output_dir:
        save_qrcode(address, output_dir)
    print(address)


def check_ethereum_args(args):
    if args.input_script or args.uncompressed or args.segwit or args.address_type != P2PKH:
        raise ValueError(
            'Ethereum addresses have no input scripts, address types or uncompressed keys'
        )


def start_workers(args):
    coin_symbol = args.symbol
    ethereum = coin_symbol in ethereum_coins
    if ethereum:
        try:
            check_ethereum_args(args)
        except ValueError as exc:
            logger.error(exc)
            return
    elif args.input_script:
        print_script_address(coin_symbol, args.input_script, args.output_dir)
        return
    address_type = P2SH_P2WPKH if args.segwit else args.address_type
    try:
        search = VanitySearch(
            coin_symbol, address_type, args.pattern, args.cores, not args.uncompressed
        )
    except ValueError as exc:
        logger.error(exc)
        return
    coin = ethereum_coins[coin_symbol] if ethereum else coins[coin_symbol]
    print(f'Looking for pattern {search.pattern} for {coin["name"]} using {args.cores} workers')
    search.start()
    started = last_report = time.monotonic()
    try:
        while search.result() is None:
            if search.failed:
                logger.error('Vanity search process ended unexpectedly')
                return
            time.sleep(0.1)
            if time.monotonic() - last_report >= PROGRESS_SECONDS:
                last_report = time.monotonic()
                speed = search.attempts / (last_report - started)
                print(f'checked {search.attempts / 1000000:.1f}M addresses ({speed:.0f}/sec)')
    finally:
        search.stop()
    address, wif_private_key = search.result()
    print(f'Address: {address}\nPrivate key: {wif_private_key}')
    if args.output_dir:
        save_qrcode(address, args.output_dir, error_correct='L')
        save_qrcode(wif_private_key, args.output_dir, f'{address}_private_key.png')
        print(f'QR codes were saved in directory {args.output_dir}')


def main():
    args = get_args()
    start_workers(args)


if __name__ == '__main__':
    main()
