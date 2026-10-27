from multicrypto.ellipticcurve import secp256k1

from multicrypto.base58 import (
    bytes_to_base58,
    base58_to_int,
    base58_to_bytes,
    validate_base58,
    BASE58_ALPHABET,
)
from multicrypto.bech32 import decode, encode
from multicrypto.coins import (
    ADDRESS_TYPES,
    P2PKH,
    P2SH_P2WPKH,
    P2TR,
    coins,
    get_address_types,
)
from multicrypto.schnorr import taproot_output_key
from multicrypto.utils import double_sha256, encode_point, hash160

G = secp256k1.G  # generator point


def convert_private_key_to_address(private_key, addr_prefix_bytes, compressed=True, segwit=False):
    public_key = G * private_key
    return convert_public_key_to_address(public_key, addr_prefix_bytes, compressed, segwit)


def convert_wif_private_key_to_address(wif_private_key, address_prefix_bytes, segwit=False):
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    address = convert_private_key_to_address(private_key, address_prefix_bytes, compressed, segwit)
    return address


def validate_address_type(address_type, coin):
    if address_type not in ADDRESS_TYPES:
        raise ValueError(f'Unknown address type {address_type}, choose one of {ADDRESS_TYPES}')
    supported_types = get_address_types(coin)
    if address_type not in supported_types:
        raise ValueError(
            f'Address type {address_type} is not supported for {coin["name"]}, '
            f'supported types: {", ".join(supported_types)}'
        )


def convert_public_key_to_coin_address(public_key, coin, compressed=True, address_type=P2PKH):
    """Calculate address of the given type for the public key. P2TR is not supported, its output
    key is calculated from the private key (taproot_output_key)."""
    validate_address_type(address_type, coin)
    if address_type == P2TR:
        raise ValueError('Taproot address cannot be calculated from the public key')
    if address_type == P2PKH:
        return convert_public_key_to_address(public_key, coin['address_prefix_bytes'], compressed)
    if not compressed:
        raise ValueError('Segwit addresses require compressed public key')
    if address_type == P2SH_P2WPKH:
        return convert_public_key_to_address(public_key, coin['script_prefix_bytes'], segwit=True)
    return encode(coin['bech32_hrp'], 0, calculate_public_key_hash(public_key))


def convert_private_key_to_coin_address(private_key, coin, compressed=True, address_type=P2PKH):
    """Calculate address of the given type (one of ADDRESS_TYPES) for the private key."""
    validate_address_type(address_type, coin)
    if address_type == P2TR:
        if not compressed:
            raise ValueError('Segwit addresses require compressed public key')
        return encode(coin['bech32_hrp'], 1, taproot_output_key(private_key))
    return convert_public_key_to_coin_address(G * private_key, coin, compressed, address_type)


def calculate_address(digest, address_prefix_bytes):
    input_data = address_prefix_bytes + digest
    check_sum = double_sha256(input_data).digest()[:4]
    address = bytes_to_base58(input_data + check_sum)
    return address


def decompose_address(address, coin):
    """Decompose address to address prefix bytes and address digest"""
    address_data = base58_to_bytes(address)
    input_data = address_data[:-4]
    address_prefix = coin['address_prefix_bytes']
    script_prefix = coin['script_prefix_bytes']
    if not input_data.startswith(address_prefix) and not input_data.startswith(script_prefix):
        raise Exception('Incorrect address prefix')
    prefix = input_data[: len(address_prefix)]
    digest = input_data[len(address_prefix) :]
    return prefix, digest


def calculate_public_key_hash(public_key, compressed=True, segwit=False):
    encoded_public_key = encode_point(public_key, compressed)
    digest = hash160(encoded_public_key)
    if segwit:
        redeem_script = b'\x00\x14' + digest
        digest = hash160(redeem_script)
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


def translate_address(address, input_address_prefix_bytes, output_address_prefix_bytes):
    bytes_address = base58_to_bytes(address)
    digest = bytes_address[len(input_address_prefix_bytes) : -4]
    return calculate_address(digest, output_address_prefix_bytes)


def bech32_address(coin_symbol, legacy_address):
    coin = coins[coin_symbol]
    bytes_address = base58_to_bytes(legacy_address)
    digest = bytes_address[len(coin['address_prefix_bytes']) : -4]
    return encode(coin['bech32_hrp'], coin.get('witness_version', 0), digest)


