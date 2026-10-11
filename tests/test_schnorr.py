import pytest

from multicrypto.ellipticcurve import secp256k1
from multicrypto.schnorr import (
    lift_x,
    schnorr_sign,
    schnorr_verify,
    taproot_output_key,
    taproot_tweak,
    taproot_tweak_private_key,
    x_only,
)

# Test vectors from BIP-340: (index, private key, public key, auxiliary random data, message,
# signature, verification result)
BIP340_VECTORS = [
    (
        0,
        '0000000000000000000000000000000000000000000000000000000000000003',
        'f9308a019258c31049344f85f89d5229b531c845836f99b08601f113bce036f9',
        '0000000000000000000000000000000000000000000000000000000000000000',
        '0000000000000000000000000000000000000000000000000000000000000000',
        (
            'e907831f80848d1069a5371b402410364bdf1c5f8307b0084c55f1ce2dca8215'
            '25f66a4a85ea8b71e482a74f382d2ce5ebeee8fdb2172f477df4900d310536c0'
        ),
        True,
    ),
    (
        1,
        'b7e151628aed2a6abf7158809cf4f3c762e7160f38b4da56a784d9045190cfef',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '0000000000000000000000000000000000000000000000000000000000000001',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '6896bd60eeae296db48a229ff71dfe071bde413e6d43f917dc8dcf8c78de3341'
            '8906d11ac976abccb20b091292bff4ea897efcb639ea871cfa95f6de339e4b0a'
        ),
        True,
    ),
    (
        2,
        'c90fdaa22168c234c4c6628b80dc1cd129024e088a67cc74020bbea63b14e5c9',
        'dd308afec5777e13121fa72b9cc1b7cc0139715309b086c960e18fd969774eb8',
        'c87aa53824b4d7ae2eb035a2b5bbbccc080e76cdc6d1692c4b0b62d798e6d906',
        '7e2d58d8b3bcdf1abadec7829054f90dda9805aab56c77333024b9d0a508b75c',
        (
            '5831aaeed7b44bb74e5eab94ba9d4294c49bcf2a60728d8b4c200f50dd313c1b'
            'ab745879a5ad954a72c45a91c3a51d3c7adea98d82f8481e0e1e03674a6f3fb7'
        ),
        True,
    ),
    (
        3,
        '0b432b2677937381aef05bb02a66ecd012773062cf3fa2549e44f58ed2401710',
        '25d1dff95105f5253c4022f628a996ad3a0d95fbf21d468a1b33f8c160d8f517',
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff',
        (
            '7eb0509757e246f19449885651611cb965ecc1a187dd51b64fda1edc9637d5ec'
            '97582b9cb13db3933705b32ba982af5af25fd78881ebb32771fc5922efc66ea3'
        ),
        True,
    ),
    (
        4,
        '',
        'd69c3509bb99e412e68b0fe8544e72837dfa30746d8be2aa65975f29d22dc7b9',
        '',
        '4df3c3f68fcc83b27e9d42c90431a72499f17875c81a599b566c9889b9696703',
        (
            '00000000000000000000003b78ce563f89a0ed9414f5aa28ad0d96d6795f9c63'
            '76afb1548af603b3eb45c9f8207dee1060cb71c04e80f593060b07d28308d7f4'
        ),
        True,
    ),
    (
        5,
        '',
        'eefdea4cdb677750a420fee807eacf21eb9898ae79b9768766e4faa04a2d4a34',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '6cff5c3ba86c69ea4b7376f31a9bcb4f74c1976089b2d9963da2e5543e177769'
            '69e89b4c5564d00349106b8497785dd7d1d713a8ae82b32fa79d5f7fc407d39b'
        ),
        False,
    ),
    (
        6,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            'fff97bd5755eeea420453a14355235d382f6472f8568a18b2f057a1460297556'
            '3cc27944640ac607cd107ae10923d9ef7a73c643e166be5ebeafa34b1ac553e2'
        ),
        False,
    ),
    (
        7,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '1fa62e331edbc21c394792d2ab1100a7b432b013df3f6ff4f99fcb33e0e1515f'
            '28890b3edb6e7189b630448b515ce4f8622a954cfe545735aaea5134fccdb2bd'
        ),
        False,
    ),
    (
        8,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '6cff5c3ba86c69ea4b7376f31a9bcb4f74c1976089b2d9963da2e5543e177769'
            '961764b3aa9b2ffcb6ef947b6887a226e8d7c93e00c5ed0c1834ff0d0c2e6da6'
        ),
        False,
    ),
    (
        9,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '0000000000000000000000000000000000000000000000000000000000000000'
            '123dda8328af9c23a94c1feecfd123ba4fb73476f0d594dcb65c6425bd186051'
        ),
        False,
    ),
    (
        10,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '0000000000000000000000000000000000000000000000000000000000000001'
            '7615fbaf5ae28864013c099742deadb4dba87f11ac6754f93780d5a1837cf197'
        ),
        False,
    ),
    (
        11,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '4a298dacae57395a15d0795ddbfd1dcb564da82b0f269bc70a74f8220429ba1d'
            '69e89b4c5564d00349106b8497785dd7d1d713a8ae82b32fa79d5f7fc407d39b'
        ),
        False,
    ),
    (
        12,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            'fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f'
            '69e89b4c5564d00349106b8497785dd7d1d713a8ae82b32fa79d5f7fc407d39b'
        ),
        False,
    ),
    (
        13,
        '',
        'dff1d77f2a671c5f36183726db2341be58feae1da2deced843240f7b502ba659',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '6cff5c3ba86c69ea4b7376f31a9bcb4f74c1976089b2d9963da2e5543e177769'
            'fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141'
        ),
        False,
    ),
    (
        14,
        '',
        'fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc30',
        '',
        '243f6a8885a308d313198a2e03707344a4093822299f31d0082efa98ec4e6c89',
        (
            '6cff5c3ba86c69ea4b7376f31a9bcb4f74c1976089b2d9963da2e5543e177769'
            '69e89b4c5564d00349106b8497785dd7d1d713a8ae82b32fa79d5f7fc407d39b'
        ),
        False,
    ),
    (
        15,
        '0340034003400340034003400340034003400340034003400340034003400340',
        '778caa53b4393ac467774d09497a87224bf9fab6f6e68b23086497324d6fd117',
        '0000000000000000000000000000000000000000000000000000000000000000',
        '',
        (
            '71535db165ecd9fbbc046e5ffaea61186bb6ad436732fccc25291a55895464cf'
            '6069ce26bf03466228f19a3a62db8a649f2d560fac652827d1af0574e427ab63'
        ),
        True,
    ),
    (
        16,
        '0340034003400340034003400340034003400340034003400340034003400340',
        '778caa53b4393ac467774d09497a87224bf9fab6f6e68b23086497324d6fd117',
        '0000000000000000000000000000000000000000000000000000000000000000',
        '11',
        (
            '08a20a0afef64124649232e0693c583ab1b9934ae63b4c3511f3ae1134c6a303'
            'ea3173bfea6683bd101fa5aa5dbc1996fe7cacfc5a577d33ec14564cec2bacbf'
        ),
        True,
    ),
    (
        17,
        '0340034003400340034003400340034003400340034003400340034003400340',
        '778caa53b4393ac467774d09497a87224bf9fab6f6e68b23086497324d6fd117',
        '0000000000000000000000000000000000000000000000000000000000000000',
        '0102030405060708090a0b0c0d0e0f1011',
        (
            '5130f39a4059b43bc7cac09a19ece52b5d8699d1a71e3c52da9afdb6b50ac370'
            'c4a482b77bf960f8681540e25b6771ece1e5a37fd80e5a51897c5566a97ea5a5'
        ),
        True,
    ),
    (
        18,
        '0340034003400340034003400340034003400340034003400340034003400340',
        '778caa53b4393ac467774d09497a87224bf9fab6f6e68b23086497324d6fd117',
        '0000000000000000000000000000000000000000000000000000000000000000',
        (
            '9999999999999999999999999999999999999999999999999999999999999999'
            '9999999999999999999999999999999999999999999999999999999999999999'
            '9999999999999999999999999999999999999999999999999999999999999999'
            '99999999'
        ),
        (
            '403b12b0d8555a344175ea7ec746566303321e5dbfa8be6f091635163eca79a8'
            '585ed3e3170807e7c03b720fc54c7b23897fcba0e9d0b4a06894cfd249f22367'
        ),
        True,
    ),
]


