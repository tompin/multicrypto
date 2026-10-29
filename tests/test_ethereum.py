from decimal import Decimal

import pytest

from multicrypto import rlp
from multicrypto.bip32 import master_key_from_seed
from multicrypto.bip39 import mnemonic_to_seed
from multicrypto.coins import ethereum_coins
from multicrypto.ecdsa import recover_public_key, sign_digest
from multicrypto.ellipticcurve import secp256k1
from multicrypto.ethereum import (
    GWEI,
    Transaction,
    decode_transaction,
    format_ether,
    format_private_key,
    hash_message,
    parse_ether,
    parse_gwei,
    parse_private_key,
    private_key_to_address,
    public_key_to_address,
    recover_message_signer,
    sign_message,
    to_checksum_address,
    validate_address,
    verify_message,
)
from multicrypto.keccak import keccak256

# Example of EIP-155 https://eips.ethereum.org/EIPS/eip-155
EIP155_PRIVATE_KEY = 0x4646464646464646464646464646464646464646464646464646464646464646
EIP155_ADDRESS = '0x9d8A62f656a8d1615C1294fd71e9CFb3E4855A4F'
EIP155_SIGNING_HASH = 'daf5a779ae972f972197303d7b574746c7ef83eadac0f2791ad23db92e4c8e53'
EIP155_R = 18515461264373351373200002665853028612451056578545711640558177340181847433846
EIP155_S = 46948507304638947509940763649030358759909902576025900602547168820602576006531

# Addresses from EIP-55 https://eips.ethereum.org/EIPS/eip-55
CHECKSUM_ADDRESSES = [
    '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed',
    '0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359',
    '0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB',
    '0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb',
    '0x52908400098527886E0F7030069857D2E4169EE7',
    '0x8617E340B3D01FA5F11F306F4090FD50E238070D',
    '0xde709f2102306220921060314715629080e2fb77',
    '0x27b1fdb04752bbc536007a920d24acb045561c26',
]

MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])


def test_private_key_to_address():
    assert private_key_to_address(1) == '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'
    assert private_key_to_address(EIP155_PRIVATE_KEY) == EIP155_ADDRESS


def test_public_key_to_address():
    assert public_key_to_address(secp256k1.G * EIP155_PRIVATE_KEY) == EIP155_ADDRESS


def test_address_of_bip44_path_is_the_same_as_in_metamask():
    root = master_key_from_seed(mnemonic_to_seed(MNEMONIC))
    slip44 = ethereum_coins['ETH']['slip44']

    key = root.derive_path(f"m/44'/{slip44}'/0'/0/0")

    assert private_key_to_address(key.private_key) == '0x9858EfFD232B4033E47d90003D41EC34EcaEda94'


@pytest.mark.parametrize('address', CHECKSUM_ADDRESSES)
def test_to_checksum_address(address):
    assert to_checksum_address(address.lower()) == address
    assert to_checksum_address('0x' + address[2:].upper()) == address


@pytest.mark.parametrize('address', CHECKSUM_ADDRESSES)
def test_validate_address_returns_checksum_address(address):
    assert validate_address(address) == address
    assert validate_address(address.lower()) == address
    assert validate_address('0x' + address[2:].upper()) == address


@pytest.mark.parametrize(
    'address, message',
    [
        ('5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed', 'start with 0x'),
        ('0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAe', '40 hexadecimal'),
        ('0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAedd', '40 hexadecimal'),
        ('0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeg', '40 hexadecimal'),
        ('0x5AAeb6053F3E94C9b9A09f33669435E7Ef1BeAed', 'checksum'),
    ],
)
def test_validate_address_rejects_incorrect_addresses(address, message):
    with pytest.raises(ValueError, match=message):
        validate_address(address)


@pytest.mark.parametrize('prefix', ['', '0x', '0X'])
def test_parse_private_key(prefix):
    assert parse_private_key(prefix + '46' * 32) == EIP155_PRIVATE_KEY
    assert parse_private_key(f'  {prefix}{"46" * 32}\n') == EIP155_PRIVATE_KEY


