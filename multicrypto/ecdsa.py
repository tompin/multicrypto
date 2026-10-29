import binascii
import hmac
from base64 import b64decode, b64encode
from hashlib import sha256
from struct import pack

from multicrypto.address import convert_public_key_to_coin_address, get_private_key_from_wif_format
from multicrypto.coins import P2PKH, P2SH_P2WPKH, P2TR, P2WPKH, get_address_types
from multicrypto.ellipticcurve import secp256k1, Point
from multicrypto.numbertheory import modular_inverse, modular_sqrt
from multicrypto.utils import double_sha256, int_to_varint

# First byte of the message signature (BIP-137) without the recovery id (0-3) of the public key
UNCOMPRESSED_P2PKH_HEADER = 27
SIGNATURE_HEADERS = {P2PKH: 31, P2SH_P2WPKH: 35, P2WPKH: 39}


def sign(message, private_key, curve=secp256k1, hash_function=sha256):
    hashed_message = hash_function(message).digest()
    int_hashed_message = int.from_bytes(hashed_message, byteorder='big')
    # generate a deterministic nonce according to RFC6979
    k = RFC6979(message, private_key, curve.n, hash_function).gen_nonce()
    rfc6979_point = curve.G * k
    r = rfc6979_point.x
    s = ((int_hashed_message + r * private_key) * modular_inverse(k, curve.n)) % curve.n
    return r, s


def sign_digest(digest: bytes, private_key: int, curve=secp256k1):
    """Sign the hash of a message (e.g. Keccak-256 in Ethereum), return r, s and the recovery id
    of the public key. The nonce is calculated like in libsecp256k1 (RFC6979 with HMAC-SHA256
    of the digest) and s is low (EIP-2), so signatures are the same as in other wallets."""
    k = RFC6979(None, private_key, curve.n, sha256).gen_nonce(digest)
    point = curve.G * k
    r = point.x % curve.n
    s = (int.from_bytes(digest, 'big') + r * private_key) * modular_inverse(k, curve.n) % curve.n
    if r == 0 or s == 0:  # probability below 2^-255
        raise ValueError('Cannot sign the digest')
    recid = (point.y & 1) | (2 if point.x >= curve.n else 0)
    if s > curve.n // 2:
        # the negated signature is valid for the point with the other y
        s = curve.n - s
        recid ^= 1
    return r, s, recid


def verify(message, signature, public_key, curve=secp256k1, hash_function=sha256):
    hashed_message = hash_function(message).digest()
    int_hashed_message = int.from_bytes(hashed_message, byteorder='big')
    r, s = signature
    w = modular_inverse(s, curve.n)
    U1 = curve.G * ((int_hashed_message * w) % curve.n)
    U2 = public_key * ((r * w) % curve.n)
    V = U1 + U2
    return r == V.x


def add_magic_prefix(message: str, coin) -> bytes:
    """Message with the prefix of the coin, serialized as it is hashed when it is signed."""
    name = coin.get('message_prefix', coin['name'].capitalize())
    prefix = f'{name} Signed Message:\n'.encode()
    data = message.encode()
    return int_to_varint(len(prefix)) + prefix + int_to_varint(len(data)) + data


