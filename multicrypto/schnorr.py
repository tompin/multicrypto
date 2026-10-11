"""Schnorr signatures for secp256k1 (BIP-340) and Taproot key tweaking (BIP-341, BIP-86).

Public keys are x-only: 32 bytes of the x coordinate of the point with even y coordinate.
"""

import hashlib
from os import urandom

from multicrypto.ellipticcurve import Point, secp256k1


def tagged_hash(tag, data):
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + data).digest()


def x_only(point):
    return point.x.to_bytes(32, byteorder='big')


def lift_x(x, curve=secp256k1):
    """Return the point with the given x coordinate and even y coordinate or None."""
    if x >= curve.p:
        return None
    y_squared = (pow(x, 3, curve.p) + curve.a * x + curve.b) % curve.p
    # For secp256k1 p % 4 == 3, so the square root is y_squared ^ ((p + 1) / 4)
    y = pow(y_squared, (curve.p + 1) // 4, curve.p)
    if pow(y, 2, curve.p) != y_squared:
        return None
    return Point(curve, x, y if y % 2 == 0 else curve.p - y)


def schnorr_sign(message, private_key, aux_rand=None, curve=secp256k1):
    """Sign 32 bytes message according to BIP-340, returns 64 bytes signature.

    :param aux_rand: 32 bytes of auxiliary random data, by default taken from os.urandom
    """
    if not 1 <= private_key < curve.n:
        raise ValueError('Private key must be an integer in the range 1..n-1')
    if aux_rand is None:
        aux_rand = urandom(32)
    public_key = private_key * curve.G
    d = private_key if public_key.y % 2 == 0 else curve.n - private_key
    t = d ^ int.from_bytes(tagged_hash('BIP0340/aux', aux_rand), byteorder='big')
    nonce_hash = tagged_hash(
        'BIP0340/nonce', t.to_bytes(32, byteorder='big') + x_only(public_key) + message
    )
    k = int.from_bytes(nonce_hash, byteorder='big') % curve.n
    if k == 0:
        raise ValueError('Failure, nonce is equal to zero')
    r_point = k * curve.G
    if r_point.y % 2:
        k = curve.n - k
    e = _challenge(x_only(r_point), x_only(public_key), message, curve)
    signature = x_only(r_point) + ((k + e * d) % curve.n).to_bytes(32, byteorder='big')
    if not schnorr_verify(message, x_only(public_key), signature, curve):
        raise ValueError('Created signature does not pass verification')
    return signature


def schnorr_verify(message, public_key, signature, curve=secp256k1):
    """Verify BIP-340 signature of the message for x-only public key (32 bytes)."""
    if len(public_key) != 32 or len(signature) != 64:
        return False
    point = lift_x(int.from_bytes(public_key, byteorder='big'), curve)
    r = int.from_bytes(signature[:32], byteorder='big')
    s = int.from_bytes(signature[32:], byteorder='big')
    if point is None or r >= curve.p or s >= curve.n:
        return False
    e = _challenge(signature[:32], public_key, message, curve)
    r_point = s * curve.G - e * point
    if r_point == curve.identity_point or r_point.y % 2:
        return False
    return r_point.x == r


def _challenge(r, public_key, message, curve):
    challenge_hash = tagged_hash('BIP0340/challenge', r + public_key + message)
    return int.from_bytes(challenge_hash, byteorder='big') % curve.n


def taproot_tweak(public_key, merkle_root=b''):
    """Tweak for the internal x-only public key, merkle root is empty for key path only
    outputs (BIP-86)."""
    return int.from_bytes(tagged_hash('TapTweak', public_key + merkle_root), byteorder='big')


def taproot_output_key(private_key, merkle_root=b'', curve=secp256k1):
    """X-only output public key (witness program of P2TR output) for the internal private key."""
    internal_key = lift_x((private_key * curve.G).x, curve)
    tweak = taproot_tweak(x_only(internal_key), merkle_root)
    return x_only(internal_key + tweak * curve.G)


def taproot_tweak_private_key(private_key, merkle_root=b'', curve=secp256k1):
    """Private key corresponding to the output key, used to sign key path spends."""
    public_key = private_key * curve.G
    d = private_key if public_key.y % 2 == 0 else curve.n - private_key
    tweak = taproot_tweak(x_only(public_key), merkle_root)
    if tweak >= curve.n:
        raise ValueError('Taproot tweak is out of range')
    return (d + tweak) % curve.n