@pytest.mark.parametrize(
    'value', ['46' * 31, '46' * 33, 'zz' * 32, '00' * 32, f'{secp256k1.n:064x}', '']
)
def test_parse_private_key_rejects_incorrect_keys(value):
    with pytest.raises(ValueError, match='private key'):
        parse_private_key(value)


def test_format_private_key():
    assert format_private_key(1) == '0x' + '00' * 31 + '01'
    assert parse_private_key(format_private_key(EIP155_PRIVATE_KEY)) == EIP155_PRIVATE_KEY


@pytest.mark.parametrize(
    'value, wei',
    [
        ('1', 10**18),
        ('0.01', 10**16),
        ('1.5', 15 * 10**17),
        ('0.000000000000000001', 1),
        (' 2 ', 2 * 10**18),
        ('0', 0),
        (Decimal('0.1'), 10**17),
    ],
)
def test_parse_ether(value, wei):
    assert parse_ether(value) == wei


@pytest.mark.parametrize(
    'value, message',
    [
        ('0.0000000000000000001', 'more than 18 decimal places'),
        ('-1', 'negative'),
        ('abc', 'not a number'),
        ('nan', 'not a number'),
        ('inf', 'not a number'),
    ],
)
def test_parse_ether_rejects_incorrect_values(value, message):
    with pytest.raises(ValueError, match=message):
        parse_ether(value)


def test_parse_gwei():
    assert parse_gwei('1.5') == 15 * 10**8
    assert parse_gwei('0.000000001') == 1


@pytest.mark.parametrize(
    'wei, text', [(10**18, '1'), (15 * 10**17, '1.5'), (1, '0.000000000000000001'), (0, '0')]
)
def test_format_ether(wei, text):
    assert format_ether(wei) == text


def test_sign_digest_gives_signature_of_eip155_example():
    r, s, recid = sign_digest(bytes.fromhex(EIP155_SIGNING_HASH), EIP155_PRIVATE_KEY)

    assert (r, s, recid) == (EIP155_R, EIP155_S, 0)


@pytest.mark.parametrize('private_key', [1, 2, 3, EIP155_PRIVATE_KEY, secp256k1.n - 1])
def test_sign_digest_gives_low_s_and_recovery_id_of_the_key(private_key):
    digest = keccak256(private_key.to_bytes(32, 'big'))

    r, s, recid = sign_digest(digest, private_key)

    assert s <= secp256k1.n // 2
    assert recover_public_key(digest, recid, r, s) == secp256k1.G * private_key


def make_transaction(**fields):
    defaults = dict(
        chain_id=1,
        nonce=9,
        max_priority_fee_per_gas=2 * GWEI,
        max_fee_per_gas=40 * GWEI,
        gas_limit=21000,
        to='0x3535353535353535353535353535353535353535',
        value=10**18,
    )
    defaults.update(fields)
    return Transaction(**defaults)


def test_transaction_signing_hash_is_keccak_of_type_and_rlp_of_fields():
    transaction = make_transaction(data=b'\xde\xad')
    payload = rlp.encode([1, 9, 2 * GWEI, 40 * GWEI, 21000, b'\x35' * 20, 10**18, b'\xde\xad', []])

    assert transaction.signing_hash() == keccak256(b'\x02' + payload)


def test_signed_transaction_has_signature_fields_and_hash_of_raw_bytes():
    transaction = make_transaction()

    signed = transaction.sign(EIP155_PRIVATE_KEY)

    assert signed.raw[0] == 2
    fields = rlp.decode(signed.raw[1:])
    assert len(fields) == 12
    y_parity, r, s = (int.from_bytes(field, 'big') for field in fields[9:])
    expected_r, expected_s, recid = sign_digest(transaction.signing_hash(), EIP155_PRIVATE_KEY)
    assert (y_parity, r, s) == (recid, expected_r, expected_s)
    assert signed.hash == '0x' + keccak256(signed.raw).hex()
    assert signed.raw_hex == '0x' + signed.raw.hex()


