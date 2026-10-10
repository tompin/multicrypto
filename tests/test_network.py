import io
import socket
import struct
from unittest.mock import patch

import pytest

from multicrypto.coins import coins
from multicrypto.network import (
    ConnectionClosedError,
    NetworkError,
    Node,
    PeerAddress,
    TransactionRejectedError,
    broadcast_transaction,
    decode_addr_payload,
    discover_nodes,
    encode_network_address,
    encode_var_str,
    encode_varint,
    parse_node_address,
    read_varint,
    serialize_message,
)

BTC = coins['BTC']
MAGIC = BTC['network']['magic']

# Coinbase transaction of the bitcoin genesis block
GENESIS_TX = '01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff4d04ffff001d0104455468652054696d65732030332f4a616e2f32303039204368616e63656c6c6f72206f6e206272696e6b206f66207365636f6e64206261696c6f757420666f722062616e6b73ffffffff0100f2052a01000000434104678afdb0fe5548271967f1a67130b7105cd6a828e03909a67962e0ea1f61deb649f6bc3f4cef38c4f35504e51ec112de5c384df7ba0b8d578a4c702b6bf11d5fac00000000'
GENESIS_TX_ID = '4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b'


def version_payload(user_agent='/Satoshi:30.0.0/', start_height=900000):
    return (
        struct.pack('<iQq', 70016, 1033, 1700000000)
        + encode_network_address('10.0.0.1', 50000, 0)
        + encode_network_address('0.0.0.0', 0, 1033)
        + struct.pack('<Q', 1234)
        + encode_var_str(user_agent)
        + struct.pack('<i', start_height)
        + b'\x01'
    )


def addr_payload(*addresses):
    payload = encode_varint(len(addresses))
    for host, port in addresses:
        payload += struct.pack('<I', 1700000000) + encode_network_address(host, port, 1)
    return payload


def reject_payload(message, code, reason, data):
    return encode_var_str(message) + bytes([code]) + encode_var_str(reason) + data


class FakeNode:
    """Socket replacement which answers messages sent to it using `handlers`.

    Each handler gets the payload and returns a list of (command, payload) tuples to send back.
    """

    def __init__(self, handlers=None, magic=MAGIC):
        self.magic = magic
        self.handlers = {
            'version': lambda payload: [('version', version_payload()), ('verack', b'')],
        }
        self.handlers.update(handlers or {})
        self.incoming = b''
        self.sent = []
        self.closed = False

    def push(self, command, payload=b''):
        self.incoming += serialize_message(self.magic, command, payload)

    def sendall(self, data):
        command = data[4:16].rstrip(b'\x00').decode()
        payload = data[24:]
        self.sent.append((command, payload))
        handler = self.handlers.get(command)
        for response in handler(payload) if handler else []:
            self.push(*response)

    def recv(self, size):
        if self.closed:
            return b''
        if not self.incoming:
            raise socket.timeout('timed out')
        data, self.incoming = self.incoming[:size], self.incoming[size:]
        return data

    def settimeout(self, timeout):
        pass

    def getpeername(self):
        return ('203.0.113.5', 8333)

    def close(self):
        self.closed = True

    def sent_commands(self):
        return [command for command, _ in self.sent]


@pytest.fixture
def fake_node():
    node = FakeNode()
    with patch('multicrypto.network.socket.create_connection', return_value=node):
        yield node


def test_serialize_message():
    assert serialize_message(MAGIC, 'verack').hex() == (
        'f9beb4d976657261636b000000000000000000005df6e0e2'
    )


@pytest.mark.parametrize('value', [0, 0xFC, 0xFD, 0xFFFF, 0x10000, 0xFFFFFFFF, 0x100000000])
def test_varint_round_trip(value):
    assert read_varint(io.BytesIO(encode_varint(value))) == value


def test_decode_addr_payload():
    payload = addr_payload(('1.2.3.4', 8333), ('2001:db8::1', 18333))

    assert decode_addr_payload(payload) == [
        PeerAddress('1.2.3.4', 8333, services=1, timestamp=1700000000),
        PeerAddress('2001:db8::1', 18333, services=1, timestamp=1700000000),
    ]


def test_node_requires_network_definition():
    with pytest.raises(ValueError, match='not defined'):
        Node(coins['BTCH'], '127.0.0.1')


def test_node_uses_default_port():
    assert Node(BTC, '127.0.0.1').port == 8333
    assert Node(BTC, '127.0.0.1', port=1234).port == 1234


