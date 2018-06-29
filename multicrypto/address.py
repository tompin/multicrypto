import hashlib

from fastecdsa.curve import secp256k1

from multicrypto.base58 import bytes_to_base58, base58_to_int, base58_to_bytes, validate_base58, \
    base58
from multicrypto.coins import coins
from multicrypto.utils import double_sha256, encode_point

G = secp256k1.G  # generator point


def convert_private_key_to_address(private_key, address_prefix_bytes, compressed=True):
    public_key = G * private_key
    return convert_public_key_to_address(public_key, address_prefix_bytes, compressed)


def convert_wif_private_key_to_address(wif_private_key, address_prefix_bytes):
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    address = convert_private_key_to_address(private_key, address_prefix_bytes, compressed)
    return address


def calculate_address(digest, address_prefix_bytes):
    input_data = address_prefix_bytes + digest
    check_sum = double_sha256(input_data).digest()[:4]
    address = bytes_to_base58(input_data + check_sum)
    return address


def get_public_key_hash(address, address_prefix_bytes):
    address_data = base58_to_bytes(address)
    input_data = address_data[:-4]
    if not input_data.startswith(address_prefix_bytes):
        raise Exception('Incorrect address prefix')
    digest = input_data[len(address_prefix_bytes):]
    return digest


def calculate_public_key_hash(public_key, compressed=True, segwit=False):
    encoded_public_key = encode_point(public_key, compressed)
    hashed_public_key = hashlib.sha256(encoded_public_key).digest()
    digest = hashlib.new('ripemd160', hashed_public_key).digest()
    if segwit:
        redeem_script = b'\x00\x14' + digest
        hashed_script = hashlib.sha256(redeem_script).digest()
        digest = hashlib.new('ripemd160', hashed_script).digest()
    return digest


def convert_public_key_to_address(public_key, address_prefix_bytes, compressed=True, segwit=False):
    digest = calculate_public_key_hash(public_key, compressed, segwit)
    return calculate_address(digest, address_prefix_bytes)


def convert_private_key_to_wif_format(private_key, secret_prefix_bytes, compressed=True):
    bin_private_key = private_key.to_bytes(32, byteorder='big')
    input_data = secret_prefix_bytes + bin_private_key
    if compressed:
        input_data += b'\x01'
    check_sum = double_sha256(input_data).digest()[:4]
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


def validate_pattern(pattern, coin_symbol, is_script):
    validate_base58(pattern)
    if is_script:
        start_address, end_address = get_address_range(coins[coin_symbol]['script_prefix_bytes'])
    else:
        start_address, end_address = get_address_range(coins[coin_symbol]['address_prefix_bytes'])
    if not (start_address[:len(pattern)] <= pattern <= end_address[:len(pattern)]):
        raise Exception('Impossible prefix! Choose different one from {}-{} range'
                        '(characters order is {})'.format(start_address, end_address, base58))
    return True


def get_address_prefix_bytes(address_bytes, coin):
    if address_bytes.startswith(coin['script_prefix_bytes']):
        return coin['script_prefix_bytes']
    elif address_bytes.startswith(coin['address_prefix_bytes']):
        return coin['address_prefix_bytes']
    raise Exception('Incorrect address prefix bytes for {}'.format(coin['name']))


def validate_address(address, coin_symbol, address_type=None):
    address_bytes = base58_to_bytes(address)
    coin = coins[coin_symbol]
    if address_type == 'p2sh':
        prefix_bytes = coin['script_prefix_bytes']
    elif address_type == 'p2pkh':
        prefix_bytes = coin['address_prefix_bytes']
    elif address_type is None:
        prefix_bytes = get_address_prefix_bytes(address_bytes, coin)
    else:
        raise Exception('Unrecognized address_type value')
    if not address_bytes.startswith(prefix_bytes):
        raise Exception('Address prefix is not correct for this coin')
    if len(address_bytes) > len(prefix_bytes) + 24:
        raise Exception('Too many characters in address')
    elif len(address_bytes) < len(prefix_bytes) + 24:
        raise Exception('Too little characters in address')
    check_sum = address_bytes[-4:]
    calculated_check_sum = double_sha256(address_bytes[:-4]).digest()[:4]
    if check_sum != calculated_check_sum:
        raise Exception('Check sum is not correct')
    return validate_pattern(address, coin_symbol, address_type == 'p2sh')


def validate_wif_private_key(wif_private_key, coin_symbol):
    private_key_data = base58_to_int(wif_private_key)
    private_key_bytes = private_key_data.to_bytes(38, byteorder='big')
    compressed = private_key_bytes[0] != 0 and private_key_bytes[-5] == 1
    if compressed:
        secret_prefix_bytes = private_key_bytes[0:1]
    else:
        secret_prefix_bytes = private_key_bytes[1:2]
    if secret_prefix_bytes != coins[coin_symbol]['secret_prefix_bytes']:
        raise Exception('Incorrect secret prefix 0x{} in wif private key for coin {}'.format(
            secret_prefix_bytes.hex(), coin_symbol))
    return True


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
