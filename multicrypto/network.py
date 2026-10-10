"""Communication with cryptocurrency nodes using the Bitcoin peer-to-peer protocol.

Coins which support it define a ``network`` entry in :mod:`multicrypto.coins` with the
message start bytes (``magic``), default ``port``, ``protocol_version`` and DNS ``seeds``.

The module allows to:

* find nodes of the network using DNS seeds (:func:`discover_nodes`),
* connect to a node and perform the version handshake (:class:`Node`),
* fetch addresses of the peers known to the node (:meth:`Node.get_peers`),
* broadcast a raw transaction to the node (:meth:`Node.send_transaction`) or to the first
  reachable node of the network (:func:`broadcast_transaction`).

Protocol reference: https://developer.bitcoin.org/reference/p2p_networking.html
"""

import io
import ipaddress
import logging
import random
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from multicrypto.utils import double_sha256, reverse_byte_hex

logger = logging.getLogger(__name__)

Coin = Dict[str, Any]

DEFAULT_TIMEOUT = 30  # in seconds
USER_AGENT = '/multicrypto/'
HEADER_SIZE = 24
MAX_PAYLOAD_SIZE = 32 * 1024 * 1024
NODE_NETWORK = 1
MAX_BROADCAST_ATTEMPTS = 10


class NetworkError(Exception):
    """Raised when communication with a node fails."""


class ConnectionClosedError(NetworkError):
    """Raised when the node closes the connection."""


class TransactionRejectedError(NetworkError):
    """Raised when the node rejects the transaction sent to it."""


@dataclass(frozen=True)
class PeerAddress:
    host: str
    port: int
    services: int = 0
    timestamp: int = 0


@dataclass(frozen=True)
class Message:
    command: str
    payload: bytes


def get_network_params(coin: Coin) -> Dict[str, Any]:
    if 'network' not in coin:
        raise ValueError(f'Peer-to-peer network is not defined for coin {coin["name"]}')
    return coin['network']


def encode_varint(value: int) -> bytes:
    if value < 0xFD:
        return struct.pack('<B', value)
    if value <= 0xFFFF:
        return b'\xfd' + struct.pack('<H', value)
    if value <= 0xFFFFFFFF:
        return b'\xfe' + struct.pack('<I', value)
    return b'\xff' + struct.pack('<Q', value)


def read_varint(stream: io.BytesIO) -> int:
    prefix = read_struct(stream, '<B')
    if prefix == 0xFD:
        return read_struct(stream, '<H')
    if prefix == 0xFE:
        return read_struct(stream, '<I')
    if prefix == 0xFF:
        return read_struct(stream, '<Q')
    return prefix


def read_struct(stream: io.BytesIO, fmt: str) -> Any:
    size = struct.calcsize(fmt)
    data = stream.read(size)
    if len(data) != size:
        raise NetworkError('Malformed message payload')
    return struct.unpack(fmt, data)[0]


def encode_var_str(value: str) -> bytes:
    encoded = value.encode()
    return encode_varint(len(encoded)) + encoded


def read_var_str(stream: io.BytesIO) -> str:
    length = read_varint(stream)
    return stream.read(length).decode(errors='replace')


def encode_network_address(host: str, port: int, services: int) -> bytes:
    """Encode address without the timestamp, as used in the version message."""
    ip = ipaddress.ip_address(host)
    if ip.version == 4:
        ip = ipaddress.IPv6Address(f'::ffff:{ip}')
    return struct.pack('<Q', services) + ip.packed + struct.pack('>H', port)


def read_network_address(stream: io.BytesIO) -> PeerAddress:
    services = read_struct(stream, '<Q')
    ip = ipaddress.IPv6Address(stream.read(16))
    port = read_struct(stream, '>H')
    host = str(ip.ipv4_mapped) if ip.ipv4_mapped else str(ip)
    return PeerAddress(host=host, port=port, services=services)


def decode_addr_payload(payload: bytes) -> List[PeerAddress]:
    stream = io.BytesIO(payload)
    addresses = []
    for _ in range(read_varint(stream)):
        timestamp = read_struct(stream, '<I')
        address = read_network_address(stream)
        addresses.append(
            PeerAddress(address.host, address.port, address.services, timestamp=timestamp)
        )
    return addresses


def decode_reject_payload(payload: bytes) -> Dict[str, Any]:
    stream = io.BytesIO(payload)
    return {
        'message': read_var_str(stream),
        'code': read_struct(stream, '<B'),
        'reason': read_var_str(stream),
        'data': stream.read(),
    }


def calculate_checksum(payload: bytes) -> bytes:
    return double_sha256(payload).digest()[:4]


def serialize_message(magic: bytes, command: str, payload: bytes = b'') -> bytes:
    return (
        magic
        + command.encode().ljust(12, b'\x00')
        + struct.pack('<I', len(payload))
        + calculate_checksum(payload)
        + payload
    )


