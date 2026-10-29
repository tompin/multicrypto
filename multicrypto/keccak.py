"""Keccak-256 hash used by Ethereum.

hashlib.sha3_256 cannot be used: Ethereum uses the original Keccak submitted to the SHA-3
competition, which differs from the final SHA3-256 standard (FIPS 202) only in the first byte of
the padding. Based on the specification https://keccak.team/keccak_specs_summary.html.
"""

RATE = 136  # in bytes, 1600 bits of the state minus 512 bits of the capacity for 256-bit digest
DIGEST_SIZE = 32
KECCAK_PADDING = 0x01
SHA3_PADDING = 0x06
MASK = 2**64 - 1

ROUND_CONSTANTS = (
    0x0000000000000001,
    0x0000000000008082,
    0x800000000000808A,
    0x8000000080008000,
    0x000000000000808B,
    0x0000000080000001,
    0x8000000080008081,
    0x8000000000008009,
    0x000000000000008A,
    0x0000000000000088,
    0x0000000080008009,
    0x000000008000000A,
    0x000000008000808B,
    0x800000000000008B,
    0x8000000000008089,
    0x8000000000008003,
    0x8000000000008002,
    0x8000000000000080,
    0x000000000000800A,
    0x800000008000000A,
    0x8000000080008081,
    0x8000000000008080,
    0x0000000080000001,
    0x8000000080008008,
)

# Rotation offsets of the lanes, indexed by x + 5 * y
ROTATIONS = (
    0, 1, 62, 28, 27,
    36, 44, 6, 55, 20,
    3, 10, 43, 25, 39,
    41, 45, 15, 21, 8,
    18, 2, 61, 56, 14,
)  # fmt: skip


# Steps rho and pi move the lane A[x, y] rotated by its offset to B[y, 2x + 3y]
RHO_PI = tuple(
    (x + 5 * y, y + 5 * ((2 * x + 3 * y) % 5), ROTATIONS[x + 5 * y])
    for x in range(5)
    for y in range(5)
)


def _rotate(lane: int, offset: int) -> int:
    return ((lane << offset) | (lane >> (64 - offset))) & MASK if offset else lane


def keccak_f(state: list) -> None:
    """Keccak-f[1600] permutation of 25 lanes of 64 bits, indexed by x + 5 * y, in place."""
    for round_constant in ROUND_CONSTANTS:
        # theta
        columns = [
            state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20]
            for x in range(5)
        ]
        for x in range(5):
            d = columns[(x - 1) % 5] ^ _rotate(columns[(x + 1) % 5], 1)
            for y in range(0, 25, 5):
                state[x + y] ^= d
        # rho and pi
        b = [0] * 25
        for source, target, offset in RHO_PI:
            b[target] = _rotate(state[source], offset)
        # chi
        for y in range(0, 25, 5):
            for x in range(5):
                state[x + y] = b[x + y] ^ (~b[(x + 1) % 5 + y] & b[(x + 2) % 5 + y])
        # iota
        state[0] ^= round_constant


def sponge(data: bytes, padding: int) -> bytes:
    """256-bit digest of the data using the sponge construction with the padding byte."""
    padded = bytearray(data)
    padded.append(padding)
    padded.extend(bytes(-len(padded) % RATE))
    padded[-1] |= 0x80
    state = [0] * 25
    for start in range(0, len(padded), RATE):
        block = padded[start : start + RATE]
        for i in range(RATE // 8):
            state[i] ^= int.from_bytes(block[8 * i : 8 * i + 8], 'little')
        keccak_f(state)
    return b''.join(lane.to_bytes(8, 'little') for lane in state[: DIGEST_SIZE // 8])


def keccak256(data: bytes) -> bytes:
    return sponge(data, KECCAK_PADDING)
