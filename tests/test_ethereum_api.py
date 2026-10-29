import json

import pytest
from tests import http_mock

from multicrypto.api import InsufficientFundsError, RateLimitError
from multicrypto.coins import ethereum_coins
from multicrypto.ethereum import GWEI, TRANSFER_GAS, decode_transaction
from multicrypto.ethereum_api import (
    MIN_PRIORITY_FEE,
    BlockscoutAPI,
    EthereumRPC,
    FeeSuggestion,
    NodeUnavailableError,
    Receipt,
    RpcError,
    broadcast_transaction,
    get_explorer,
    get_rpc,
    prepare_transfer,
    suggest_fees,
    wait_for_receipt,
)

NODE1 = 'https://node1.example'
NODE2 = 'https://node2.example'
ADDRESS = '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'  # address of the private key 1
DESTINATION = '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed'
ETH = ethereum_coins['ETH']


def rpc_result(result):
    return {'jsonrpc': '2.0', 'id': 1, 'result': result}


def rpc_error(code, message):
    return {'jsonrpc': '2.0', 'id': 1, 'error': {'code': code, 'message': message}}


@http_mock.activate
def test_call_sends_json_rpc_request_and_returns_result():
    http_mock.add(http_mock.POST, NODE1, json=rpc_result('0x1'))

    assert EthereumRPC([NODE1], timeout=5).call('eth_getBalance', ADDRESS, 'latest') == '0x1'

    request = http_mock.calls[0].request
    assert json.loads(request.body) == {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'eth_getBalance',
        'params': [ADDRESS, 'latest'],
    }
    assert request.headers['content-type'] == 'application/json'
    assert http_mock.calls[0].timeout == 5


@pytest.mark.parametrize(
    'kwargs',
    [
        dict(status=503, body='unavailable'),
        dict(status=429, body='too many requests'),
        dict(body='not json'),
        dict(json={'jsonrpc': '2.0', 'id': 1}),
        dict(json=rpc_error(-32005, 'limit exceeded')),
        dict(json=rpc_error(-32603, 'internal error')),
        dict(json=rpc_error(-32000, 'Rate limit reached')),
        dict(json=rpc_error(-32029, 'Too Many Requests')),
        dict(json=rpc_error(-32000, 'Too Many Requests, apply for API key')),
    ],
)
@http_mock.activate
def test_call_tries_next_node_when_node_fails(kwargs):
    http_mock.add(http_mock.POST, NODE1, **kwargs)
    http_mock.add(http_mock.POST, NODE2, json=rpc_result('0x2'))

    assert EthereumRPC([NODE1, NODE2]).call('eth_chainId') == '0x2'


@http_mock.activate
def test_call_tries_next_node_when_connection_fails():
    http_mock.add(http_mock.POST, NODE2, json=rpc_result('0x2'))

    assert EthereumRPC([NODE1, NODE2]).call('eth_chainId') == '0x2'


@http_mock.activate
def test_call_raises_error_of_node_without_trying_other_nodes():
    http_mock.add(http_mock.POST, NODE1, json=rpc_error(-32000, 'nonce too low'))
    http_mock.add(http_mock.POST, NODE2, json=rpc_result('0x2'))

    with pytest.raises(RpcError, match='nonce too low') as error:
        EthereumRPC([NODE1, NODE2]).call('eth_sendRawTransaction', '0x02')

    assert error.value.code == -32000
    assert len(http_mock.calls) == 1


@http_mock.activate
def test_call_raises_error_when_no_node_responds():
    http_mock.add(http_mock.POST, NODE1, status=503, body='unavailable')

    with pytest.raises(NodeUnavailableError, match='node1.example: HTTP 503 unavailable.*node2'):
        EthereumRPC([NODE1, NODE2]).call('eth_chainId')


def test_rpc_requires_node():
    with pytest.raises(ValueError, match='No Ethereum node'):
        EthereumRPC([])


