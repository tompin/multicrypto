import argparse

from multicrypto.coins import coins


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


def check_coin_symbol(coin_symbol):
    coin_symbol = coin_symbol.upper()
    if coin_symbol not in coins:
        raise argparse.ArgumentTypeError(f'{coin_symbol} is not supported coin symbol')
    return coin_symbol