def segwit_scriptpubkey(witver, witprog):
    """Create a segwit locking script for a given witness program (P2WPKH, P2WSH, P2TR)."""
    return bytes([witver + 0x50 if witver else 0, len(witprog)] + list(witprog))


def decode_segwit_address(address, coin):
    """Return (witness version, witness program) for bech32 address of the coin or None."""
    hrp = coin.get('bech32_hrp')
    if not hrp:
        return None
    witver, witprog = decode(hrp, address)
    if witver is None:
        return None
    return witver, witprog


def is_segwit_address(address, coin):
    hrp = coin.get('bech32_hrp')
    return bool(hrp) and address.lower().startswith(hrp + '1')


def translate_private_key(private_key_wif_format, output_private_key_prefix_bytes):
    private_key, is_compressed = get_private_key_from_wif_format(private_key_wif_format)
    return convert_private_key_to_wif_format(
        private_key, output_private_key_prefix_bytes, is_compressed
    )


def get_address_range(address_prefix_bytes):
    low_threshold = address_prefix_bytes + b'\x00' * 24
    high_threshold = address_prefix_bytes + b'\xff' * 24
    start_address = bytes_to_base58(low_threshold)
    end_address = bytes_to_base58(high_threshold)
    return start_address, end_address


def validate_pattern(pattern, coin_symbol, is_script):
    validate_base58(pattern)
    if is_script:
        start_address, end_address = get_address_range(coins[coin_symbol]['script_prefix_bytes'])
    else:
        start_address, end_address = get_address_range(coins[coin_symbol]['address_prefix_bytes'])
    if not start_address[: len(pattern)] <= pattern <= end_address[: len(pattern)]:
        raise ValueError(
            f'Impossible prefix! Choose different one from {start_address}-{end_address} range'
            f'(characters order is {BASE58_ALPHABET})'
        )
    return True


def validate_address(address, coin_symbol):
    coin = coins[coin_symbol]
    if is_segwit_address(address, coin):
        if decode_segwit_address(address, coin) is None:
            raise ValueError('Incorrect bech32 address')
        return True
    address_bytes = base58_to_bytes(address)
    prefix_bytes, _ = decompose_address(address, coin)
    if not address_bytes.startswith(prefix_bytes):
        raise ValueError('Address prefix is not correct for this coin')
    if len(address_bytes) > len(prefix_bytes) + 24:
        raise ValueError('Too many characters in address')
    if len(address_bytes) < len(prefix_bytes) + 24:
        raise ValueError('Too little characters in address')
    check_sum = address_bytes[-4:]
    calculated_check_sum = double_sha256(address_bytes[:-4]).digest()[:4]
    if check_sum != calculated_check_sum:
        raise ValueError('Check sum is not correct')
    return validate_pattern(address, coin_symbol, prefix_bytes == coin['script_prefix_bytes'])


def detect_address_kind(address, coin_symbol):
    """Return 'p2pkh' or 'p2sh' for the base58 address of the coin. Bech32 addresses cannot be
    translated to another coin without the private key."""
    coin = coins[coin_symbol]
    if is_segwit_address(address, coin):
        raise ValueError(
            'Bech32 (segwit) addresses cannot be translated, they need the private key'
        )
    validate_address(address, coin_symbol)
    prefix, _ = decompose_address(address, coin)
    return 'p2sh' if prefix == coin['script_prefix_bytes'] else 'p2pkh'


def validate_wif_private_key(wif_private_key, coin_symbol):
    private_key_data = base58_to_int(wif_private_key)
    private_key_bytes = private_key_data.to_bytes(38, byteorder='big')
    compressed = private_key_bytes[0] != 0 and private_key_bytes[-5] == 1
    if compressed:
        secret_prefix_bytes = private_key_bytes[0:1]
    else:
        secret_prefix_bytes = private_key_bytes[1:2]
    if secret_prefix_bytes != coins[coin_symbol]['secret_prefix_bytes']:
        raise ValueError(
            f'Incorrect secret prefix 0x{secret_prefix_bytes.hex()} in wif private key '
            f'for coin {coin_symbol}'
        )
    return True