def test_discover_nodes():
    def getaddrinfo(host, port, type):
        if host == 'dnsseed.bluematt.me':
            raise socket.gaierror('Name or service not known')
        return [
            (socket.AF_INET, type, 6, '', ('1.2.3.4', port)),
            (socket.AF_INET6, type, 6, '', ('2001:db8::1', port, 0, 0)),
        ]

    with patch('multicrypto.network.socket.getaddrinfo', side_effect=getaddrinfo):
        nodes = discover_nodes(BTC)

    assert nodes == [PeerAddress('1.2.3.4', 8333), PeerAddress('2001:db8::1', 8333)]


def test_connect_performs_handshake(fake_node):
    with Node(BTC, '203.0.113.5') as node:
        assert node.peer_version == {
            'version': 70016,
            'services': 1033,
            'timestamp': 1700000000,
            'user_agent': '/Satoshi:30.0.0/',
            'start_height': 900000,
        }

    assert fake_node.sent_commands() == ['version', 'verack']
    assert fake_node.closed
    version, services = struct.unpack('<iQ', fake_node.sent[0][1][:12])
    assert (version, services) == (70016, 0)


def test_connect_fails_on_connection_error():
    with patch('multicrypto.network.socket.create_connection', side_effect=OSError('refused')):
        with pytest.raises(NetworkError, match='Could not connect'):
            Node(BTC, '203.0.113.5').connect()


def test_handshake_timeout(fake_node):
    fake_node.handlers['version'] = lambda payload: [('version', version_payload())]

    with pytest.raises(NetworkError, match='Handshake .* timed out'):
        Node(BTC, '203.0.113.5').connect()
    assert fake_node.closed


def test_invalid_magic():
    with patch(
        'multicrypto.network.socket.create_connection',
        return_value=FakeNode(magic=coins['LTC']['network']['magic']),
    ):
        with pytest.raises(NetworkError, match='Invalid message start'):
            Node(BTC, '203.0.113.5').connect()


def test_invalid_checksum(fake_node):
    with Node(BTC, '203.0.113.5') as node:
        message = bytearray(serialize_message(MAGIC, 'ping', b'\x00' * 8))
        message[20] ^= 0xFF
        fake_node.incoming += bytes(message)

        with pytest.raises(NetworkError, match='Invalid message checksum'):
            node.receive_message()


def test_receive_message_answers_ping(fake_node):
    with Node(BTC, '203.0.113.5') as node:
        fake_node.push('ping', b'12345678')
        fake_node.push('inv', b'\x00')

        message = node.receive_message()

    assert message.command == 'inv'
    assert fake_node.sent[-1] == ('pong', b'12345678')


def test_get_peers(fake_node):
    fake_node.handlers['getaddr'] = lambda payload: [
        ('addr', addr_payload(('203.0.113.5', 8333))),
        ('inv', b'\x00'),
        ('addr', addr_payload(('1.2.3.4', 8333), ('203.0.113.5', 8333), ('5.6.7.8', 8334))),
    ]

    with Node(BTC, '203.0.113.5') as node:
        peers = node.get_peers()

    assert [(peer.host, peer.port) for peer in peers] == [
        ('203.0.113.5', 8333),
        ('1.2.3.4', 8333),
        ('5.6.7.8', 8334),
    ]


def test_get_peers_returns_announcements_on_timeout(fake_node):
    fake_node.handlers['getaddr'] = lambda payload: [('addr', addr_payload(('1.2.3.4', 8333)))]

    with Node(BTC, '203.0.113.5') as node:
        peers = node.get_peers(timeout=1)

    assert peers == [PeerAddress('1.2.3.4', 8333, services=1, timestamp=1700000000)]


def test_send_transaction(fake_node):
    fake_node.handlers['ping'] = lambda payload: [('inv', b'\x00'), ('pong', payload)]

    with Node(BTC, '203.0.113.5') as node:
        transaction_id = node.send_transaction(GENESIS_TX)

    assert transaction_id == GENESIS_TX_ID
    assert fake_node.sent_commands() == ['version', 'verack', 'tx', 'ping']
    assert fake_node.sent[2][1] == bytes.fromhex(GENESIS_TX)


def test_send_transaction_ignores_other_pong(fake_node):
    fake_node.handlers['ping'] = lambda payload: [('pong', b'\x00' * 8)]

    with Node(BTC, '203.0.113.5') as node:
        with pytest.raises(NetworkError, match='No response'):
            node.send_transaction(GENESIS_TX)


