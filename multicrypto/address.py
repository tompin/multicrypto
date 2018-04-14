import hashlib

from fastecdsa.curve import secp256k1
from multicrypto.coins import coins

from multicrypto.base58 import bytes_to_base58, base58_to_int, base58_to_bytes, validate_base58

G = secp256k1.G  # generator point
N = secp256k1.q  # order of the curve


# Calculations are based on https://en.bitcoin.it/w/images/en/9/9b/PubKeyToAddr.png

def double_sha256(input_data):
    return hashlib.sha256(hashlib.sha256(input_data).digest()).digest()


def get_encoded_point(point, compressed):
    if compressed:
        return bytes([2 + (point.y % 2)]) + point.x.to_bytes(32, byteorder='big')
    else:
        return b'\x04' + point.x.to_bytes(32, byteorder='big') + \
               point.y.to_bytes(32, byteorder='big')


def convert_private_key_to_address(private_key, address_prefix_bytes, compressed=True):
    public_key = G * private_key
    return convert_public_key_to_addres(public_key, address_prefix_bytes, compressed)


def calculate_address(digest, address_prefix_bytes):
    input_data = address_prefix_bytes + digest
    check_sum = double_sha256(input_data)[:4]
    return bytes_to_base58(input_data + check_sum)


def convert_public_key_to_addres(public_key, address_prefix_bytes, compressed=True, segwit=False):
    encoded_public_key = get_encoded_point(public_key, compressed)
    hashed_public_key = hashlib.sha256(encoded_public_key).digest()
    digest = hashlib.new('ripemd160', hashed_public_key).digest()
    if segwit:
        redeem_script = b'\x00\x14' + digest
        hashed_script = hashlib.sha256(redeem_script).digest()
        digest = hashlib.new('ripemd160', hashed_script).digest()
    return calculate_address(digest, address_prefix_bytes)


def convert_private_key_to_wif_format(private_key, secret_prefix_bytes, compressed=True):
    bin_private_key = private_key.to_bytes(32, byteorder='big')
    input_data = secret_prefix_bytes + bin_private_key
    if compressed:
        input_data += b'\x01'
    check_sum = double_sha256(input_data)[:4]
    return bytes_to_base58(input_data + check_sum)


def get_private_key_from_wif_format(wif_private_key):
    private_key_data = base58_to_int(wif_private_key)
    private_key_bytes = private_key_data.to_bytes(38, byteorder='big')
    # Removing magic byte and check sum
    if private_key_bytes[0] == 0:
        was_compressed = False
        private_key_bytes = private_key_bytes[2:-4]  # not compressed wif
    else:
        was_compressed = True
        private_key_bytes = private_key_bytes[1:-5]  # compressed wif
    return int.from_bytes(private_key_bytes, byteorder='big'), was_compressed


def validate_pattern(pattern, coin, script):
    validate_base58(pattern)
    if script:
        start_address, end_address = get_address_range(coins[coin]['script_prefix_bytes'])
    else:
        start_address, end_address = get_address_range(coins[coin]['address_prefix_bytes'])
    if not (start_address[:len(pattern)] <= pattern <= end_address[:len(pattern)]):
        raise Exception('Impossible prefix! Choose different one from {}-{} range.'.format(
            start_address, end_address))
    return True


def validate_address(address, coin, script):
    address_bytes = base58_to_bytes(address)
    if script:
        prefix_bytes = coins[coin]['script_prefix_bytes']
    else:
        prefix_bytes = coins[coin]['address_prefix_bytes']
    if not address_bytes.startswith(prefix_bytes):
        raise Exception('Address prefix is not correct for this coin')
    if len(address_bytes) > len(prefix_bytes) + 24:
        raise Exception('Too many characters in address')
    elif len(address_bytes) < len(prefix_bytes) + 24:
        raise Exception('Too little characters in address')
    check_sum = address_bytes[-4:]
    calculated_check_sum = double_sha256(address_bytes[:-4])
    if check_sum != calculated_check_sum:
        raise Exception('Check sum is not correct')
    return validate_pattern(address, coin, script)


def translate_address(address, input_address_prefix_bytes, output_address_prefix_bytes):
    bytes_address = base58_to_bytes(address)
    digest = bytes_address[len(input_address_prefix_bytes):-4]
    return calculate_address(digest, output_address_prefix_bytes)


def translate_private_key(private_key_wif_format, output_private_key_prefix_bytes):
    private_key, is_compressed = get_private_key_from_wif_format(private_key_wif_format)
    return convert_private_key_to_wif_format(
        private_key, output_private_key_prefix_bytes, is_compressed)


def get_address_range(address_prefix_bytes):
    low_threshold = address_prefix_bytes + b'\x00' * 24
    high_threshold = address_prefix_bytes + b'\xff' * 24
    start_address = bytes_to_base58(low_threshold)
    end_address = bytes_to_base58(high_threshold)
    return start_address, end_address