def test_get_rpc_uses_given_nodes_or_public_nodes_of_coin():
    assert get_rpc(ETH).urls == ETH['rpcs']
    assert get_rpc(ETH, ['http://localhost:8545']).urls == ['http://localhost:8545']


@http_mock.activate
def test_methods_convert_hex_quantities():
    for result in ('0x1', '0xde0b6b3a7640000', '0x5', '0x5208'):
        http_mock.add(http_mock.POST, NODE1, json=rpc_result(result))
    rpc = EthereumRPC([NODE1])

    assert rpc.chain_id() == 1
    assert rpc.get_balance(ADDRESS) == 10**18
    assert rpc.get_nonce(ADDRESS) == 5
    assert rpc.estimate_gas(ADDRESS, DESTINATION, 10, b'\x01') == 21000

    params = [json.loads(call.request.body)['params'] for call in http_mock.calls]
    assert params[1:] == [
        [ADDRESS, 'latest'],
        [ADDRESS, 'pending'],
        [{'from': ADDRESS, 'to': DESTINATION, 'value': '0xa', 'data': '0x01'}],
    ]


BLOCKSCOUT_ADDRESS = f'https://eth.blockscout.com/api/v2/addresses/{ADDRESS}'


@http_mock.activate
def test_blockscout_get_tx_count_from_the_only_page_of_transactions():
    page = {'items': [{'hash': '0x1'}, {'hash': '0x2'}], 'next_page_params': None}
    http_mock.add(http_mock.GET, f'{BLOCKSCOUT_ADDRESS}/transactions', json=page)

    assert get_explorer(ETH).get_tx_count(ADDRESS) == 2
    assert len(http_mock.calls) == 1


@http_mock.activate
def test_blockscout_get_tx_count_without_transactions():
    page = {'items': [], 'next_page_params': None}
    http_mock.add(http_mock.GET, f'{BLOCKSCOUT_ADDRESS}/transactions', json=page)

    assert get_explorer(ETH).get_tx_count(ADDRESS) == 0


@pytest.mark.parametrize('counter, count', [('120', 120), ('3', 50)])
@http_mock.activate
def test_blockscout_get_tx_count_with_more_pages_uses_counter(counter, count):
    page = {'items': [{'hash': '0x1'}] * 50, 'next_page_params': {'index': 1}}
    http_mock.add(http_mock.GET, f'{BLOCKSCOUT_ADDRESS}/transactions', json=page)
    http_mock.add(
        http_mock.GET, f'{BLOCKSCOUT_ADDRESS}/counters', json={'transactions_count': counter}
    )

    assert get_explorer(ETH).get_tx_count(ADDRESS) == count


@http_mock.activate
def test_blockscout_rate_limit():
    url = f'https://explorer.example/addresses/{ADDRESS}/transactions'
    http_mock.add(http_mock.GET, url, status=429, body='slow down')

    with pytest.raises(RateLimitError):
        BlockscoutAPI('https://explorer.example').get_tx_count(ADDRESS)


class FakeRPC:
    """Node with the state of the account of the private key 1."""

    def __init__(self, chain_id=1, balance=10**18, nonce=3, gas=TRANSFER_GAS, error=None):
        self.chain = chain_id
        self.balance = balance
        self.nonce = nonce
        self.gas = gas
        self.error = error
        self.sent = []
        self.history = {
            'baseFeePerGas': ['0x1', '0x2', hex(10 * GWEI)],
            'reward': [[hex(GWEI)], [hex(3 * GWEI)], [hex(2 * GWEI)]],
        }

    def chain_id(self):
        return self.chain

    def get_balance(self, address):
        assert address == ADDRESS
        return self.balance

    def get_nonce(self, address):
        assert address == ADDRESS
        return self.nonce

    def estimate_gas(self, sender, to, value, data=b''):
        assert (sender, to) == (ADDRESS, DESTINATION)
        return self.gas

    def fee_history(self, blocks, percentiles):
        return self.history

    def send_raw_transaction(self, raw_transaction):
        if self.error:
            raise self.error
        self.sent.append(raw_transaction)
        return '0xhash'