@pytest.mark.parametrize(
    'transaction',
    [
        make_transaction(),
        make_transaction(chain_id=11155111, nonce=0, value=0, data=bytes.fromhex('a9059cbb')),
        make_transaction(nonce=2**64 - 1, value=2**256 - 1),
    ],
)
def test_decode_transaction_returns_transaction_and_sender(transaction):
    signed = transaction.sign(EIP155_PRIVATE_KEY)

    assert decode_transaction(signed.raw) == (transaction, EIP155_ADDRESS)


def test_decode_transaction_rejects_other_types():
    with pytest.raises(ValueError, match='EIP-1559'):
        decode_transaction(b'\x01' + rlp.encode([]))


def test_decode_transaction_rejects_wrong_number_of_fields():
    with pytest.raises(ValueError, match='12 fields'):
        decode_transaction(b'\x02' + rlp.encode([1, 2, 3]))


def test_transaction_accepts_gas_limit_below_21000():
    # transfer to own address on Sepolia after the fork with repriced gas
    assert make_transaction(gas_limit=12000).gas_limit == 12000


def test_transaction_max_fee():
    assert make_transaction().max_fee == 21000 * 40 * GWEI


@pytest.mark.parametrize(
    'fields, message',
    [
        (dict(max_priority_fee_per_gas=50 * GWEI), 'priority fee'),
        (dict(gas_limit=0), 'gas limit'),
        (dict(value=-1), 'negative'),
        (dict(nonce=-1), 'negative'),
        (dict(to='0x1234'), '40 hexadecimal'),
    ],
)
def test_transaction_rejects_incorrect_fields(fields, message):
    with pytest.raises(ValueError, match=message):
        make_transaction(**fields)


# Example of personal_sign from the documentation of web3.py (sign_message with encode_defunct)
MESSAGE_VECTORS = [
    (
        0xB25C7DB31FEED9122727BF0939DC769A96564B2DE4C4726D035B36ECF1E5B364,
        'I♥SF',
        '0xe6ca9bba58c88611fad66a6ce8f996908195593807c4b38bd528d2cff09d4eb3'
        '3e5bfbbf4d3e39b1a2fd816a7680c19ebebaf3a141b239934ad43cb33fcec8ce1c',
    ),
]


def test_hash_message_adds_prefix_with_length_of_utf8_bytes():
    assert hash_message('I♥SF') == keccak256(b'\x19Ethereum Signed Message:\n6I\xe2\x99\xa5SF')


@pytest.mark.parametrize('private_key, message, signature', MESSAGE_VECTORS)
def test_sign_message(private_key, message, signature):
    assert sign_message(message, private_key) == signature


@pytest.mark.parametrize('private_key, message, signature', MESSAGE_VECTORS)
def test_verify_message(private_key, message, signature):
    address = private_key_to_address(private_key)

    assert verify_message(message, signature, address)
    assert verify_message(message, signature.upper().replace('0X', '0x'), address.lower())
    assert not verify_message(message + '!', signature, address)
    assert not verify_message(message, signature, EIP155_ADDRESS)


@pytest.mark.parametrize('message', ['abc', 'Hello World'])
def test_recover_message_signer_accepts_v_and_recovery_id(message):
    signature = sign_message(message, EIP155_PRIVATE_KEY)
    recid = int(signature[-2:], 16) - 27

    assert recid in (0, 1)
    assert recover_message_signer(message, signature) == EIP155_ADDRESS
    assert recover_message_signer(message, signature[:-2] + f'{recid:02x}') == EIP155_ADDRESS
    assert recover_message_signer(message, signature[2:]) == EIP155_ADDRESS


@pytest.mark.parametrize(
    'signature, message',
    [
        ('0x' + '11' * 64, '65 bytes'),
        ('0x' + 'zz' * 65, 'hexadecimal'),
        ('0x' + '11' * 64 + '1d', 'Incorrect v'),
        ('0x' + '00' * 64 + '1b', 'out of range'),
    ],
)
def test_recover_message_signer_rejects_incorrect_signatures(signature, message):
    with pytest.raises(ValueError, match=message):
        recover_message_signer('abc', signature)


def test_verify_message_rejects_incorrect_address():
    signature = sign_message('abc', EIP155_PRIVATE_KEY)

    with pytest.raises(ValueError, match='40 hexadecimal'):
        verify_message('abc', signature, '0x1234')
