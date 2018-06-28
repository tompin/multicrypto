import hashlib
from unittest.mock import patch

from fastecdsa.curve import secp256k1
from fastecdsa.ecdsa import verify
from fastecdsa.point import Point

from multicrypto.coins import coins
from multicrypto.consts import OP_DUP, OP_HASH160, OP_PUSH_20, OP_EQUALVERIFY, OP_CHECKSIG
from multicrypto.transaction import Transaction, POSTransaction
from multicrypto.utils import double_sha256_hex, reverse_byte_hex, encode_point


def test_verify_one_input():
    """ BTC transaction:
     b2fcadebe12b9f8ec1820ef22e1e4fafb119876149bb9013a65dbc91c4921549 """

    r = int('059c71db0d01d284fc4589c03b09947d21b98d7cefae614ac1039b6de0fa28ba', 16)
    s = int('6cde9c0649fe2242b1dd90f40615e1bb247280b8f152c0ae9151b9c4d7abaf87', 16)
    x = int('8cc516ad062ac55d5ed980c4f743a366621fa409060188df3c39e289720090ae', 16)
    y = int('bba61faf69a3f2a39fac2745a565e5b2a4a9a5c90a71c9ee770135695231832c', 16)
    public_key = Point(x, y, secp256k1)
    encoded_public_key = b'\x04' + x.to_bytes(32, byteorder='big') + y.to_bytes(32, byteorder='big')
    hashed_public_key = hashlib.sha256(encoded_public_key).digest()
    digest_public_key = hashlib.new('ripemd160', hashed_public_key).digest()
    funding_script = OP_DUP + OP_HASH160 + OP_PUSH_20 + digest_public_key + OP_EQUALVERIFY + OP_CHECKSIG
    raw_transaction_mod = '020000000169ab945e88fc3d73d052e8c3ce546309a635458fea2c6b3e69981945b0d2a62201000000' + reverse_byte_hex(
        hex(len(funding_script))[2:]) + funding_script.hex() + 'fdffffff025641e52d000000001976a914759d667709c9d1fbd7aa26537b5c441747d88f2588ac80c3c901000000001976a9146928f2f330f57e6916543481ab3af69597ae289d88ac06d70700' + '01000000'

    result = verify((r, s), raw_transaction_mod, public_key, secp256k1, double_sha256_hex)

    assert result


def test_verify_one_input_zeit():
    """ ZEIT transaction:
     975e4d8a5530ba43dd607c62af925ad20a5347e2fd5873c65364bc4a89b6a829 """

    r = int('5f69442b8ffd4ce39997c27a3f1c134a1ce6d1cdeb6dd39c5191d3e748419577', 16)
    s = int('67d9c5b4144c80aac91701130686b66dc3da15799de960edb22ee9f90be6f554', 16)
    x = int('771b0c5df5773a9c3f8da066d6b9e8e577025caeaa15ef1289c9e83050124eca', 16)
    y = int('c71f2fe45289be22f857d721489e871dce3e7e6a951534f0504c5784c796def9', 16)
    public_key = Point(x, y, secp256k1)
    encoded_public_key = encode_point(public_key, compressed=True)
    hashed_public_key = hashlib.sha256(encoded_public_key).digest()
    digest_public_key = hashlib.new('ripemd160', hashed_public_key).digest()
    funding_script = OP_DUP + OP_HASH160 + OP_PUSH_20 + digest_public_key + OP_EQUALVERIFY + OP_CHECKSIG
    raw_transaction_mod = '010000006bbc345b01ec2636bc0dc4a0fa774a1448b5cd26f90b1ebf6ab7474cb87b003dc15280043a00000000' + \
                          reverse_byte_hex(hex(len(funding_script))[2:]) + funding_script.hex() + 'ffffffff016e2ae671000000001976a91415cdc3710d179a525dc6011f4588befc5a04ff4488ac00000000' + '01000000'

    result = verify((r, s), raw_transaction_mod, public_key, secp256k1, double_sha256_hex)

    assert result


