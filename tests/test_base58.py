import pytest

from multicrypto.base58 import bytes_to_base58, base58_to_int, base58_to_bytes

bytes_to_base58_test_data = [
    (b'', ''),
    (b'\x00', '1'),
    (b'\x00\x00\x00\x00\x01', '11112'),
    (b'\x01', '2'),
    (b'\x11', 'J'),
    (b'b\x15%s\xfe\\\xa9\xc9\x92\xc4\xc8_\xae\xe6\r\xd6\x01\xfc^\x83\xe1\xb2\x94V\x8f\xdbZs4x\xa1\x19',
     '7bsf4iS37xtdqVj82HFEZQ6gd2PdpA79i8zjk5RGXpZW'),
    (b'\x08\x95A\x17\x0f\x88^S\xa6B\xf5\xed+-\x85\x97h\xb6\xd3\xeaSf\x13#\xd74\xb3\xfe\xaf\x88\x97\x9f',
     'aWGF5LG5rtkykSJuusdhFkt9ozaSyRHeuDH68mrps7L'),
    (b'mdZ\xbd\xe7\x8f\x85k~\xc5+\xa8!\xc4\x14\x87\xbd\xf0\xd3\xdc.\x83\xe7\x9aSY0G\xeaJo\xd2',
     '8N2CCREu3c2LSZ7BcRa7jcTf7NkMsYA1mVpLArzPxM3w'),
    (b'`\x1a\xc2-\x85!?\x19\xdf\x1e\x16\x1ev\x1b\xaaWZ\xc1\x82\x04\xa7_\x82\x02$\x05\xff\x88N\x15o\xe9',
     '7U9oepF5qpGfSmpZWA5PQuVMsHUG8dvamqyKww6ispwJ'),
    (b'QrP\x1a\xc2;wy$\xc9\xe55\xff\xbc\xa5\x92\x93\xce\x05\xf4};N\xf5\x8b\n\x8c\xa3\xfe\x9d\x88\x9f',
     '6Uw86sPqdE5KZGajQpLhji6gHZJbNe8CVH6wvJ8qzSJz'),
    (b'g\x8e\xd17\xb4{\xa5\xa6*\xc7\xeev\x8fL\xfacr\xd1.]\xdcF\x10\xae\x17\xc9l4m\xae/r',
     '7yFJU9pgTq5iZLDZDN6d4K8ZNVe1GhXsLLzrH896gwy3'),
    (b"!\xcb\x1c\xd5\xa8gy<U\x82'n&c\xdc\xd4\xe54\xa3\xf9\xc2\xfc*\xa4\xc9\x03\xf0 \xed\x16\x97b",
     '3Gv66bZ2i2PjzhsS55U2P4hBiarTiQXmFzu3c5HNMhuB')
]

base58_to_bytes_test_data = [(y, x) for (x, y) in bytes_to_base58_test_data]

base58_to_int_test_data = [
    ('1', 0),
    ('1111111111112', 1),
    ('2', 1),
    ('J', 17),
    ('7bsf4iS37xtdqVj82HFEZQ6gd2PdpA79i8zjk5RGXpZW',
     44364021441316591631148327783711028887656920940609971662428502375251146481945),
    ('aWGF5LG5rtkykSJuusdhFkt9ozaSyRHeuDH68mrps7L',
     3882212236545208210435008046337986512778839084132684177574347797284637939615),
    ('8N2CCREu3c2LSZ7BcRa7jcTf7NkMsYA1mVpLArzPxM3w',
     49479411479041186568741565101873351285948211783734943856527014408433850544082),
    ('7U9oepF5qpGfSmpZWA5PQuVMsHUG8dvamqyKww6ispwJ',
     43469311653686900271573001492300659828095443318116793996960676828658028343273),
    ('6Uw86sPqdE5KZGajQpLhji6gHZJbNe8CVH6wvJ8qzSJz',
     36839314161750717624810596307212723549894265905257237956045150402380239308959),
    ('7yFJU9pgTq5iZLDZDN6d4K8ZNVe1GhXsLLzrH896gwy3',
     46840559654065592451673077450760248701463582899810463010842609239728721899378),
    ('3Gv66bZ2i2PjzhsS55U2P4hBiarTiQXmFzu3c5HNMhuB',
     15285192966499184634992179212489090959874552004758652561965980071027226875746)
]


@pytest.mark.parametrize("bytes_input,result_b58", bytes_to_base58_test_data)
def test_bytes_to_base58(bytes_input, result_b58):
    assert bytes_to_base58(bytes_input) == result_b58


@pytest.mark.parametrize("base58_input,result_int", base58_to_int_test_data)
def test_base58_to_int(base58_input, result_int):
    assert base58_to_int(base58_input) == result_int


@pytest.mark.parametrize("b58_data,result_bytes", base58_to_bytes_test_data)
def test_base58_to_bytes(b58_data, result_bytes):
    assert base58_to_bytes(b58_data) == result_bytes