def recover_public_key(digest: bytes, recid: int, r: int, s: int, curve=secp256k1):
    """Public key which signed the hash of a message, None when the signature has no key with
    the recovery id. Calculation is based on http://www.secg.org/sec1-v2.pdf chapter 4.1.6
    'Public Key Recovery Operation'."""
    x = r + (recid // 2) * curve.n
    if x >= curve.p:
        return None
    alpha = (x**3 + curve.a * x + curve.b) % curve.p
    beta = modular_sqrt(alpha, curve.p)
    if beta * beta % curve.p != alpha:
        return None
    y = beta if (beta - recid) % 2 == 0 else curve.p - beta
    R = Point(curve, x, y)
    e = int.from_bytes(digest, byteorder='big')
    return modular_inverse(r, curve.n) * (s * R - e * curve.G)


def _recover_public_key(message, recid, r, s, curve=secp256k1, hash_function=double_sha256):
    """Public key which signed the message, None when the signature has no key with the recovery
    id."""
    return recover_public_key(hash_function(message).digest(), recid, r, s, curve)


def sign_message(
    coin,
    message: str,
    wif_private_key: str,
    address_type: str = P2PKH,
    curve=secp256k1,
    hash_function=double_sha256,
) -> bytes:
    """Sign the message with the private key of the address (BIP-137), return base64 signature.
    The first byte of the signature tells the address type and the recovery id of the key."""
    if address_type == P2TR:
        raise ValueError('Taproot addresses cannot sign messages (BIP-137)')
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    public_key = curve.G * private_key
    # raises ValueError when the coin or the key does not support the address type
    convert_public_key_to_coin_address(public_key, coin, compressed, address_type)
    header = SIGNATURE_HEADERS[address_type] if compressed else UNCOMPRESSED_P2PKH_HEADER
    message_with_magic_prefix = add_magic_prefix(message, coin)
    r, s = sign(message_with_magic_prefix, private_key, curve, hash_function)
    signature = r.to_bytes(curve.bytes_size, byteorder='big') + s.to_bytes(
        curve.bytes_size, byteorder='big'
    )
    for recid in range(4):
        recovered = _recover_public_key(
            message_with_magic_prefix, recid, r, s, curve, hash_function
        )
        if recovered is not None and recovered == public_key:
            return b64encode(bytes([header + recid]) + signature)
    raise ValueError('Cannot sign the message')


def verify_signature(
    coin, message: str, signature: str, address: str, curve=secp256k1, hash_function=double_sha256
) -> bool:
    """Check the base64 signature (BIP-137) of the message made with the key of the address.
    The address can have any type of the recovered key, since some wallets (Electrum, Trezor)
    sign messages of segwit addresses with the header of P2PKH address."""
    try:
        data = b64decode(signature.strip(), validate=True)
    except binascii.Error:
        raise ValueError('Signature is not correct base64') from None
    size = 1 + 2 * curve.bytes_size
    if len(data) != size:
        raise ValueError(f'Signature must have {size} bytes, it has {len(data)}')
    header = data[0]
    if not UNCOMPRESSED_P2PKH_HEADER <= header < SIGNATURE_HEADERS[P2WPKH] + 4:
        raise ValueError(f'Incorrect first byte of the signature: {header}')
    compressed = header >= SIGNATURE_HEADERS[P2PKH]
    recid = (header - UNCOMPRESSED_P2PKH_HEADER) % 4
    r = int.from_bytes(data[1 : 1 + curve.bytes_size], byteorder='big')
    s = int.from_bytes(data[1 + curve.bytes_size :], byteorder='big')
    if not (0 < r < curve.n and 0 < s < curve.n):
        return False
    public_key = _recover_public_key(
        add_magic_prefix(message, coin), recid, r, s, curve, hash_function
    )
    if public_key is None:
        return False
    if compressed:
        address_types = [type_ for type_ in get_address_types(coin) if type_ != P2TR]
    else:
        address_types = [P2PKH]
    return any(
        convert_public_key_to_coin_address(public_key, coin, compressed, address_type) == address
        for address_type in address_types
    )


class RFC6979:
    """Nonce calculation as defined in RFC6979.

    Reusing a nonce with the same key when signing two different messages leaks
    the private key. RFC6979 provides a deterministic method for generating nonces.
    This is based on using a pseudo-random function (HMAC) to derive a nonce from
    the message and private key. More info here: http://tools.ietf.org/html/rfc6979.
    """

    def __init__(self, message, private_key, n, hash_function):
        """
        :param message: Message to sign
        :param private_key: Private key
        :param n: Order of the generator point
        :param hash_function: Hash function used to compress the message
        """
        self.private_key = private_key
        self.n = n
        self.message = message
        self.n_bit_length = len(bin(n)) - 2
        self.n_byte_length = (self.n_bit_length + 7) // 8
        self.hash_function = hash_function

    def bits2int(self, b):
        """http://tools.ietf.org/html/rfc6979#section-2.3.2"""
        b_int_value = int.from_bytes(b, byteorder='big')
        b_bit_length = len(b) * 8
        if b_bit_length > self.n_bit_length:
            b_int_value >>= b_bit_length - self.n_bit_length
        return b_int_value

    def int2octets(self, x):
        """http://tools.ietf.org/html/rfc6979#section-2.3.3"""
        octets = b''
        while x > 0:
            octets = pack('=B', (0xFF & x)) + octets
            x >>= 8
        padding = b'\x00' * (self.n_byte_length - len(octets))
        return padding + octets

    def bits2octets(self, b):
        """http://tools.ietf.org/html/rfc6979#section-2.3.4"""
        z1 = self.bits2int(b)
        z2 = z1 % self.n
        return self.int2octets(z2)

    def gen_nonce(self, h1=None):
        """http://tools.ietf.org/html/rfc6979#section-3.2, h1 is the hash of the message
        when it is already calculated"""
        if h1 is None:
            h1 = self.hash_function(self.message).digest()
        hash_size = len(h1)
        key_and_msg = self.int2octets(self.private_key) + self.bits2octets(h1)
        v = b'\x01' * hash_size
        k = b'\x00' * hash_size
        k = hmac.new(k, v + b'\x00' + key_and_msg, self.hash_function).digest()
        v = hmac.new(k, v, self.hash_function).digest()
        k = hmac.new(k, v + b'\x01' + key_and_msg, self.hash_function).digest()
        v = hmac.new(k, v, self.hash_function).digest()
        while True:
            t = b''
            while len(t) * 8 < self.n_bit_length:
                v = hmac.new(k, v, self.hash_function).digest()
                t += v
            nonce = self.bits2int(t)
            if 1 <= nonce < self.n:
                return nonce
            k = hmac.new(k, v + b'\x00', self.hash_function).digest()
            v = hmac.new(k, v, self.hash_function).digest()
