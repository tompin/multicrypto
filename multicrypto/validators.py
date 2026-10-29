import argparse

from multicrypto.coins import coins, ethereum_coins


def check_positive(value):
    int_value = int(value)
    if int_value <= 0:
        raise argparse.ArgumentTypeError(f'{value} is an invalid positive int value')
    return int_value


def check_non_negative(value):
    int_value = int(value)
    if int_value < 0:
        raise argparse.ArgumentTypeError(f'{value} is an invalid non negative int value')
    return int_value


def check_positive_number(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'{value} is an invalid number') from None
    if not number > 0:
        raise argparse.ArgumentTypeError(f'{value} is an invalid positive number')
    return number


def check_coin_symbol(coin_symbol):
    coin_symbol = coin_symbol.upper()
    if coin_symbol not in coins:
        raise argparse.ArgumentTypeError(f'{coin_symbol} is not supported coin symbol')
    return coin_symbol


def check_ethereum_coin_symbol(coin_symbol):
    coin_symbol = coin_symbol.upper()
    if coin_symbol not in ethereum_coins:
        raise argparse.ArgumentTypeError(
            f'{coin_symbol} is not supported, choose one of {", ".join(ethereum_coins)}'
        )
    return coin_symbol


def check_any_coin_symbol(coin_symbol):
    """Symbol of a coin with unspent outputs or of an Ethereum coin."""
    if coin_symbol.upper() in ethereum_coins:
        return coin_symbol.upper()
    return check_coin_symbol(coin_symbol)