def test_verify_two_inputs():
    """ BTC transaction:
     1e976937f0dadc7c7fac9b7c62291f7843bc781ec44ee65c41b9b9e4f10cf0b3 """

    r1 = int('6545773c1a86326a2e27b0c06af1eccc43304518e3be1f7fe3949a2a7fde8a6f', 16)
    s1 = int('7bf41875ef112a731835875e187086a322226759d410a2e8ee2fb91813340d43', 16)
    x1 = int('c0dae3dc13a30b6fc4fbe361a943680148cc028d96d91d6997cbbb572258b308', 16)
    y1 = int('17defc0d8dde6f62da3e4256ddb164b5847ef0112907e4d9e99c74035efe46c2', 16)
    public_key1 = Point(x1, y1, secp256k1)
    encoded_public_key1 = b'\x02' + x1.to_bytes(32, byteorder='big')
    hashed_public_key1 = hashlib.sha256(encoded_public_key1).digest()
    digest_public_key1 = hashlib.new('ripemd160', hashed_public_key1).digest()
    funding_script1 = OP_DUP + OP_HASH160 + OP_PUSH_20 + digest_public_key1 + OP_EQUALVERIFY + OP_CHECKSIG
    raw_transaction_mod1 = '0200000002999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a00000000' + reverse_byte_hex(
        hex(len(funding_script1))[2:]) + funding_script1.hex() + 'feffffff999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a01000000' + '00' + 'feffffff0286e75900000000001976a914f640fe9c961287aeceefe8499754aa4516c9a31c88acc00e1602000000001976a9140272b913f2755541abcdeeea8cb9845d615daa2b88acd9080800' + '01000000'
    r2 = int('75dbfcbe3f05076ff6ad90525afec4e8ca110fb80555fc3c91d5f2d54f82ee2c', 16)
    s2 = int('4a12501fd9704ae713ba2cd1500bca3e9cb34bb0bae145921c91ddce9c32017f', 16)
    x2 = int('7940f42f1dbfc7af95ce0b8c9bc2565cc1b0b1e39924941dd07833a01e4f6d05', 16)
    y2 = int('9c29c8439dc9e60b3d3809f7e9b648f3a78229801d691b581bd6492112154625', 16)
    public_key2 = Point(x2, y2, secp256k1)
    encoded_public_key2 = b'\x03' + x2.to_bytes(32, byteorder='big')
    hashed_public_key2 = hashlib.sha256(encoded_public_key2).digest()
    digest_public_key2 = hashlib.new('ripemd160', hashed_public_key2).digest()
    funding_script2 = OP_DUP + OP_HASH160 + OP_PUSH_20 + digest_public_key2 + OP_EQUALVERIFY + OP_CHECKSIG

    raw_transaction_mod2 = '0200000002999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a00000000' + '00' + 'feffffff999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a01000000' + reverse_byte_hex(
        hex(len(funding_script2))[2:]) + funding_script2.hex() + 'feffffff0286e75900000000001976a914f640fe9c961287aeceefe8499754aa4516c9a31c88acc00e1602000000001976a9140272b913f2755541abcdeeea8cb9845d615daa2b88acd9080800' + '01000000'

    result1 = verify((r1, s1), raw_transaction_mod1, public_key1, secp256k1, double_sha256_hex)
    result2 = verify((r2, s2), raw_transaction_mod2, public_key2, secp256k1, double_sha256_hex)

    assert result1
    assert result2


