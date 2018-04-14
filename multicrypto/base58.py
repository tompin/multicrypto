base58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
base58_digits_values = {digit: value for value, digit in enumerate(base58)}


def bytes_to_base58(bytes_data):
    bytes_data_without_leading_zeros = bytes_data.lstrip(b'\x00')
    leading_zeros = len(bytes_data) - len(bytes_data_without_leading_zeros)
    value = int.from_bytes(bytes_data_without_leading_zeros, byteorder='big')
    result = ''
    while value > 0:
        value, remainder = divmod(value, 58)
        result = base58[remainder] + result
    return '1' * leading_zeros + result


def base58_to_bytes(base58_data):
    data_without_leading_ones = base58_data.lstrip('1')
    value = 0
    for digit in data_without_leading_ones:
        value *= 58
        value += base58_digits_values[digit]
    leading_zeros = b'\x00' * (len(base58_data) - len(data_without_leading_ones))
    return leading_zeros + value.to_bytes((value.bit_length() + 7) // 8, byteorder='big')


def base58_to_int(base58_data):
    result = 0
    for digit in base58_data:
        result *= 58
        result += base58_digits_values[digit]
    return result


def validate_base58(string):
    invalid_characters = set(string) - set(base58_digits_values)
    if invalid_characters:
        raise Exception('pattern {} contains not allowed characters: {}'.format(
            string, ''.join(sorted(invalid_characters))
        ))
    return True
