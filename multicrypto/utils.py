import hashlib
from binascii import unhexlify

import qrcode

from multicrypto.ellipticcurve import Point, secp256k1
from multicrypto.numbertheory import modular_sqrt


def decode_point(encoded_point, curve=secp256k1):
    if isinstance(encoded_point, bytes):
        encoded_point = encoded_point.hex()
    if len(encoded_point) == 130:  # uncompressed
        x = int(encoded_point[2:66], 16)
        y = int(encoded_point[66:130], 16)
        return Point(curve=curve, x=x, y=y)
    elif len(encoded_point) == 66:  # compressed
        x = int(encoded_point[2:66], 16)
        beta = modular_sqrt(x**3 + curve.a * x + curve.b, curve.p)
        if (beta + int(encoded_point[:2], 16)) % 2:
            y = curve.p - beta
        else:
            y = beta
        return Point(curve=curve, x=x, y=y)
    else:
        raise Exception('Unrecognized point format')


def encode_point(point, compressed, output_format='bytes'):
    if compressed:
        encoded_point = bytes([2 + (point.y % 2)]) + point.x.to_bytes(32, byteorder='big')
    else:
        encoded_point = b'\x04' + point.x.to_bytes(32, byteorder='big') + \
            point.y.to_bytes(32, byteorder='big')
    if output_format == 'hex':
        return encoded_point.hex()
    else:
        return encoded_point


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


def double_sha256(input_data=b''):
    return hashlib.sha256(hashlib.sha256(input_data).digest())


def hash160(input_data):
    hash_sha256 = hashlib.sha256(input_data).digest()
    digest = hashlib.new('ripemd160', hash_sha256).digest()
    return digest


def encode_script(script):
    return int_to_bytes(len(script), byteorder='little') + script


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

    :param signature: Tuple (r, s) containing integers returned from ECDSA sign
    function, which signs message, using elliptic curve digital signature algorithm
    :return: DER encoded signature
    """
    der_sequence = b'\x30'
    der_int = b'\x02'
    r, s = signature

    # BIP 66 additional rules
    if s > secp256k1.n / 2:
        s = secp256k1.n - s
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


def get_integer(string):
    if {'a', 'b', 'c', 'd', 'e', 'f', 'x'} & set(string):
        try:
            return int(string, 16)
        except ValueError:
            return None
    else:
        try:
            return int(string)
        except ValueError:
            return None


def get_qrcode_image(string, error_correct='low'):
    if error_correct == 'low':
        error_correct = qrcode.constants.ERROR_CORRECT_L
    elif error_correct == 'high':
        error_correct = qrcode.constants.ERROR_CORRECT_H
    qr = qrcode.QRCode(
        version=1,
        error_correction=error_correct,
        box_size=10,
        border=4)
    qr.add_data(string)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    return image