def test_send_transaction_rejected(fake_node):
    transaction_hash = bytes.fromhex(GENESIS_TX_ID)[::-1]
    fake_node.handlers['tx'] = lambda payload: [
        ('reject', reject_payload('tx', 0x10, 'bad-txns-inputs-missingorspent', transaction_hash))
    ]

    with Node(BTC, '203.0.113.5') as node:
        with pytest.raises(TransactionRejectedError, match='bad-txns-inputs-missingorspent'):
            node.send_transaction(GENESIS_TX)


def test_send_transaction_disconnected(fake_node):
    def disconnect(payload):
        fake_node.closed = True
        return []

    fake_node.handlers['tx'] = disconnect

    with Node(BTC, '203.0.113.5') as node:
        with pytest.raises(TransactionRejectedError, match='closed the connection') as error:
            node.send_transaction(GENESIS_TX)

    assert isinstance(error.value.__cause__, ConnectionClosedError)


def test_send_message_requires_connection():
    with pytest.raises(NetworkError, match='Not connected'):
        Node(BTC, '203.0.113.5').send_message('ping')


@pytest.mark.parametrize(
    'value, expected',
    [
        ('1.2.3.4', PeerAddress('1.2.3.4', 8333)),
        ('1.2.3.4:18333', PeerAddress('1.2.3.4', 18333)),
        ('node.example.com:8334', PeerAddress('node.example.com', 8334)),
        ('2001:db8::1', PeerAddress('2001:db8::1', 8333)),
        ('[2001:db8::1]', PeerAddress('2001:db8::1', 8333)),
        ('[2001:db8::1]:18333', PeerAddress('2001:db8::1', 18333)),
    ],
)
def test_parse_node_address(value, expected):
    assert parse_node_address(value, 8333) == expected


@pytest.mark.parametrize(
    'value', ['1.2.3.4:port', '1.2.3.4:0', '1.2.3.4:65536', ':8333', '[::1', '[::1]8333']
)
def test_parse_node_address_invalid(value):
    with pytest.raises(ValueError, match='Invalid node'):
        parse_node_address(value, 8333)


def broadcasting_node():
    return FakeNode({'ping': lambda payload: [('pong', payload)]})


def test_broadcast_transaction_tries_next_node():
    nodes = [PeerAddress('203.0.113.5', 8333), PeerAddress('203.0.113.6', 8334)]
    with patch(
        'multicrypto.network.socket.create_connection',
        side_effect=[OSError('refused'), broadcasting_node()],
    ) as create_connection:
        transaction_id = broadcast_transaction(BTC, GENESIS_TX, nodes, timeout=5)

    assert transaction_id == GENESIS_TX_ID
    assert [call.args[0] for call in create_connection.call_args_list] == [
        ('203.0.113.5', 8333),
        ('203.0.113.6', 8334),
    ]


def test_broadcast_transaction_discovers_nodes():
    discovered = [PeerAddress(f'10.0.0.{i}', 8333) for i in range(20)]
    with patch('multicrypto.network.discover_nodes', return_value=discovered), patch(
        'multicrypto.network.socket.create_connection', side_effect=OSError('refused')
    ) as create_connection:
        with pytest.raises(NetworkError, match='any of 10 node'):
            broadcast_transaction(BTC, GENESIS_TX)

    assert create_connection.call_count == 10


def test_broadcast_transaction_no_nodes_found():
    with patch('multicrypto.network.discover_nodes', return_value=[]):
        with pytest.raises(NetworkError, match='No nodes found'):
            broadcast_transaction(BTC, GENESIS_TX)


def test_broadcast_transaction_stops_on_rejection():
    transaction_hash = bytes.fromhex(GENESIS_TX_ID)[::-1]
    rejecting_node = FakeNode(
        {
            'tx': lambda payload: [
                ('reject', reject_payload('tx', 0x10, 'bad-txns', transaction_hash))
            ]
        }
    )
    nodes = [PeerAddress('203.0.113.5', 8333), PeerAddress('203.0.113.6', 8333)]
    with patch(
        'multicrypto.network.socket.create_connection',
        side_effect=[rejecting_node, broadcasting_node()],
    ) as create_connection:
        with pytest.raises(TransactionRejectedError, match='bad-txns'):
            broadcast_transaction(BTC, GENESIS_TX, nodes)

    assert create_connection.call_count == 1
