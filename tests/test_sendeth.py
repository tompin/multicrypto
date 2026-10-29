import json
import logging
import sys
from io import StringIO
from unittest.mock import patch

import pytest
from tests import http_mock

from multicrypto.coins import ethereum_coins
from multicrypto.commands.sendeth import main
from multicrypto.ethereum import GWEI, decode_transaction

PRIVATE_KEY = '0x' + '00' * 31 + '01'
SENDER = '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'
DESTINATION = '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed'
NODE = ethereum_coins['TETH']['rpcs'][0]
ARGS = ['', '-c', 'teth', '-p', PRIVATE_KEY, '-a', DESTINATION, '-v', '0.5']


def add_node_responses(node=NODE, chain_id=11155111, send_result='0xhash'):
    """Node responses in the order of the requests made by prepare_transfer and broadcast."""
    history = {'baseFeePerGas': [hex(GWEI), hex(2 * GWEI)], 'reward': [[hex(GWEI)]]}
    results = [hex(chain_id), hex(10**18), '0x4', '0x5208', history]
    if send_result is not None:
        results.append(send_result)
    for result in results:
        http_mock.add(http_mock.POST, node, json={'jsonrpc': '2.0', 'id': 1, 'result': result})


def sent_transaction():
    raw = json.loads(http_mock.calls[-1].request.body)['params'][0]
    return decode_transaction(bytes.fromhex(raw[2:]))


@http_mock.activate
@patch.object(sys, 'argv', ARGS)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth(sys_stdout, caplog):
    caplog.set_level(logging.INFO)
    add_node_responses()

    main()

    assert sys_stdout.getvalue() == '{"txid": "0xhash"}\n'
    assert f'From: {SENDER} (balance 1 TETH)' in caplog.text
    assert 'Value: 0.5 TETH' in caplog.text
    assert (
        'Nonce: 4, gas limit: 21000, max fee per gas: 5 gwei, priority fee per gas: 1 gwei'
        in caplog.text
    )
    assert 'Max fee: 0.000105 TETH' in caplog.text
    transaction, sender = sent_transaction()
    assert sender == SENDER
    assert (transaction.chain_id, transaction.nonce, transaction.to) == (11155111, 4, DESTINATION)
    assert transaction.value == 5 * 10**17
    assert json.loads(http_mock.calls[-1].request.body)['method'] == 'eth_sendRawTransaction'


@http_mock.activate
@patch.object(
    sys,
    'argv',
    ARGS
    + ['--nonce', '0', '--gas_limit', '30000', '--max_fee', '3.5', '--priority_fee', '0.5']
    + ['--node', 'http://localhost:8545'],
)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_with_given_parameters_and_node(sys_stdout):
    for result in ('0xaa36a7', hex(10**18), '0xhash'):
        http_mock.add(
            http_mock.POST, 'http://localhost:8545', json={'jsonrpc': '2.0', 'result': result}
        )

    main()

    assert sys_stdout.getvalue().endswith('{"txid": "0xhash"}\n')
    transaction, _ = sent_transaction()
    assert (transaction.nonce, transaction.gas_limit) == (0, 30000)
    assert transaction.max_fee_per_gas == 35 * GWEI // 10
    assert transaction.max_priority_fee_per_gas == GWEI // 2


@http_mock.activate
@patch.object(sys, 'argv', ARGS + ['--dry_run'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_dry_run_does_not_send_transaction(sys_stdout):
    add_node_responses(send_result=None)

    main()

    result = json.loads(sys_stdout.getvalue().splitlines()[-1])
    transaction, sender = decode_transaction(bytes.fromhex(result['raw_transaction'][2:]))
    assert sender == SENDER
    assert result['txid'].startswith('0x')
    methods = [json.loads(call.request.body)['method'] for call in http_mock.calls]
    assert 'eth_sendRawTransaction' not in methods


@http_mock.activate
@patch.object(sys, 'argv', ARGS)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_node_on_other_chain(sys_stdout, caplog):
    add_node_responses(chain_id=1)

    main()

    assert 'Node is on the chain 1, but ethereum sepolia testnet has chain id' in caplog.text
    assert sys_stdout.getvalue() == ''


@http_mock.activate
@patch.object(sys, 'argv', ARGS[:-1] + ['2'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_insufficient_funds(sys_stdout, caplog):
    add_node_responses()

    main()

    assert f'Error: Balance 1 of {SENDER} is lower than 2' in caplog.text


@http_mock.activate
@patch.object(sys, 'argv', ARGS)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_transaction_rejected(sys_stdout, caplog):
    add_node_responses(send_result=None)
    http_mock.add(
        http_mock.POST,
        NODE,
        json={'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32000, 'message': 'nonce too low'}},
    )

    main()

    assert 'Error: Node error -32000: nonce too low' in caplog.text
    assert '"txid"' not in sys_stdout.getvalue()


@patch.object(sys, 'argv', ARGS[:4] + ['1234'] + ARGS[5:])
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_incorrect_private_key(sys_stdout, caplog):
    main()

    assert 'Ethereum private key must have 64 hexadecimal digits' in caplog.text


@pytest.mark.parametrize(
    'args, error',
    [
        (['-c', 'BTC'], 'BTC is not supported, choose one of ETH, TETH'),
        (['-v', '0.0000000000000000001'], 'more than 18 decimal places'),
        (['--max_fee', 'abc'], 'abc is not a number'),
    ],
)
@patch('sys.stderr', new_callable=StringIO)
def test_sendeth_incorrect_arguments(sys_stderr, args, error):
    with patch.object(sys, 'argv', ARGS + args), pytest.raises(SystemExit):
        main()

    assert error in sys_stderr.getvalue()
