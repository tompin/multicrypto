from multicrypto.address import (
    calculate_address,
    decode_segwit_address,
    decompose_address,
    is_segwit_address,
    segwit_scriptpubkey,
)
from multicrypto.consts import (
    OP_HASH160,
    OP_PUSH_20,
    OP_PUSH_32,
    OP_EQUALVERIFY,
    OP_EQUAL,
    OP_CHECKSIG,
    OP_DUP,
    OP_0,
    OP_1,
    OP_2,
    OP_3,
    OP_4,
    OP_5,
    OP_6,
    OP_7,
    OP_8,
    OP_9,
    OP_10,
    OP_11,
    OP_12,
    OP_13,
    OP_14,
    OP_15,
    OP_16,
    OP_RETURN,
    OP_CHECKMULTISIGVERIFY,
)
from multicrypto.utils import hex_to_bytes, hash160, int_to_varint

P2SH_SCRIPT = (OP_HASH160 + OP_PUSH_20) + b'%b' + OP_EQUAL
P2PKH_SCRIPT = (OP_DUP + OP_HASH160 + OP_PUSH_20) + b'%b' + OP_EQUALVERIFY + OP_CHECKSIG
P2WPKH_SCRIPT = (OP_0 + OP_PUSH_20) + b'%b'

# Fee rate (in satoshis per virtual byte) used by Bitcoin Core to decide whether an output is dust
DUST_RELAY_FEE = 3


def is_p2sh(script):
    return (
        len(script) == 23
        and script.startswith(OP_HASH160 + OP_PUSH_20)
        and script.endswith(OP_EQUAL)
    )


def is_p2pkh(script):
    return (
        len(script) == 25
        and script.startswith(OP_DUP + OP_HASH160 + OP_PUSH_20)
        and script.endswith(OP_EQUALVERIFY + OP_CHECKSIG)
    )


def is_p2wpkh(script):
    return len(script) == 22 and script.startswith(OP_0 + OP_PUSH_20)


def is_p2tr(script):
    return len(script) == 34 and script.startswith(OP_1 + OP_PUSH_32)


def is_witness_program(script):
    """Locking script of a segwit output: version (OP_0 to OP_16) and 2 to 40 bytes push"""
    return (
        4 <= len(script) <= 42
        and (script[:1] == OP_0 or OP_1 <= script[:1] <= OP_16)
        and script[1] == len(script) - 2
    )


def get_dust_threshold(script):
    """Minimal amount of satoshis which can be sent to the locking script without the output
    being rejected by nodes as dust: cost of creating and spending the output at the dust relay
    fee, calculated in the same way as GetDustThreshold in Bitcoin Core"""
    output_size = 8 + len(int_to_varint(len(script))) + len(script)
    # outpoint, script length, unlocking script (signature and public key), sequence
    if is_witness_program(script):
        spending_input_size = 32 + 4 + 1 + 107 // 4 + 4
    else:
        spending_input_size = 32 + 4 + 1 + 107 + 4
    return (output_size + spending_input_size) * DUST_RELAY_FEE


def is_p2pk(script):
    # Public key is 65 bytes long (0x04 + 64 bytes public key) or 33 bytes when compressed
    # (0x02 | 0x03 + 32 bytes public key), so  Public key + OP_CHECKSIG has 66 or 34 length
    return (
        (len(script) == 34 and script[0] in [b'\x02', b'\x03'])
        or (len(script) == 66 and script[0] == b'\x04')
    ) and script[-1] == OP_CHECKSIG


def is_null_data(script):
    return len(script) > 0 and script[0] == OP_RETURN


def is_multisig(script):
    op_x = [
        OP_0,
        OP_1,
        OP_2,
        OP_3,
        OP_4,
        OP_5,
        OP_6,
        OP_7,
        OP_8,
        OP_9,
        OP_10,
        OP_11,
        OP_12,
        OP_13,
        OP_14,
        OP_15,
        OP_16,
    ]
    return (
        len(script) > 3
        and script[-1] == OP_CHECKMULTISIGVERIFY
        and script[-2] in op_x
        and script[0] in op_x
    )
    # TODO: read script and verify public keys were correctly provided


def address_to_script(address, coin):
    """Locking script (scriptPubKey) paying to the base58 (P2PKH, P2SH) or bech32 address"""
    if is_segwit_address(address, coin):
        witness = decode_segwit_address(address, coin)
        if witness is None:
            raise ValueError(f'Incorrect bech32 address {address}')
        return segwit_scriptpubkey(*witness)
    prefix, digest = decompose_address(address, coin)
    if prefix == coin['script_prefix_bytes']:
        return P2SH_SCRIPT % digest
    return P2PKH_SCRIPT % digest


def validate_hex_script(hex_script):
    try:
        bytes.fromhex(hex_script)
    except Exception as e:
        raise ValueError(f'Script should be provided in HEX format: {e}') from e
    # TODO: validate structure of the script


def convert_script_to_p2sh_address(script, address_prefix_bytes):
    digest = hash160(hex_to_bytes(script, byteorder='big'))
    address = calculate_address(digest, address_prefix_bytes)
    return address
