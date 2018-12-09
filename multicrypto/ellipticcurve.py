import hmac
from hashlib import sha256
from os import urandom
from struct import pack


def modular_inverse(a, n):
    """
    Extended Euclidean Algorithm. It's the 'division' in elliptic curves
    :param a: Divisor
    :param n: Mod for division
    :return: Value which fulfill equation `(value * a) % n == 1`
    """
    a = a % n
    if a == 0:
        return 0
    lm, hm = 1, 0
    low, high = a % n, n
    while low > 1:
        r = high // low
        nm, new = hm - lm * r, high - low * r
        lm, low, hm, high = nm, new, lm, low
    return lm % n


class Curve:
    def __init__(self, name, p, a, b, n, gx, gy):
        """
        An elliptic curve representing equation y^2 = x^3 + a*x + b (mod p)
        :param name: Name of the curve
        :param p: The prime used to mod all coordinates
        :param a: Coefficient in above elliptic curve equation
        :param b: Coefficient in above elliptic curve equation
        :param n: The order of the base point of the curve
        :param gx: The x coordinate of the base point of the curve.
        :param gy: The y coordinate of the base point of the curve.
        """
        self.name = name
        self.p = p
        self.a = a
        self.b = b
        self.n = n
        self.gx = gx
        self.gy = gy
        self.G = Point(self, gx, gy)

    def __str__(self):
        return 'curve {}'.format(self.name)

    @property
    def identity_point(self):
        return Point(self, 0, 0)

    def is_point_on_curve(self, point):
        if point.x == point.y == 0:  # identity point
            return True
        left = pow(point.y, 2, self.p)
        right = (pow(point.x, 3, self.p) + self.a * point.x + self.b) % self.p
        return left == right

    def gen_private_key(self):
        order_bits = 0
        order = self.n
        while order > 0:
            order >>= 1
            order_bits += 1
        order_bytes = (order_bits + 7) // 8  # urandom only takes bytes
        extra_bits = order_bytes * 8 - order_bits  # bits to shave off after getting bytes
        rand = int.from_bytes(urandom(order_bytes), byteorder='big')
        rand >>= extra_bits
        # no modding by group order or we'll introduce biases
        while rand >= self.n:
            rand = int.from_bytes(urandom(order_bytes), byteorder='big')
            rand >>= extra_bits
        return rand


class Point:
    def __init__(self, curve, x, y):
        """
        Point on elliptic curve with (x, y) coordinates
        :param curve: Elliptic curve
        :param x: x coordinate
        :param y: y coordinate
        """
        self.curve = curve
        self.x = x % self.curve.p
        self.y = y % self.curve.p
        if not curve.is_point_on_curve(self):
            raise Exception('Point {} is not on the curve {}'.format(self, curve))

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y

    def __iadd__(self, other):
        result = self.__add__(other)
        self.x = result.x
        self.y = result.y
        return self

    def __add__(self, other):
        if self == self.curve.identity_point:
            return other
        if other == self.curve.identity_point:
            return self

        if self.x == other.x:
            if self.y == other.y:  # adding point to itself
                return self.double()
            else:  # sum of vertical pair points gives identity point
                return self.curve.identity_point

        inverse_den = modular_inverse((self.x - other.x) % self.curve.p, self.curve.p)
        slope = ((self.y - other.y) * inverse_den) % self.curve.p
        return self.line_intersect(other, slope)

    def __sub__(self, other):
        neg_other = Point(self.curve, other.x, -other.y % self.curve.p)
        return self.__add__(neg_other)

    def __isub__(self, other):
        result = self.__sub__(other)
        self.x = result.x
        self.y = result.y
        return self

    def __mul__(self, m):
        result_point = self.curve.identity_point
        double_point = self
        while m != 0:  # binary multiply loop
            if m & 1:  # bit is set
                result_point = result_point + double_point
            m >>= 1
            if m != 0:
                double_point = double_point.double()
        return result_point

    def __rmul__(self, other):
        return self.__mul__(other)

    def __imul__(self, other):
        result = self.__mul__(other)
        self.x = result.x
        self.y = result.y
        return self

    # Return the (x,y) point where this line intersects our curve
    #  Q1 and Q2 are two points on the line of slope m
    def line_intersect(self, other_point, m):
        p = self.curve.p
        v = (self.y + p - (m * self.x) % p) % p
        x = m * m + p - self.x + p - other_point.x
        y = p - (m * x) % p + p - v
        return Point(self.curve, x, y)

    # Return the slope of the tangent of this curve
    def tangent(self):
        inverse = modular_inverse(self.y * 2, self.curve.p)
        return ((self.x * self.x * 3 + self.curve.a) * inverse) % self.curve.p

    # Return a doubled version of this elliptic curve point
    def double(self):
        if self.x == 0:  # doubling the identity
            return self
        return self.line_intersect(self, self.tangent())

    def __str__(self):
        return '({}, {}) on {}'.format(self.x, self.y, self.curve)


secp256k1 = Curve(
    name='secp256k1',
    p=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F,
    a=0,
    b=7,
    n=0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141,
    gx=0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
    gy=0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
)


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
