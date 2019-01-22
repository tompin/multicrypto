from base64 import b64encode
from hashlib import sha256
from struct import pack
import hmac

from multicrypto.address import get_private_key_from_wif_format, \
    convert_wif_private_key_to_address, convert_public_key_to_address
from multicrypto.ellipticcurve import secp256k1, Point
from multicrypto.numbertheory import modular_inverse, modular_sqrt
from multicrypto.utils import double_sha256


def sign(message, private_key, curve=secp256k1, hash_function=sha256):
    hashed_message = hash_function(message).digest()
    int_hashed_message = int.from_bytes(hashed_message, byteorder='big')
    # generate a deterministic nonce according to RFC6979
    rfc6979 = RFC6979(message, private_key, curve.n, hash_function)
    k = rfc6979.gen_nonce()
    rfc6979_point = curve.G * k
    r = rfc6979_point.x
    s = ((int_hashed_message + r * private_key) * modular_inverse(k, curve.n)) % curve.n
    return r, s


def verify(message, signature, public_key, curve=secp256k1, hash_function=sha256):
    hashed_message = hash_function(message).digest()
    int_hashed_message = int.from_bytes(hashed_message, byteorder='big')
    r, s = signature
    w = modular_inverse(s, curve.n)
    U1 = curve.G * ((int_hashed_message * w) % curve.n)
    U2 = public_key * ((r * w) % curve.n)
    V = U1 + U2
    return r == V.x


def add_magic_prefix(message, coin):
    return '\x18{coin_name} Signed Message:\n{message_length}{message}'.format(
        coin_name=coin['name'].capitalize(), message_length=chr(len(message)), message=message)


def verify_message(
        coin, message, v, signature, address, curve=secp256k1, hash_function=double_sha256):
    r, s = signature
    if v < 27 or v >= 35:
        return False
    if v >= 31:
        compressed = True
        v -= 4
    else:
        compressed = False
    recid = v - 27

    # Calculation is based on http://www.secg.org/sec1-v2.pdf
    # chapter 4.1.6 'Public Key Recovery Operation'.
    x = r + (recid // 2) * curve.n
    alpha = (x ** 3 + curve.a * x + curve.b) % curve.p
    beta = modular_sqrt(alpha, curve.p)
    y = beta if (beta - recid) % 2 == 0 else curve.p - beta
    R = Point(curve, x, y)
    h = hash_function(message).digest()
    e = int.from_bytes(h, byteorder='big')
    Q = modular_inverse(r, curve.n) * (s * R - e * curve.G)
    public_key = Q
    calculated_address = convert_public_key_to_address(
        public_key, coin['address_prefix_bytes'], compressed)
    if calculated_address == address:
        return True
    else:
        return False


def sign_message(
        coin, message, wif_private_key, segwit=False, curve=secp256k1, hash_function=double_sha256):
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    address = convert_wif_private_key_to_address(
        wif_private_key, coin['address_prefix_bytes'], segwit=segwit)
    message_with_magic_prefix = add_magic_prefix(message, coin).encode()
    r, s = sign(message_with_magic_prefix, private_key, curve, hash_function)
    bytes_signature = (r.to_bytes(byteorder='big', length=curve.bytes_size) +
                       s.to_bytes(byteorder='big', length=curve.bytes_size))
    v = 27
    if compressed:
        v += 4
    for i in range(4):
        v += i
        if verify_message(
                coin, message_with_magic_prefix, v, (r, s), address, curve, hash_function):
            return b64encode(v.to_bytes(byteorder='big', length=1) + bytes_signature)
    else:
        raise BaseException("error: cannot sign message")


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
        """ http://tools.ietf.org/html/rfc6979#section-2.3.2 """
        b_int_value = int.from_bytes(b, byteorder='big')
        b_bit_length = len(b) * 8
        if b_bit_length > self.n_bit_length:
            b_int_value >>= (b_bit_length - self.n_bit_length)
        return b_int_value

    def int2octets(self, x):
        """ http://tools.ietf.org/html/rfc6979#section-2.3.3 """
        octets = b''
        while x > 0:
            octets = pack('=B', (0xff & x)) + octets
            x >>= 8
        padding = b'\x00' * (self.n_byte_length - len(octets))
        return padding + octets

    def bits2octets(self, b):
        """ http://tools.ietf.org/html/rfc6979#section-2.3.4 """
        z1 = self.bits2int(b)
        z2 = z1 % self.n
        return self.int2octets(z2)

    def gen_nonce(self):
        """ http://tools.ietf.org/html/rfc6979#section-3.2 """
        h1 = self.hash_function(self.message)
        hash_size = h1.digest_size
        h1 = h1.digest()
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
                t = t + v
            nonce = self.bits2int(t)
            if 1 <= nonce < self.n:
                return nonce
            k = hmac.new(k, v + b'\x00', self.hash_function).digest()
            v = hmac.new(k, v, self.hash_function).digest()