@patch('multicrypto.transaction.sign')
def test_create_p2pkh_transaction_single_input_two_outputs(sign_mock):
    """ BTC transaction b2fcadebe12b9f8ec1820ef22e1e4fafb119876149bb9013a65dbc91c4921549 """

    raw_transaction = '020000000169ab945e88fc3d73d052e8c3ce546309a635458fea2c6b3e69981945b0d2a622' \
                      '010000008a4730440220059c71db0d01d284fc4589c03b09947d21b98d7cefae614ac1039b' \
                      '6de0fa28ba02206cde9c0649fe2242b1dd90f40615e1bb247280b8f152c0ae9151b9c4d7ab' \
                      'af870141048cc516ad062ac55d5ed980c4f743a366621fa409060188df3c39e289720090ae' \
                      'bba61faf69a3f2a39fac2745a565e5b2a4a9a5c90a71c9ee770135695231832cfdffffff02' \
                      '5641e52d000000001976a914759d667709c9d1fbd7aa26537b5c441747d88f2588ac80c3c9' \
                      '01000000001976a9146928f2f330f57e6916543481ab3af69597ae289d88ac06d70700'
    sign_mock.return_value = (
        2537978187957076796562690004660801047397330004528620476924739080817015924922,
        49243104537355692482079219689264807514166015800858788389587884050872189824903
    )
    inputs = [{'transaction_id': '69ab945e88fc3d73d052e8c3ce546309a635458fea2c6b3e69981945b0d2a622',
               'output_index': 1,
               'script': '76a914759d667709c9d1fbd7aa26537b5c441747d88f2588ac',
               # private_key='5J2S79PkfxFGfknLFWtKTTC1wZ7sxSuhrYSnJVejVUj1LFZybSA',
               'private_key': 12475340246878237482690613272958836260975458135334145710205272338180483502080,
               'satoshis': 800000000}]
    outputs = [{'address': '1Bitcoinmw2Ui5A547MRjgnGi1Pk25jBzi', 'satoshis': 769999190},
               {'address': '1Ab31L9qTsKiDsC4cExAzH4tbukE7uv3XW', 'satoshis': 30000000}]

    transaction = Transaction(
        coin=coins['BTC'],
        inputs=inputs,
        outputs=outputs,
        sequence=b'\xfd\xff\xff\xff',
        lock_time=b'\x06\xd7\x07\x00',
        version=b'\x02\x00\x00\x00'
    )
    transaction.create()

    assert transaction.raw == raw_transaction
    assert transaction.id == 'b2fcadebe12b9f8ec1820ef22e1e4fafb119876149bb9013a65dbc91c4921549'


@patch('multicrypto.transaction.sign')
def test_create_p2pkh_transaction_two_inputs_two_outputs(sign_mock):
    """ BTC transaction 1e976937f0dadc7c7fac9b7c62291f7843bc781ec44ee65c41b9b9e4f10cf0b3 """

    raw_transaction = '0200000002999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a' \
                      '000000006a47304402206545773c1a86326a2e27b0c06af1eccc43304518e3be1f7fe3949a' \
                      '2a7fde8a6f02207bf41875ef112a731835875e187086a322226759d410a2e8ee2fb9181334' \
                      '0d43012102c0dae3dc13a30b6fc4fbe361a943680148cc028d96d91d6997cbbb572258b308' \
                      'feffffff999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a01' \
                      '0000006a473044022075dbfcbe3f05076ff6ad90525afec4e8ca110fb80555fc3c91d5f2d5' \
                      '4f82ee2c02204a12501fd9704ae713ba2cd1500bca3e9cb34bb0bae145921c91ddce9c3201' \
                      '7f0121037940f42f1dbfc7af95ce0b8c9bc2565cc1b0b1e39924941dd07833a01e4f6d05fe' \
                      'ffffff0286e75900000000001976a914f640fe9c961287aeceefe8499754aa4516c9a31c88' \
                      'acc00e1602000000001976a9140272b913f2755541abcdeeea8cb9845d615daa2b88acd908' \
                      '0800'
    sign_mock.side_effect = [
        (int('6545773c1a86326a2e27b0c06af1eccc43304518e3be1f7fe3949a2a7fde8a6f', 16),
         int('7bf41875ef112a731835875e187086a322226759d410a2e8ee2fb91813340d43', 16)),
        (int('75dbfcbe3f05076ff6ad90525afec4e8ca110fb80555fc3c91d5f2d54f82ee2c', 16),
         int('4a12501fd9704ae713ba2cd1500bca3e9cb34bb0bae145921c91ddce9c32017f', 16))
    ]
    inputs = [
        {'transaction_id': '999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a',
         'output_index': 0,
         'script': '76a914b1b685a57154a3c3265b8648101ea6fbba8fad7288ac',
         'private_key': 43265286516710475498079662292151387463063605274999989765271924584279496871562,
         # KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu
         'satoshis': 10892722},
        {'transaction_id': '999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a',
         'output_index': 1,
         'script': '76a9148ad42af2b409e228388a446731d8c95da725e26088ac',
         'private_key': 57600979085682226857778837041313156146409772100816702579179860421765513727329,
         # L1VFvRCJs8rr5rZcJkaB67ALC86yG8UECgNgLn22pYaw3iAB9bad
         'satoshis': 30000000}]
    outputs = [{'address': '1PT566Ng2hKvDooBNhp7UHU3PrF3UdCgjf', 'satoshis': 5891974},
               {'address': '1DwnUXv5XbBj6v5wb7Ystbedj99y2Nv2i', 'satoshis': 35000000}]

    transaction = Transaction(
        coin=coins['BTC'],
        inputs=inputs,
        outputs=outputs,
        sequence=b'\xfe\xff\xff\xff',
        lock_time=b'\xd9\x08\x08\x00',
        version=b'\x02\x00\x00\x00'
    )
    transaction.create()

    assert transaction.raw == raw_transaction
    assert transaction.id == '1e976937f0dadc7c7fac9b7c62291f7843bc781ec44ee65c41b9b9e4f10cf0b3'


