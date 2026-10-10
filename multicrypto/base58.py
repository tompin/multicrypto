from multicrypto.utils import int_to_bytes

BASE58_ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
BASE58_DIGITS_VALUES = {digit: value for value, digit in enumerate(BASE58_ALPHABET)}


def bytes_to_base58(bytes_data):
    bytes_data_without_leading_zeros = bytes_data.lstrip(b'\x00')
    leading_zeros = len(bytes_data) - len(bytes_data_without_leading_zeros)
    value = int.from_bytes(bytes_data_without_leading_zeros, byteorder='big')
    result = []
    while value > 0:
        value, remainder = divmod(value, 58)
        result.append(BASE58_ALPHABET[remainder])
    return '1' * leading_zeros + ''.join(reversed(result))


def base58_to_bytes(base58_data):
    data_without_leading_ones = base58_data.lstrip('1')
    value = 0
    for digit in data_without_leading_ones:
        value = value * 58 + BASE58_DIGITS_VALUES[digit]
    leading_zeros = b'\x00' * (len(base58_data) - len(data_without_leading_ones))
    return leading_zeros + int_to_bytes(value, byteorder='big')


def base58_to_int(base58_data):
    value = 0
    for digit in base58_data:
        value = value * 58 + BASE58_DIGITS_VALUES[digit]
    return value


def validate_base58(string):
    invalid_characters = set(string) - set(BASE58_ALPHABET)
    if invalid_characters:
        raise ValueError(
            f'pattern {string} contains not allowed characters: '
            f'{"".join(sorted(invalid_characters))}'
        )
    return True
