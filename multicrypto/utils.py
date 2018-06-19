import argparse
import hashlib
from binascii import unhexlify

from fastecdsa.curve import secp256k1


def int_to_bytes(integer, byteorder):
    return integer.to_bytes((integer.bit_length() + 7) // 8, byteorder=byteorder)


def hex_to_bytes(hex_value, byteorder):
    if len(hex_value) % 2 == 1:
        hex_value = '0' + hex_value
    bytes_value = bytes.fromhex(hex_value)
    if byteorder == 'little':
        return bytes_value[::-1]
    else:
        return bytes_value


def double_sha256(input_data):
    return hashlib.sha256(hashlib.sha256(input_data).digest())


def double_sha256_hex(hex_str=b''):
    hex_str = hex_str.decode()
    input_data = hex_to_bytes(hex_str, byteorder='big')
    return double_sha256(input_data)


def int_to_varint_hex(int_value):
    """
    VARINT
    <= 0xfc	                  example: 12
    <= 0xffff                 example: fd1234
       Prefix is fd and the next 2 bytes are the VarInt (in little-endian).
    <= 0xffffffff             example: fe12345678
       Prefix is fe and the next 4 bytes are the VarInt (in little-endian).
    <= 0xffffffffffffffff     example: ff1234567890abcdef
       Prefix is ff and the next 8 bytes are the VarInt (in little-endian).

    :param int_value: integer value which we want to convert to hex format varint
    :return: varint hex string in little-endian
    """
    if int_value <= 0xfc:
        return hex(int_value)[2:]
    elif int_value <= 0xffff:
        return 'fd' + int_value.to_bytes(2, byteorder='little').hex()
    elif int_value <= 0xffffffff:
        return 'fe' + int_value.to_bytes(4, byteorder='little').hex()
    elif int_value <= 0xffffffffffffffff:
        return 'ff' + int_value.to_bytes(8, byteorder='little').hex()
    else:
        raise Exception('Too big varint: {}'.format(int_value))


def der_encode_signature(signature):
    """
    Serializing EC signature using DER.

    :param signature: Tuple (r, s) containing integers returned from fastecdsa.ecdsa.sign
    which signs message using elliptic curve digital signature algorithm
    :return: DER encoded signature
    """
    der_sequence = b'\x30'
    der_int = b'\x02'
    r, s = signature

    # BIP 66 additional rules
    if s > secp256k1.q / 2:
        s = secp256k1.q - s
    r_bytes = int_to_bytes(r, byteorder='big')
    s_bytes = int_to_bytes(s, byteorder='big')
    if r_bytes[0] & 0x80:
        r_bytes = b'\x00' + r_bytes
    if s_bytes[0] & 0x80:
        s_bytes = b'\x00' + s_bytes

    r_der_encoded = der_int + int_to_bytes(len(r_bytes), byteorder='big') + r_bytes
    s_der_encoded = der_int + int_to_bytes(len(s_bytes), byteorder='big') + s_bytes
    sequence = r_der_encoded + s_der_encoded
    sequence_length = int_to_bytes(len(sequence), byteorder='big')
    der_encoded_signature = der_sequence + sequence_length + sequence

    return der_encoded_signature


def reverse_byte_hex(hex_str):
    """
    Reverse the bytes represented by the hex_str and returns them in hex format

    :param hex_str: Bytes in hex format that we want to reverse
    :return: Reversed bytes in hex format
    """
    byte_str = unhexlify(hex_str)
    reversed_byte_str = byte_str[::-1]
    reversed_hex_str = reversed_byte_str.hex()
    return reversed_hex_str


def check_positive(value):
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError("%s is an invalid positive int value" % value)
    return ivalue