@pytest.mark.parametrize(
    'index,private_key,public_key,aux_rand,message,signature,result', BIP340_VECTORS
)
def test_schnorr_verify_bip340(
    index, private_key, public_key, aux_rand, message, signature, result
):
    assert (
        schnorr_verify(bytes.fromhex(message), bytes.fromhex(public_key), bytes.fromhex(signature))
        is result
    )


@pytest.mark.parametrize(
    'index,private_key,public_key,aux_rand,message,signature,result',
    [vector for vector in BIP340_VECTORS if vector[1]],
)
def test_schnorr_sign_bip340(index, private_key, public_key, aux_rand, message, signature, result):
    created_signature = schnorr_sign(
        bytes.fromhex(message), int(private_key, 16), bytes.fromhex(aux_rand)
    )

    assert created_signature.hex() == signature
    assert x_only(int(private_key, 16) * secp256k1.G).hex() == public_key


def test_schnorr_sign_uses_random_auxiliary_data():
    message = b'\x01' * 32
    public_key = x_only(0x1111 * secp256k1.G)

    signature1 = schnorr_sign(message, 0x1111)
    signature2 = schnorr_sign(message, 0x1111)

    assert signature1 != signature2
    assert schnorr_verify(message, public_key, signature1)
    assert schnorr_verify(message, public_key, signature2)


