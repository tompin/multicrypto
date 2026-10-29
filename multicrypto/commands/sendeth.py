import argparse
import json
import logging
import sys

from multicrypto.api import InsufficientFundsError
from multicrypto.coins import ethereum_coins
from multicrypto.ethereum import (
    format_ether,
    format_gwei,
    parse_ether,
    parse_gwei,
    parse_private_key,
)
from multicrypto.ethereum_api import broadcast_transaction, get_rpc, prepare_transfer
from multicrypto.validators import check_ethereum_coin_symbol, check_non_negative, check_positive

logger = logging.getLogger(__name__)


def check_ether(value):
    try:
        return parse_ether(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def check_gwei(value):
    try:
        return parse_gwei(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def get_args():
    parser = argparse.ArgumentParser(
        description=(
            'Send ether to the specified address using EIP-1559 transaction. Supported coins are: '
            + ', '.join(f'{symbol} ({coin["name"]})' for symbol, coin in ethereum_coins.items())
        )
    )
    parser.add_argument(
        '-c',
        '--coin_symbol',
        type=check_ethereum_coin_symbol,
        required=True,
        help='Symbol of the coin: ETH or TETH (Sepolia testnet)',
    )
    parser.add_argument(
        '-p',
        '--private_key',
        type=str,
        required=True,
        help='Private key in hex format (64 hexadecimal digits) of the address sending ether',
    )
    parser.add_argument(
        '-a', '--address', type=str, required=True, help='Address to which ether will be sent'
    )
    parser.add_argument(
        '-v',
        '--value',
        type=check_ether,
        required=True,
        help='Amount of ether to send, e.g. 0.01',
    )
    parser.add_argument(
        '--max_fee',
        type=check_gwei,
        default=None,
        help='Max fee per gas in gwei, by default twice the base fee of the next block plus '
        'the priority fee',
    )
    parser.add_argument(
        '--priority_fee',
        type=check_gwei,
        default=None,
        help='Max priority fee (tip) per gas in gwei, by default the median of the recent blocks',
    )
    parser.add_argument(
        '--gas_limit',
        type=check_positive,
        default=None,
        help='Gas limit, by default estimated by the node (21000 for a transfer to an account '
        'without code)',
    )
    parser.add_argument(
        '--nonce',
        type=check_non_negative,
        default=None,
        help='Nonce of the transaction, by default the next one of the address. The nonce of '
        'a pending transaction replaces it when the fees are higher',
    )
    parser.add_argument(
        '--node',
        type=str,
        action='append',
        default=None,
        help='URL of JSON-RPC of the Ethereum node, e.g. http://localhost:8545, can be repeated '
        'to try more nodes in order. By default public nodes are used',
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Print the signed transaction without sending it',
    )
    return parser.parse_args()


def send_eth(args):
    logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
    coin_symbol = args.coin_symbol
    coin = ethereum_coins[coin_symbol]
    try:
        private_key = parse_private_key(args.private_key)
    except ValueError as e:
        logger.error(e)
        return None
    rpc = get_rpc(coin, args.node)
    prepared = prepare_transfer(
        coin,
        rpc,
        private_key,
        args.address,
        args.value,
        nonce=args.nonce,
        gas_limit=args.gas_limit,
        max_priority_fee_per_gas=args.priority_fee,
        max_fee_per_gas=args.max_fee,
    )
    transaction = prepared.transaction
    balance = format_ether(prepared.balance)
    logger.info('From: %s (balance %s %s)', prepared.sender, balance, coin_symbol)
    logger.info('To: %s', transaction.to)
    logger.info('Value: %s %s', format_ether(transaction.value), coin_symbol)
    logger.info(
        'Nonce: %s, gas limit: %s, max fee per gas: %s gwei, priority fee per gas: %s gwei',
        transaction.nonce,
        transaction.gas_limit,
        format_gwei(transaction.max_fee_per_gas),
        format_gwei(transaction.max_priority_fee_per_gas),
    )
    logger.info('Max fee: %s %s', format_ether(transaction.max_fee), coin_symbol)
    if args.dry_run:
        return json.dumps(
            {'txid': prepared.signed.hash, 'raw_transaction': prepared.signed.raw_hex}
        )
    return json.dumps({'txid': broadcast_transaction(rpc, prepared)})


def main():
    args = get_args()
    try:
        result = send_eth(args)
        if result is None:  # the error has been already logged
            return
        print(result)
    except (ValueError, InsufficientFundsError) as e:
        logger.error('Error: %s', e)


if __name__ == '__main__':
    main()