def discover_nodes(coin: Coin) -> List[PeerAddress]:
    """Resolve DNS seeds of the coin network and return addresses of the nodes found."""
    network = get_network_params(coin)
    nodes = {}
    for seed in network.get('seeds', []):
        try:
            results = socket.getaddrinfo(seed, network['port'], type=socket.SOCK_STREAM)
        except socket.gaierror as error:
            logger.warning('Could not resolve DNS seed %s: %s', seed, error)
            continue
        for _family, _type, _proto, _canonname, sockaddr in results:
            host, port = sockaddr[0], sockaddr[1]
            nodes[(host, port)] = PeerAddress(host=host, port=port)
    return list(nodes.values())


def parse_node_address(value: str, default_port: int) -> PeerAddress:
    """Parse node address in ``host``, ``host:port`` or ``[ipv6]:port`` format."""
    host, port = value, default_port
    if value.startswith('['):
        host, separator, rest = value[1:].partition(']')
        if not separator or (rest and not rest.startswith(':')):
            raise ValueError(f'Invalid node address: {value}')
        if rest:
            port = rest[1:]
    elif value.count(':') == 1:
        host, port = value.split(':')
    try:
        port = int(port)
    except ValueError:
        raise ValueError(f'Invalid node port: {value}') from None
    if not host or not 0 < port < 65536:
        raise ValueError(f'Invalid node address: {value}')
    return PeerAddress(host=host, port=port)


