"""Ethereum addresses, private keys and transactions.

Transactions use the format of EIP-1559 (type 2) with the fee split into the base fee, burned by
the network, and the priority fee for the block builder. The chain id of the transaction protects
against replaying it on another chain (e.g. a testnet transaction on the mainnet).
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Tuple, Union

from multicrypto import rlp
from multicrypto.ecdsa import recover_public_key, sign_digest
from multicrypto.ellipticcurve import Point, secp256k1
from multicrypto.keccak import keccak256

ETHER_DECIMALS = 18
GWEI_DECIMALS = 9
GWEI = 10**GWEI_DECIMALS
ETHER = 10**ETHER_DECIMALS
# Gas of a transfer to an existing account without code. It is not the minimum: since the fork with
# repriced gas (on Sepolia in 2026) a transfer to own address costs less and creating an account
# by sending ether to a new address costs more, so the gas limit is estimated by the node.
TRANSFER_GAS = 21000
EIP1559_TYPE = 2
SIGNED_FIELDS = 12

ADDRESS_PATTERN = re.compile(r'[0-9a-fA-F]{40}')
PRIVATE_KEY_PATTERN = re.compile(r'(0[xX])?[0-9a-fA-F]{64}')


def address_bytes(public_key: Point) -> bytes:
    """Address is the last 20 bytes of Keccak-256 of the uncompressed public key without
    the first byte 04."""
    return keccak256(public_key.x.to_bytes(32, 'big') + public_key.y.to_bytes(32, 'big'))[-20:]


def to_checksum_address(address: str) -> str:
    """Address with mixed case letters encoding its checksum (EIP-55)."""
    hex_address = address[2:].lower()
    digest = keccak256(hex_address.encode()).hex()
    return '0x' + ''.join(
        character.upper() if int(digest[i], 16) >= 8 else character
        for i, character in enumerate(hex_address)
    )


def public_key_to_address(public_key: Point) -> str:
    return to_checksum_address('0x' + address_bytes(public_key).hex())


def private_key_to_address(private_key: int) -> str:
    return public_key_to_address(secp256k1.G * private_key)


def validate_address(address: str) -> str:
    """Check the address and return it with the checksum. Addresses with letters of one case
    have no checksum (EIP-55), so they are accepted without checking it."""
    if not address.startswith('0x'):
        raise ValueError(f'Ethereum address {address} must start with 0x')
    if not ADDRESS_PATTERN.fullmatch(address[2:]):
        raise ValueError(f'Ethereum address {address} must have 40 hexadecimal digits after 0x')
    checksum_address = to_checksum_address(address)
    hex_digits = address[2:]
    if hex_digits not in (hex_digits.lower(), hex_digits.upper()) and address != checksum_address:
        raise ValueError(f'Incorrect checksum of Ethereum address {address}')
    return checksum_address


def parse_private_key(value: str) -> int:
    """Private key from 64 hexadecimal digits, optionally prefixed with 0x."""
    value = value.strip()
    if not PRIVATE_KEY_PATTERN.fullmatch(value):
        raise ValueError('Ethereum private key must have 64 hexadecimal digits')
    private_key = int(value, 16)
    if not 0 < private_key < secp256k1.n:
        raise ValueError('Ethereum private key is out of range of secp256k1 keys')
    return private_key


def format_private_key(private_key: int) -> str:
    return f'0x{private_key:064x}'


def parse_units(value: Union[str, Decimal], decimals: int) -> int:
    """Amount in the smallest units from the decimal number, e.g. wei from ether."""
    try:
        number = Decimal(value.strip() if isinstance(value, str) else value)
    except InvalidOperation:
        raise ValueError(f'{value} is not a number') from None
    if not number.is_finite():
        raise ValueError(f'{value} is not a number')
    if number < 0:
        raise ValueError(f'Amount {value} cannot be negative')
    units = number.scaleb(decimals)
    if units != units.to_integral_value():
        raise ValueError(f'Amount {value} has more than {decimals} decimal places')
    return int(units)


def format_units(value: int, decimals: int) -> str:
    text = format(Decimal(value).scaleb(-decimals), 'f')
    return text.rstrip('0').rstrip('.') if '.' in text else text


def parse_ether(value: Union[str, Decimal]) -> int:
    return parse_units(value, ETHER_DECIMALS)


def format_ether(wei: int) -> str:
    return format_units(wei, ETHER_DECIMALS)


def parse_gwei(value: Union[str, Decimal]) -> int:
    return parse_units(value, GWEI_DECIMALS)


def format_gwei(wei: int) -> str:
    return format_units(wei, GWEI_DECIMALS)


@dataclass(frozen=True)
class SignedTransaction:
    raw: bytes

    @property
    def raw_hex(self) -> str:
        return '0x' + self.raw.hex()

    @property
    def hash(self) -> str:
        """Transaction hash (id) used by nodes and block explorers."""
        return '0x' + keccak256(self.raw).hex()


@dataclass(frozen=True)
class Transaction:
    """Transaction of EIP-1559 (type 2) without an access list. Amounts are in wei."""

    chain_id: int
    nonce: int
    max_priority_fee_per_gas: int
    max_fee_per_gas: int
    gas_limit: int
    to: str
    value: int
    data: bytes = field(default=b'', repr=False)

    def __post_init__(self):
        object.__setattr__(self, 'to', validate_address(self.to))
        for name in ('chain_id', 'nonce', 'max_priority_fee_per_gas', 'max_fee_per_gas', 'value'):
            if getattr(self, name) < 0:
                raise ValueError(f'Transaction {name} cannot be negative')
        if self.max_priority_fee_per_gas > self.max_fee_per_gas:
            raise ValueError('Max priority fee per gas cannot be bigger than max fee per gas')
        if self.gas_limit <= 0:
            raise ValueError('Transaction gas limit must be positive')

    @property
    def max_fee(self) -> int:
        """The most the transaction can pay for gas, the base fee lower than the max fee per gas
        is not paid."""
        return self.gas_limit * self.max_fee_per_gas

    def _fields(self) -> list:
        return [
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas_limit,
            bytes.fromhex(self.to[2:]),
            self.value,
            self.data,
            [],  # access list
        ]

    def signing_hash(self) -> bytes:
        return keccak256(bytes([EIP1559_TYPE]) + rlp.encode(self._fields()))

    def sign(self, private_key: int) -> SignedTransaction:
        r, s, recid = sign_digest(self.signing_hash(), private_key)
        # recovery id 2 and 3 (r above n) cannot be encoded, their probability is below 2^-127
        if recid > 1:
            raise ValueError('Cannot sign the transaction')
        payload = rlp.encode(self._fields() + [recid, r, s])
        return SignedTransaction(bytes([EIP1559_TYPE]) + payload)


def decode_transaction(raw: bytes) -> Tuple[Transaction, str]:
    """Transaction and the address of the sender from the signed transaction."""
    if not raw or raw[0] != EIP1559_TYPE:
        raise ValueError('Only EIP-1559 (type 2) transactions are supported')
    fields = rlp.decode(raw[1:])
    if not isinstance(fields, list) or len(fields) != SIGNED_FIELDS:
        raise ValueError(f'EIP-1559 transaction must have {SIGNED_FIELDS} fields')
    chain_id, nonce, priority_fee, max_fee, gas_limit, to, value, data, access_list = fields[:9]
    if access_list:
        raise ValueError('Transactions with an access list are not supported')
    if len(to) != 20:
        raise ValueError('Transactions creating contracts are not supported')
    transaction = Transaction(
        *(int.from_bytes(item, 'big') for item in (chain_id, nonce, priority_fee, max_fee)),
        int.from_bytes(gas_limit, 'big'),
        to_checksum_address('0x' + to.hex()),
        int.from_bytes(value, 'big'),
        data,
    )
    y_parity, r, s = (int.from_bytes(item, 'big') for item in fields[9:])
    public_key = recover_public_key(transaction.signing_hash(), y_parity, r, s)
    if public_key is None:
        raise ValueError('Incorrect signature of the transaction')
    return transaction, public_key_to_address(public_key)
