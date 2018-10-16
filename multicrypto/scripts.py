from multicrypto.consts import OP_DUP, OP_HASH160, OP_PUSH_20, OP_EQUALVERIFY, OP_CHECKSIG, \
    OP_EQUAL

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