@pytest.mark.parametrize('private_key', [0, secp256k1.n])
def test_schnorr_sign_invalid_private_key(private_key):
    with pytest.raises(ValueError, match='Private key must be an integer in the range 1..n-1'):
        schnorr_sign(b'\x00' * 32, private_key, b'\x00' * 32)


def test_schnorr_verify_invalid_lengths():
    public_key = x_only(secp256k1.G)

    assert not schnorr_verify(b'\x00' * 32, public_key[:31], b'\x00' * 64)
    assert not schnorr_verify(b'\x00' * 32, public_key, b'\x00' * 63)


def test_lift_x():
    point = lift_x(secp256k1.G.x)

    assert point == secp256k1.G  # y coordinate of the generator is even
    assert lift_x(secp256k1.p) is None
    assert lift_x(5) is None  # 5^3 + 7 is not a square modulo p


# Test vectors from BIP-341: (internal public key, merkle root, tweak, output key)
BIP341_TWEAK_VECTORS = [
    (
        'd6889cb081036e0faefa3a35157ad71086b123b2b144b649798b494c300a961d',
        '',
        'b86e7be8f39bab32a6f2c0443abbc210f0edac0e2c53d501b36b64437d9c6c70',
        '53a1f6e454df1aa2776a2814a721372d6258050de330b3c6d10ee8f4e0dda343',
    ),
    (
        '187791b6f712a8ea41c8ecdd0ee77fab3e85263b37e1ec18a3651926b3a6cf27',
        '5b75adecf53548f3ec6ad7d78383bf84cc57b55a3127c72b9a2481752dd88b21',
        'cbd8679ba636c1110ea247542cfbd964131a6be84f873f7f3b62a777528ed001',
        '147c9c57132f6e7ecddba9800bb0c4449251c92a1e60371ee77557b6620f3ea3',
    ),
    (
        '93478e9488f956df2396be2ce6c5cced75f900dfa18e7dabd2428aae78451820',
        'c525714a7f49c28aedbbba78c005931a81c234b2f6c99a73e4d06082adc8bf2b',
        '6af9e28dbf9d6aaf027696e2598a5b3d056f5fd2355a7fd5a37a0e5008132d30',
        'e4d810fd50586274face62b8a807eb9719cef49c04177cc6b76a9a4251d5450e',
    ),
    (
        'ee4fe085983462a184015d1f782d6a5f8b9c2b60130aff050ce221ecf3786592',
        '6c2dc106ab816b73f9d07e3cd1ef2c8c1256f519748e0813e4edd2405d277bef',
        '9e0517edc8259bb3359255400b23ca9507f2a91cd1e4250ba068b4eafceba4a9',
        '712447206d7a5238acc7ff53fbe94a3b64539ad291c7cdbc490b7577e4b17df5',
    ),
    (
        'f9f400803e683727b14f463836e1e78e1c64417638aa066919291a225f0e8dd8',
        'ab179431c28d3b68fb798957faf5497d69c883c6fb1e1cd9f81483d87bac90cc',
        '639f0281b7ac49e742cd25b7f188657626da1ad169209078e2761cefd91fd65e',
        '77e30a5522dd9f894c3f8b8bd4c4b2cf82ca7da8a3ea6a239655c39c050ab220',
    ),
    (
        'e0dfe2300b0dd746a3f8674dfd4525623639042569d829c7f0eed9602d263e6f',
        'ccbd66c6f7e8fdab47b3a486f59d28262be857f30d4773f2d5ea47f7761ce0e2',
        'b57bfa183d28eeb6ad688ddaabb265b4a41fbf68e5fed2c72c74de70d5a786f4',
        '91b64d5324723a985170e4dc5a0f84c041804f2cd12660fa5dec09fc21783605',
    ),
    (
        '55adf4e8967fbd2e29f20ac896e60c3b0f1d5b0efa9d34941b5958c7b0a0312d',
        '2f6b2c5397b6d68ca18e09a3f05161668ffe93a988582d55c6f07bd5b3329def',
        '6579138e7976dc13b6a92f7bfd5a2fc7684f5ea42419d43368301470f3b74ed9',
        '75169f4001aa68f15bbed28b218df1d0a62cbbcf1188c6665110c293c907b831',
    ),
]