class Node:
    """Connection to a single node of the coin peer-to-peer network.

    Can be used as a context manager, which connects to the node and closes the connection::

        with Node(coins['BTC'], '203.0.113.5') as node:
            peers = node.get_peers()
    """

    def __init__(
        self, coin: Coin, host: str, port: Optional[int] = None, timeout: float = DEFAULT_TIMEOUT
    ):
        network = get_network_params(coin)
        self.magic = network['magic']
        self.protocol_version = network['protocol_version']
        self.host = host
        self.port = port or network['port']
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self.peer_version: Dict[str, Any] = {}

    def __enter__(self) -> 'Node':
        return self.connect()

    def __exit__(self, *exc_info) -> None:
        self.close()

    def connect(self) -> 'Node':
        try:
            self.socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as error:
            raise NetworkError(f'Could not connect to {self.host}:{self.port}: {error}') from error
        try:
            self._handshake()
        except Exception:
            self.close()
            raise
        logger.info(
            'Connected to %s:%s (%s, protocol version %s, height %s)',
            self.host,
            self.port,
            self.peer_version['user_agent'],
            self.peer_version['version'],
            self.peer_version['start_height'],
        )
        return self

    def close(self) -> None:
        if self.socket:
            self.socket.close()
            self.socket = None

    def send_message(self, command: str, payload: bytes = b'') -> None:
        if not self.socket:
            raise NetworkError('Not connected to the node')
        logger.debug('Sending %s (%s bytes) to %s', command, len(payload), self.host)
        try:
            self.socket.sendall(serialize_message(self.magic, command, payload))
        except OSError as error:
            raise NetworkError(f'Could not send {command} message: {error}') from error

    def receive_message(self, timeout: Optional[float] = None) -> Message:
        """Receive next message from the node, answering pings on the way.

        :param timeout: Maximum time to wait for the message to start arriving
        :raises socket.timeout: When no message arrived within the timeout
        """
        while True:
            message = self._read_message(self.timeout if timeout is None else timeout)
            if message.command == 'ping':
                self.send_message('pong', message.payload)
                continue
            return message

    def get_peers(self, timeout: Optional[float] = None) -> List[PeerAddress]:
        """Ask the node for addresses of other nodes it knows about.

        Waits until the node responds with a list of addresses or the timeout expires. Nodes answer
        ``getaddr`` only once per connection, so subsequent calls could return nothing.
        """
        self.send_message('getaddr')
        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        peers = {}
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                message = self.receive_message(remaining)
            except socket.timeout:
                break
            if message.command != 'addr':
                continue
            addresses = decode_addr_payload(message.payload)
            for address in addresses:
                peers[(address.host, address.port)] = address
            # A single address is usually the node announcing itself, not the getaddr response
            if len(addresses) > 1:
                break
        return list(peers.values())

    def send_transaction(self, raw_transaction: str) -> str:
        """Send raw transaction (hex) to the node and return its id.

        After the transaction the node is pinged. Since messages are processed in order, the pong
        confirms the node processed the transaction. Nodes which still support ``reject`` messages
        report invalid transactions before that. Notice that the pong does not guarantee the node
        accepted the transaction to its mempool (e.g. when the fee is too low).
        """
        transaction = bytes.fromhex(raw_transaction)
        transaction_hash = double_sha256(transaction).digest()
        transaction_id = reverse_byte_hex(transaction_hash.hex())
        self.send_message('tx', transaction)
        nonce = random.getrandbits(64)
        self.send_message('ping', struct.pack('<Q', nonce))
        while True:
            try:
                message = self.receive_message()
            except socket.timeout as error:
                raise NetworkError(
                    f'No response from the node for transaction {transaction_id}'
                ) from error
            except ConnectionClosedError as error:
                raise TransactionRejectedError(
                    f'Node closed the connection after receiving transaction {transaction_id}'
                ) from error
            if message.command == 'reject':
                reject = decode_reject_payload(message.payload)
                if reject['message'] == 'tx' and reject['data'] == transaction_hash:
                    raise TransactionRejectedError(
                        f'Transaction {transaction_id} rejected: {reject["reason"]} '
                        f'(code {reject["code"]:#x})'
                    )
            elif message.command == 'pong' and message.payload == struct.pack('<Q', nonce):
                logger.info('Transaction %s sent to %s', transaction_id, self.host)
                return transaction_id

    def _handshake(self) -> None:
        self.send_message('version', self._create_version_payload())
        received_version = received_verack = False
        while not (received_version and received_verack):
            try:
                message = self.receive_message()
            except socket.timeout as error:
                raise NetworkError(f'Handshake with {self.host}:{self.port} timed out') from error
            if message.command == 'version':
                self.peer_version = self._decode_version_payload(message.payload)
                self.send_message('verack')
                received_version = True
            elif message.command == 'verack':
                received_verack = True

    def _create_version_payload(self) -> bytes:
        peer_host = self.socket.getpeername()[0]
        return (
            struct.pack('<iQq', self.protocol_version, 0, int(time.time()))
            + encode_network_address(peer_host, self.port, NODE_NETWORK)
            + encode_network_address('0.0.0.0', 0, 0)
            + struct.pack('<Q', random.getrandbits(64))
            + encode_var_str(USER_AGENT)
            + struct.pack('<i', 0)  # start height, we do not have any blocks
            + b'\x01'  # relay
        )

    @staticmethod
    def _decode_version_payload(payload: bytes) -> Dict[str, Any]:
        stream = io.BytesIO(payload)
        version = read_struct(stream, '<i')
        services = read_struct(stream, '<Q')
        timestamp = read_struct(stream, '<q')
        read_network_address(stream)  # our address as seen by the node
        read_network_address(stream)  # node address, usually empty
        read_struct(stream, '<Q')  # nonce
        return {
            'version': version,
            'services': services,
            'timestamp': timestamp,
            'user_agent': read_var_str(stream),
            'start_height': read_struct(stream, '<i'),
        }

    def _read_message(self, timeout: float) -> Message:
        header = self._read_exact(HEADER_SIZE, timeout)
        magic, command, length, checksum = struct.unpack('<4s12sI4s', header)
        if magic != self.magic:
            raise NetworkError(f'Invalid message start {magic.hex()}, expected {self.magic.hex()}')
        if length > MAX_PAYLOAD_SIZE:
            raise NetworkError(f'Message too big: {length} bytes')
        # Once the header arrived the payload is expected shortly, a timeout would break the stream
        try:
            payload = self._read_exact(length, self.timeout)
        except socket.timeout as error:
            raise NetworkError('Timed out while receiving message payload') from error
        if calculate_checksum(payload) != checksum:
            raise NetworkError('Invalid message checksum')
        command = command.rstrip(b'\x00').decode(errors='replace')
        logger.debug('Received %s (%s bytes) from %s', command, length, self.host)
        return Message(command, payload)

    def _read_exact(self, size: int, timeout: float) -> bytes:
        if not self.socket:
            raise NetworkError('Not connected to the node')
        self.socket.settimeout(timeout)
        data = b''
        while len(data) < size:
            try:
                chunk = self.socket.recv(size - len(data))
            except socket.timeout:
                if data:
                    raise NetworkError('Timed out while receiving message') from None
                raise
            except OSError as error:
                raise ConnectionClosedError(f'Connection to {self.host} failed: {error}') from error
            if not chunk:
                raise ConnectionClosedError(f'Connection closed by {self.host}')
            data += chunk
        return data


def broadcast_transaction(
    coin: Coin,
    raw_transaction: str,
    nodes: Optional[Sequence[PeerAddress]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """Send raw transaction (hex) to the first node which accepts the connection.

    :param nodes: Nodes to try in the given order, by default random nodes found using DNS seeds
                  (at most :data:`MAX_BROADCAST_ATTEMPTS` of them)
    :return: Transaction id
    :raises TransactionRejectedError: When the node rejects the transaction, other nodes are not
                                      tried since they would most likely reject it as well
    """
    if not nodes:
        nodes = discover_nodes(coin)
        random.shuffle(nodes)
        nodes = nodes[:MAX_BROADCAST_ATTEMPTS]
    if not nodes:
        raise NetworkError(f'No nodes found for coin {coin["name"]}')
    for address in nodes:
        try:
            with Node(coin, address.host, address.port, timeout) as node:
                return node.send_transaction(raw_transaction)
        except TransactionRejectedError:
            raise
        except NetworkError as error:
            logger.warning(
                'Could not send transaction to %s:%s: %s', address.host, address.port, error
            )
    raise NetworkError(f'Could not send transaction to any of {len(nodes)} node(s)')
