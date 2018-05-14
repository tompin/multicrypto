def int_to_bytes(integer, byteorder):
    return integer.to_bytes((integer.bit_length() + 7) // 8, byteorder=byteorder)


def hex_to_bytes(hex_value, byteorder):
    if len(hex_value) % 2 == 1:
        hex_value = '0' + hex_value
    bytes_value = bytes.fromhex(hex_value)
    if byteorder == 'little':
        bytes_value = bytes_value[::-1]
    return bytes_value