def test_suggest_fees_uses_next_base_fee_and_median_tip():
    suggestion = suggest_fees(FakeRPC())

    assert suggestion == FeeSuggestion(10 * GWEI, 2 * GWEI)
    assert suggestion.max_fee_per_gas == 22 * GWEI


def test_suggest_fees_has_minimum_tip():
    rpc = FakeRPC()
    rpc.history = {'baseFeePerGas': ['0x10'], 'reward': [['0x0'], ['0x0']]}

    assert suggest_fees(rpc) == FeeSuggestion(16, MIN_PRIORITY_FEE)


def test_suggest_fees_without_rewards():
    rpc = FakeRPC()
    rpc.history = {'baseFeePerGas': ['0x10'], 'oldestBlock': '0x1'}

    assert suggest_fees(rpc) == FeeSuggestion(16, MIN_PRIORITY_FEE)


def test_prepare_transfer_uses_parameters_from_node():
    prepared = prepare_transfer(ETH, FakeRPC(), 1, DESTINATION.lower(), 10**17)

    transaction, sender = decode_transaction(prepared.signed.raw)
    assert transaction == prepared.transaction
    assert sender == prepared.sender == ADDRESS
    assert (transaction.chain_id, transaction.nonce, transaction.gas_limit) == (1, 3, 21000)
    assert transaction.to == DESTINATION
    assert transaction.value == 10**17
    assert transaction.max_priority_fee_per_gas == 2 * GWEI
    assert transaction.max_fee_per_gas == 22 * GWEI
    assert prepared.balance == 10**18
    assert prepared.max_total == 10**17 + 21000 * 22 * GWEI


def test_prepare_transfer_uses_given_parameters():
    prepared = prepare_transfer(
        ETH,
        FakeRPC(),
        1,
        DESTINATION,
        1,
        nonce=7,
        gas_limit=30000,
        max_priority_fee_per_gas=GWEI,
        max_fee_per_gas=5 * GWEI,
    )

    transaction = prepared.transaction
    assert (transaction.nonce, transaction.gas_limit) == (7, 30000)
    assert (transaction.max_priority_fee_per_gas, transaction.max_fee_per_gas) == (GWEI, 5 * GWEI)


def test_prepare_transfer_with_max_fee_lower_than_suggested_tip():
    prepared = prepare_transfer(ETH, FakeRPC(), 1, DESTINATION, 1, max_fee_per_gas=GWEI)

    assert prepared.transaction.max_priority_fee_per_gas == GWEI


def test_prepare_transfer_with_given_tip_calculates_max_fee():
    prepared = prepare_transfer(ETH, FakeRPC(), 1, DESTINATION, 1, max_priority_fee_per_gas=GWEI)

    assert prepared.transaction.max_fee_per_gas == 21 * GWEI


def test_prepare_transfer_checks_chain_of_node():
    with pytest.raises(ValueError, match='chain 11155111.*chain id 1'):
        prepare_transfer(ETH, FakeRPC(chain_id=11155111), 1, DESTINATION, 1)


def test_prepare_transfer_checks_balance_for_value():
    with pytest.raises(InsufficientFundsError, match='lower than 2'):
        prepare_transfer(ETH, FakeRPC(), 1, DESTINATION, 2 * 10**18)


def test_prepare_transfer_checks_balance_for_value_and_fee():
    with pytest.raises(InsufficientFundsError, match='max fee 0.000462'):
        prepare_transfer(ETH, FakeRPC(), 1, DESTINATION, 10**18)


def test_prepare_transfer_validates_destination():
    with pytest.raises(ValueError, match='checksum'):
        prepare_transfer(ETH, FakeRPC(), 1, DESTINATION.replace('a', 'A', 1), 1)


def test_broadcast_transaction():
    rpc = FakeRPC()
    prepared = prepare_transfer(ETH, rpc, 1, DESTINATION, 1)

    assert broadcast_transaction(rpc, prepared) == '0xhash'
    assert rpc.sent == [prepared.signed.raw_hex]


