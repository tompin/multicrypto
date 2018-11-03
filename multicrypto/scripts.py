from multicrypto.address import calculate_address
from multicrypto.consts import OP_HASH160, OP_PUSH_20, OP_EQUALVERIFY, OP_EQUAL, OP_CHECKSIG, OP_DUP, \
    OP_0, OP_1, OP_2, OP_3, OP_4, OP_5, OP_6, OP_7, OP_8, OP_9, OP_10, OP_11, OP_12, OP_13, OP_14, \
    OP_15, OP_16, OP_RETURN, OP_CHECKMULTISIGVERIFY
from multicrypto.utils import hex_to_bytes, hash160

P2SH_SCRIPT = (OP_HASH160 + OP_PUSH_20) + b'%b' + OP_EQUAL
P2PKH_SCRIPT = (OP_DUP + OP_HASH160 + OP_PUSH_20) + b'%b' + OP_EQUALVERIFY + OP_CHECKSIG


def is_p2sh(script):
    return (
        len(script) == 23 and
        script.startswith(OP_HASH160 + OP_PUSH_20) and
        script.endswith(OP_EQUAL)
    )


def is_p2pkh(script):
    return (
        len(script) == 25 and
        script.startswith(OP_DUP + OP_HASH160 + OP_PUSH_20) and
        script.endswith(OP_EQUALVERIFY + OP_CHECKSIG)
    )


def is_p2pk(script):
    # Public key is 65 bytes long (0x04 + 64 bytes public key) or 33 bytes when compressed
    # (0x02 | 0x03 + 32 bytes public key), so  Public key + OP_CHECKSIG has 66 or 34 length
    return (
        ((len(script) == 34 and script[0] in [b'\x02', b'\x03']) or
         (len(script) == 66 and script[0] == b'\x04')) and
        script[-1] == OP_CHECKSIG
    )


def is_null_data(script):
    return len(script) > 0 and script[0] == OP_RETURN


def is_multisig(script):
    OP_X = [OP_0, OP_1, OP_2, OP_3, OP_4, OP_5, OP_6, OP_7, OP_8, OP_9, OP_10,
            OP_11, OP_12, OP_13, OP_14, OP_15, OP_16]
    return (len(script) > 3 and script[-1] == OP_CHECKMULTISIGVERIFY and script[-2] in OP_X and
            script[0] in OP_X)
    # TODO: read script and verify public keys were correctly provided


def validate_hex_script(hex_script):
    try:
        bytes.fromhex(hex_script)
    except Exception as e:
        raise Exception('Script should be provided in HEX format: {}'.format(e))
    # TODO: validate structure of the script


def convert_script_to_p2sh_address(script, address_prefix_bytes):
    digest = hash160(hex_to_bytes(script, byteorder='big'))
    address = calculate_address(digest, address_prefix_bytes)
    return address