@patch('multicrypto.transaction.sign')
def test_create_zeit_p2pkh_transaction_single_input_single_output(sign_mock):
    """ ZEIT transaction 975e4d8a5530ba43dd607c62af925ad20a5347e2fd5873c65364bc4a89b6a829 """

    raw_transaction = '010000006bbc345b01ec2636bc0dc4a0fa774a1448b5cd26f90b1ebf6ab7474cb87b003dc1' \
                      '5280043a000000006a47304402205f69442b8ffd4ce39997c27a3f1c134a1ce6d1cdeb6dd3' \
                      '9c5191d3e748419577022067d9c5b4144c80aac91701130686b66dc3da15799de960edb22e' \
                      'e9f90be6f554012103771b0c5df5773a9c3f8da066d6b9e8e577025caeaa15ef1289c9e830' \
                      '50124ecaffffffff016e2ae671000000001976a91415cdc3710d179a525dc6011f4588befc' \
                      '5a04ff4488ac00000000'

    sign_mock.return_value = (
        0x5f69442b8ffd4ce39997c27a3f1c134a1ce6d1cdeb6dd39c5191d3e748419577,
        0x67d9c5b4144c80aac91701130686b66dc3da15799de960edb22ee9f90be6f554
    )
    inputs = [{'transaction_id': '3a048052c13d007bb84c47b76abf1e0bf926cdb548144a77faa0c40dbc3626ec',
               'output_index': 0,
               'script': '76a9141019136435d702c05d433cb404547e6fbcad085c88ac',
               # private_key='TaMECDUSKV6tt17Zrwai2Go4HgF6R8xSwDY1UTBeFFY6hMWNyY6n',
               'private_key': 75008817533290696227105990373334596279639239099625180499796393413953408726677,
               'satoshis': 1911009550}]
    outputs = [{'address': 'MZE3uG9NUKDS3ZPC8jgJqpL9MrXRFxRMYL', 'satoshis': 1910909550}]

    transaction = POSTransaction(
        coin=coins['ZEIT'],
        inputs=inputs,
        outputs=outputs,
        transaction_time=b'\x6b\xbc\x34\x5b'
    )
    transaction.create()

    assert transaction.raw == raw_transaction
    assert transaction.id == '975e4d8a5530ba43dd607c62af925ad20a5347e2fd5873c65364bc4a89b6a829'