def test_broadcast_transaction_already_known_by_node():
    rpc = FakeRPC(error=RpcError(-32000, 'already known'))
    prepared = prepare_transfer(ETH, rpc, 1, DESTINATION, 1)

    assert broadcast_transaction(rpc, prepared) == prepared.signed.hash


def test_broadcast_transaction_rejected_by_node():
    rpc = FakeRPC(error=RpcError(-32000, 'nonce too low'))
    prepared = prepare_transfer(ETH, rpc, 1, DESTINATION, 1)

    with pytest.raises(RpcError, match='nonce too low'):
        broadcast_transaction(rpc, prepared)


RECEIPT = {
    'transactionHash': '0xabc',
    'status': '0x1',
    'blockNumber': '0x10',
    'gasUsed': '0x5208',
    'effectiveGasPrice': hex(2 * GWEI),
}


@http_mock.activate
def test_get_receipt():
    http_mock.add(http_mock.POST, NODE1, json=rpc_result(RECEIPT))

    receipt = EthereumRPC([NODE1]).get_receipt('0xabc')

    assert receipt == Receipt('0xabc', True, 16, 21000, 2 * GWEI)
    assert receipt.fee == 42000 * GWEI
    assert json.loads(http_mock.calls[0].request.body)['params'] == ['0xabc']


@http_mock.activate
def test_get_receipt_of_failed_transaction():
    http_mock.add(http_mock.POST, NODE1, json=rpc_result(dict(RECEIPT, status='0x0')))

    assert not EthereumRPC([NODE1]).get_receipt('0xabc').success


@http_mock.activate
def test_get_receipt_of_pending_transaction():
    http_mock.add(http_mock.POST, NODE1, json=rpc_result(None))

    assert EthereumRPC([NODE1]).get_receipt('0xabc') is None


class FakeClock:
    def __init__(self):
        self.time = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.time += seconds

    def __call__(self):
        return self.time


class ReceiptRPC:
    def __init__(self, receipts):
        self.receipts = list(receipts)

    def get_receipt(self, transaction_hash):
        return self.receipts.pop(0) if len(self.receipts) > 1 else self.receipts[0]


def test_wait_for_receipt_polls_until_transaction_is_mined():
    receipt = Receipt('0xabc', True, 16, 21000, GWEI)
    clock = FakeClock()

    result = wait_for_receipt(ReceiptRPC([None, None, receipt]), '0xabc', 60, 4, clock.sleep, clock)

    assert result == receipt
    assert clock.sleeps == [4, 4]


def test_wait_for_receipt_returns_none_after_timeout():
    clock = FakeClock()

    assert wait_for_receipt(ReceiptRPC([None]), '0xabc', 10, 4, clock.sleep, clock) is None
    assert clock.sleeps == [4, 4, 2]


def prepared_with(**fields):
    return prepare_transfer(ETH, FakeRPC(), 1, DESTINATION, fields.pop('value', 10**17), **fields)


def test_fee_warnings_of_suggested_fees():
    assert prepared_with().fee_warnings() == []


def test_fee_warning_when_max_fee_is_lower_than_base_fee():
    warnings = prepared_with(max_fee_per_gas=GWEI).fee_warnings()

    assert warnings == [
        'Max fee per gas 1 gwei is lower than the base fee 10 gwei of the next block, '
        'the transaction will wait until the base fee drops'
    ]


def test_fee_warning_when_max_fee_is_much_higher_than_suggested():
    warnings = prepared_with(max_fee_per_gas=221 * GWEI, value=10**18 // 2).fee_warnings()

    assert warnings == ['Max fee per gas 221 gwei is more than 10 times the suggested 22 gwei']


def test_fee_warning_when_max_fee_is_higher_than_value():
    warnings = prepared_with(value=1).fee_warnings()

    assert warnings == ['Max fee 0.000462 is higher than the sent value 0.000000000000000001']
