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
ARGS_WITHOUT_KEY = ['', '-c', 'teth', '-a', DESTINATION, '-v', '0.5']
INTERACTIVE_ARGS = ARGS_WITHOUT_KEY + ['-p', PRIVATE_KEY]
ARGS = INTERACTIVE_ARGS + ['--yes']
HISTORY = {'baseFeePerGas': [hex(GWEI), hex(2 * GWEI)], 'reward': [[hex(GWEI)]]}
RECEIPT = {
    'transactionHash': '0xhash',
    'status': '0x1',
    'blockNumber': '0x10',
    'gasUsed': '0x5208',
    'effectiveGasPrice': hex(3 * GWEI),
}


class TerminalInput(StringIO):
    def isatty(self):
        return True


def add_node_responses(node=NODE, chain_id=11155111, send_result='0xhash'):
    """Node responses in the order of the requests made by prepare_transfer and broadcast."""
    results = [hex(chain_id), hex(10**18), '0x4', '0x5208', HISTORY]
    if send_result is not None:
        results.append(send_result)
    add_results(results, node)


def add_results(results, node=NODE):
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
    add_results(['0xaa36a7', hex(10**18), HISTORY, '0xhash'], 'http://localhost:8545')

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
@patch.object(sys, 'argv', ARGS + ['-v', '2'])
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


@patch.object(sys, 'argv', ARGS + ['-p', '1234'])
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


@http_mock.activate
@patch.object(sys, 'argv', INTERACTIVE_ARGS)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_requires_yes_when_input_is_not_terminal(sys_stdout, caplog):
    main()

    assert 'Standard input is not a terminal, confirm sending with --yes' in caplog.text
    assert http_mock.calls == []


@pytest.mark.parametrize('answer', ['y', 'YES'])
@http_mock.activate
@patch.object(sys, 'argv', INTERACTIVE_ARGS)
@patch('sys.stdin', new_callable=TerminalInput)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_asks_for_confirmation(sys_stdout, sys_stdin, answer):
    add_node_responses()

    with patch('builtins.input', return_value=answer) as ask:
        main()

    ask.assert_called_once_with('Send the transaction? [y/N] ')
    assert sys_stdout.getvalue() == '{"txid": "0xhash"}\n'


@pytest.mark.parametrize('answer', ['', 'n', 'no'])
@http_mock.activate
@patch.object(sys, 'argv', INTERACTIVE_ARGS)
@patch('sys.stdin', new_callable=TerminalInput)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_not_confirmed(sys_stdout, sys_stdin, caplog, answer):
    caplog.set_level(logging.INFO)
    add_node_responses(send_result=None)

    with patch('builtins.input', return_value=answer):
        main()

    assert 'Transaction was not sent' in caplog.text
    assert sys_stdout.getvalue() == ''
    methods = [json.loads(call.request.body)['method'] for call in http_mock.calls]
    assert 'eth_sendRawTransaction' not in methods


@http_mock.activate
@patch.object(sys, 'argv', ARGS_WITHOUT_KEY + ['--yes'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_reads_private_key_from_standard_input(sys_stdout):
    add_node_responses()

    with patch('sys.stdin', StringIO(PRIVATE_KEY + '\n')):
        main()

    assert sys_stdout.getvalue() == '{"txid": "0xhash"}\n'
    assert sent_transaction()[1] == SENDER


@http_mock.activate
@patch.object(sys, 'argv', ARGS_WITHOUT_KEY)
@patch('sys.stdin', new_callable=TerminalInput)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_asks_for_private_key_in_terminal(sys_stdout, sys_stdin):
    add_node_responses()

    with patch('getpass.getpass', return_value=PRIVATE_KEY) as ask_key:
        with patch('builtins.input', return_value='y'):
            main()

    ask_key.assert_called_once_with('Private key: ')
    assert sent_transaction()[1] == SENDER


@http_mock.activate
@patch.object(sys, 'argv', ARGS + ['--max_fee', '0.5', '--dry_run'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_shows_fee_warnings(sys_stdout, caplog):
    add_node_responses(send_result=None)

    main()

    assert 'Warning: Max fee per gas 0.5 gwei is lower than the base fee 2 gwei' in caplog.text


@pytest.mark.parametrize(
    'status, result, message',
    [
        ('0x1', 'success', ''),
        ('0x0', 'failed', 'Transaction failed (reverted), the fee was paid'),
    ],
)
@http_mock.activate
@patch.object(sys, 'argv', ARGS + ['--wait'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_waits_for_receipt(sys_stdout, caplog, status, result, message):
    add_node_responses()
    add_results([dict(RECEIPT, status=status)])

    main()

    assert json.loads(sys_stdout.getvalue()) == {
        'txid': '0xhash',
        'status': result,
        'block': 16,
        'gas_used': 21000,
        'fee': '0.000063',
    }
    assert message in caplog.text


@http_mock.activate
@patch.object(sys, 'argv', ARGS + ['--wait', '30'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_transaction_not_mined_while_waiting(sys_stdout, caplog):
    add_node_responses()

    with patch('multicrypto.commands.sendeth.wait_for_receipt', return_value=None) as wait:
        main()

    assert wait.call_args.args[1:] == ('0xhash', 30)
    assert json.loads(sys_stdout.getvalue()) == {'txid': '0xhash', 'status': 'pending'}
    assert 'Transaction was not mined in 30 seconds' in caplog.text


@pytest.mark.parametrize('error', [EOFError, KeyboardInterrupt])
@http_mock.activate
@patch.object(sys, 'argv', ARGS_WITHOUT_KEY)
@patch('sys.stdin', new_callable=TerminalInput)
@patch('sys.stdout', new_callable=StringIO)
def test_sendeth_cancelled_when_private_key_is_asked(sys_stdout, sys_stdin, caplog, error):
    with patch('getpass.getpass', side_effect=error):
        main()

    assert 'Cancelled, transaction was not sent' in caplog.text
    assert http_mock.calls == []
