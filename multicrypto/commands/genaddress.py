import argparse
import datetime
import logging
import multiprocessing
import os
import sys

from fastecdsa.curve import secp256k1
from fastecdsa.keys import gen_private_key

from multicrypto.address import convert_public_key_to_address, convert_private_key_to_wif_format, \
    validate_pattern
from multicrypto.coins import coins, validate_coin_symbol
from multicrypto.utils import get_qrcode_image

logger = logging.getLogger(__name__)
N = secp256k1.q  # order of the curve
G = secp256k1.G  # generator point


def generate_address(worker_num, coin_settings, pattern, compressed, segwit, out_dir, found, quit):
    if segwit:
        prefix_bytes = coin_settings['script_prefix_bytes']
    else:
        prefix_bytes = coin_settings['address_prefix_bytes']
    secret_prefix_bytes = coin_settings['secret_prefix_bytes']
    seed = gen_private_key(secp256k1)
    point = seed * G
    counter = 0
    start_time = datetime.datetime.now()
    while not quit.is_set():
        address = convert_public_key_to_address(point, prefix_bytes, compressed, segwit)
        if address.startswith(pattern):
            private_key = (seed + counter) % N
            wif_private_key = convert_private_key_to_wif_format(
                private_key, secret_prefix_bytes, compressed)
            print('Address: {}\nPrivate key: {}'.format(address, wif_private_key))
            if out_dir:
                address_image = get_qrcode_image(address, error_correct='low')
                address_image.save(os.path.join(out_dir, address + '.png'))
                private_key_image = get_qrcode_image(wif_private_key, error_correct='high')
                private_key_image.save(os.path.join(out_dir, address + '_private_key.png'))
                print('QR codes were saved in directory {}'.format(out_dir))
            found.set()
            quit.set()
            return address, wif_private_key
        point += G
        counter += 1
        if counter % 10000000 == 0:
            print('worker: {}, checked {}M addresses ({}/sec)'.format(
                worker_num, counter / 1000000,
                counter // (datetime.datetime.now() - start_time).seconds))
            sys.stdout.flush()


def get_args():
    parser = argparse.ArgumentParser(description='Multi coin vanity generation script')
    parser.add_argument('-p', '--pattern', type=str, required=True,
                        help='Pattern which generated address should contain')
    parser.add_argument('-s', '--symbol', type=str, required=True,
                        help='Symbol of the coin i.e. BTC')
    parser.add_argument('-c', '--cores', type=int, required=False,
                        default=multiprocessing.cpu_count(),
                        help='How many cores we would like to use. Default maximum available.')
    parser.add_argument('-u', '--uncompressed', action='store_true',
                        help='Generate address based on uncompressed wif private key format')
    parser.add_argument('-w', '--segwit', action='store_true',
                        help='Generate segwit (P2SH-P2WPKH) address')
    parser.add_argument('-d', '--output_dir', type=str, required=False,
                        help='Directory where QR codes with address and private key will be stored')

    return parser.parse_args()


def start_workers(args):
    coin_symbol = args.symbol.upper()
    pattern = args.pattern
    workers = args.cores
    compressed = not args.uncompressed
    segwit = args.segwit
    output_dir = args.output_dir
    if segwit and not compressed:
        raise Exception('Segwit addresses must used compressed public key representation')
    jobs = []
    quit = multiprocessing.Event()
    found = multiprocessing.Event()
    try:
        validate_coin_symbol(coin_symbol)
        validate_pattern(pattern, coin_symbol, segwit)
    except Exception as e:
        logger.error(e)
        return
    print('Looking for pattern {} for {} using {} workers'.format(
        pattern, coins[coin_symbol]['name'], workers))
    for i in range(workers):
        p = multiprocessing.Process(
            target=generate_address,
            args=(i, coins[coin_symbol], pattern, compressed, segwit, output_dir, found, quit))
        jobs.append(p)
        p.start()
    found.wait()


def main():
    args = get_args()
    start_workers(args)


if __name__ == '__main__':
    main()