@pytest.mark.parametrize('internal_key,merkle_root,tweak,output_key', BIP341_TWEAK_VECTORS)
def test_taproot_tweak_bip341(internal_key, merkle_root, tweak, output_key):
    calculated_tweak = taproot_tweak(bytes.fromhex(internal_key), bytes.fromhex(merkle_root))
    tweaked_point = lift_x(int(internal_key, 16)) + calculated_tweak * secp256k1.G

    assert calculated_tweak == int(tweak, 16)
    assert x_only(tweaked_point).hex() == output_key


# Test vectors from BIP-341 key path spending: (internal private key, merkle root,
# tweaked private key)
BIP341_PRIVATE_KEY_VECTORS = [
    (
        '6b973d88838f27366ed61c9ad6367663045cb456e28335c109e30717ae0c6baa',
        '',
        '2405b971772ad26915c8dcdf10f238753a9b837e5f8e6a86fd7c0cce5b7296d9',
    ),
    (
        '1e4da49f6aaf4e5cd175fe08a32bb5cb4863d963921255f33d3bc31e1343907f',
        '5b75adecf53548f3ec6ad7d78383bf84cc57b55a3127c72b9a2481752dd88b21',
        'ea260c3b10e60f6de018455cd0278f2f5b7e454be1999572789e6a9565d26080',
    ),
    (
        'd3c7af07da2d54f7a7735d3d0fc4f0a73164db638b2f2f7c43f711f6d4aa7e64',
        'c525714a7f49c28aedbbba78c005931a81c234b2f6c99a73e4d06082adc8bf2b',
        '97323385e57015b75b0339a549c56a948eb961555973f0951f555ae6039ef00d',
    ),
    (
        'f36bb07a11e469ce941d16b63b11b9b9120a84d9d87cff2c84a8d4affb438f4e',
        'ccbd66c6f7e8fdab47b3a486f59d28262be857f30d4773f2d5ea47f7761ce0e2',
        'a8e7aa924f0d58854185a490e6c41f6efb7b675c0f3331b7f14b549400b4d501',
    ),
    (
        '415cfe9c15d9cea27d8104d5517c06e9de48e2f986b695e4f5ffebf230e725d8',
        '2f6b2c5397b6d68ca18e09a3f05161668ffe93a988582d55c6f07bd5b3329def',
        '241c14f2639d0d7139282aa6abde28dd8a067baa9d633e4e7230287ec2d02901',
    ),
    (
        'c7b0e81f0a9a0b0499e112279d718cca98e79a12e2f137c72ae5b213aad0d103',
        '6c2dc106ab816b73f9d07e3cd1ef2c8c1256f519748e0813e4edd2405d277bef',
        '65b6000cd2bfa6b7cf736767a8955760e62b6649058cbc970b7c0871d786346b',
    ),
    (
        '77863416be0d0665e517e1c375fd6f75839544eca553675ef7fdf4949518ebaa',
        'ab179431c28d3b68fb798957faf5497d69c883c6fb1e1cd9f81483d87bac90cc',
        'ec18ce6af99f43815db543f47b8af5ff5df3b2cb7315c955aa4a86e8143d2bf5',
    ),
]


@pytest.mark.parametrize('private_key,merkle_root,tweaked_private_key', BIP341_PRIVATE_KEY_VECTORS)
def test_taproot_tweak_private_key_bip341(private_key, merkle_root, tweaked_private_key):
    tweaked = taproot_tweak_private_key(int(private_key, 16), bytes.fromhex(merkle_root))

    assert tweaked == int(tweaked_private_key, 16)
    assert x_only(tweaked * secp256k1.G) == taproot_output_key(
        int(private_key, 16), bytes.fromhex(merkle_root)
    )


def test_taproot_output_key_without_script_tree():
    """BIP-86: output key of the key path only output for the internal private key"""
    output_key = taproot_output_key(
        0x6B973D88838F27366ED61C9AD6367663045CB456E28335C109E30717AE0C6BAA
    )

    assert output_key.hex() == '53a1f6e454df1aa2776a2814a721372d6258050de330b3c6d10ee8f4e0dda343'