# @patch('multicrypto.transaction.sign')
# def test_create_p2pkh_transaction_three_inputs_one_output(sign_mock):
#     """ BTC transaction 064fafbbdf803d6711d8f3c70e8a8e089f42c540f399b53c6596cb2c3d077875 """
#
#     raw_transaction = '02000000000103491592c491bc5da61390bb49618719b1af4f1e2ef20e82c18e9f2be1ebad' \
#                       'fcb2000000008a47304402203e6d476f81e6e4b689e93ce4fd81f0fc0953c4495bdbeeb2a7' \
#                       '695c83b2be20d50220558943de300a9deea48a0cd0d362f82764aeb87c822e94c867725d72' \
#                       'f1039c720141048cc516ad062ac55d5ed980c4f743a366621fa409060188df3c39e2897200' \
#                       '90aebba61faf69a3f2a39fac2745a565e5b2a4a9a5c90a71c9ee770135695231832cfeffff' \
#                       'ff774aca1b9bd505e46d766e4c9246b588d5973684e9d73ed1f866c157d9890f9001000000' \
#                       '17160014af08c5ac0e2453054378e1b7ec4e60ab8c47ef5afeffffffc43892797f71459b71' \
#                       '17da6df58338c6b0a6d60416a7c37a63bb25b6e3fd548e450000008b483045022100c846cd' \
#                       '45ff290e233e878eb16583ae9d1652092c84a401bed97cf475e90e7de402204bfb314d4c16' \
#                       '8e92b07b67b12bf51ca320120611d2b3c2cbb270e2eb10a64b4a0141048cc516ad062ac55d' \
#                       '5ed980c4f743a366621fa409060188df3c39e289720090aebba61faf69a3f2a39fac2745a5' \
#                       '65e5b2a4a9a5c90a71c9ee770135695231832cfeffffff016561802f0000000017a9141563' \
#                       '3f6cbe6c23b15aeb5aaa0d1e42b06522a7e18700024730440220241f62d59690b0fc99ab22' \
#                       '381788ac468c54a7d591456ae02360ea8877530da1022001e758325fd7870b15d8d52d5f2c' \
#                       '43f9d0959e00c93c67c4c9bce4654470b808012103ca53c43da64dbe03a5a6937898a8944d' \
#                       'ba2f80526c90defd46e1c70bed0a572c002cee0700'
#
#     sign_mock.side_effect = [
#         (int('3e6d476f81e6e4b689e93ce4fd81f0fc0953c4495bdbeeb2a7695c83b2be20d5', 16),
#          int('558943de300a9deea48a0cd0d362f82764aeb87c822e94c867725d72f1039c72', 16)),
#         (int('241f62d59690b0fc99ab22381788ac468c54a7d591456ae02360ea8877530da1', 16),
#          int('01e758325fd7870b15d8d52d5f2c43f9d0959e00c93c67c4c9bce4654470b808', 16)),
#         (int('00c846cd45ff290e233e878eb16583ae9d1652092c84a401bed97cf475e90e7de4', 16),
#          int('4bfb314d4c168e92b07b67b12bf51ca320120611d2b3c2cbb270e2eb10a64b4a', 16))
#     ]
#
#     inputs = [
#         {'transaction_id': 'b2fcadebe12b9f8ec1820ef22e1e4fafb119876149bb9013a65dbc91c4921549',
#          'output_index': 0,
#          'script': '76a914759d667709c9d1fbd7aa26537b5c441747d88f2588ac',
#          'private_key': 12475340246878237482690613272958836260975458135334145710205272338180483502080,  # 5J2S79PkfxFGfknLFWtKTTC1wZ7sxSuhrYSnJVejVUj1LFZybSA
#          'satoshis': 769999190},
#         {'transaction_id': '900f89d957c166f8d13ed7e9843697d588b546924c6e766de405d59b1bca4a77',
#          'output_index': 1,
#          'script': 'a9149c21b1d68fa2fe8c74cef825462813b358f58b9a87',
#          'private_key': 34000148492062219691113509907075374683881483977305782540856005451828115038495,  #  Kyjq8Y6oQbyjiF5PHYZ59MwTrJGdjnXojcgmo83RCcVEtqPsQZ8n
#          'satoshis': 30000000
#          },
#         {'transaction_id': '999422d4e2a72c7bd5890922129498b7b0e68141aadb6ec920b6baee57e2586a',
#          'output_index': 1,
#          'script': '8e54fde3b625bb637ac3a71604d6a6b0c63883f56dda17719b45717f799238c4',
#          'private_key': 12475340246878237482690613272958836260975458135334145710205272338180483502080,  # 5J2S79PkfxFGfknLFWtKTTC1wZ7sxSuhrYSnJVejVUj1LFZybSA
#          'satoshis': 8619895}
#     ]
#     outputs = [{'address': '33e71Ria2mdGy5Hj2FUr7zGYZH4q3manex', 'satoshis': 796942693}]
#
#     transaction = Transaction(
#         coin=coins['BTC'],
#         inputs=inputs,
#         outputs=outputs,
#         sequence=b'\xfe\xff\xff\xff',
#         lock_time=b'\xd9\x08\x08\x00',
#         version=b'\x02\x00\x00\x00'
#     )
#     transaction.create()
#
#     assert transaction.raw == raw_transaction
#     assert transaction.id == '1e976937f0dadc7c7fac9b7c62291f7843bc781ec44ee65c41b9b9e4f10cf0b3'
