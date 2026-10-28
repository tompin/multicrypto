import sys
from io import StringIO
from unittest.mock import patch

import pytest
from tests import http_mock

from multicrypto.api import InsightAPI, get_api
from multicrypto.coins import coins
from multicrypto.commands.sendcrypto import main
from multicrypto.network import PeerAddress, TransactionRejectedError

ARGS = [
    '',
    '-a',
    'XuJQq23TpwtSAszL9pXghx3VbNTSngYgC8',
    '-c',
    'DASH',
    '-s',
    '50900000',
    '-p',
    'XG9xRTPCLz3pzWHFVBS8vxZEKQCJyJJWVZNXTrc8XXYqsjPPAoiK,'
    'XHHn1HYHwTxfJhtBFDgrWXJA69fnSGiBEEoV8p8jo7NTohyHjeBo',
]
TXID = 'a9700b6b18559c2ee976c5a7a5b51f1f9b47daacca96148b3b0afd2b0c6da138'


def add_utxo_responses(api_url):
    address_url1 = '{}/addr/{}/utxo'.format(api_url, 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5')
    address_url2 = '{}/addr/{}/utxo'.format(api_url, 'Xk7MSekGBMEzExJBRwq5uv7CGzSrMj7yn4')
    http_mock.add(
        http_mock.GET,
        address_url1,
        json=[
            {
                'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
                'txid': 'ff269d70ad429f2f3b8e042cf88f76c2f8a9e10de67f626fce25784fc29adb1e',
                'scriptPubKey': '76a914fa20c5e0689b92014ac4c3ecfc94b5163eaca3ae88ac',
                'amount': 0.49999,
                'satoshis': 49999000,
                'height': 326169,
                'vout': 0,
                'confirmations': 100,
            }
        ],
        status=200,
    )
    http_mock.add(
        http_mock.GET,
        address_url2,
        json=[
            {
                'address': 'Xk7MSekGBMEzExJBRwq5uv7CGzSrMj7yn4',
                'txid': 'e2860bc090fecbe97ebafae2a31c9d9df4aca221002fc8c57d75c5a2ac58af51',
                'scriptPubKey': '76a914675bd5240d72cb96e7722b0785ccc60cb168b7ad88ac',
                'amount': 0.01,
                'satoshis': 1000000,
                'height': 326168,
                'vout': 1,
                'confirmations': 102,
            }
        ],
        status=200,
    )


@http_mock.activate
@patch.object(sys, 'argv', ARGS)
@patch('sys.stdout', new_callable=StringIO)
def test_sendcrypto_success(sys_stdout):
    coin = coins['DASH']
    api_url = InsightAPI(coin).base_url
    send_url = '{}/tx/send'.format(api_url)
    add_utxo_responses(api_url)
    http_mock.add(
        http_mock.POST,
        send_url,
        json={'txid': 'a9700b6b18559c2ee976c5a7a5b51f1f9b47daacca96148b3b0afd2b0c6da138'},
        content_type='application/json',
        status=200,
    )
    main()

    res = '{"txid": "a9700b6b18559c2ee976c5a7a5b51f1f9b47daacca96148b3b0afd2b0c6da138"}\n'
    assert sys_stdout.getvalue() == res


@http_mock.activate
@patch.object(sys, 'argv', ARGS + ['--node', '1.2.3.4', '--node', '[2001:db8::1]:18233'])
@patch('sys.stdout', new_callable=StringIO)
@patch('multicrypto.commands.sendcrypto.broadcast_transaction', return_value=TXID)
def test_sendcrypto_p2p_nodes(broadcast_transaction, sys_stdout):
    add_utxo_responses(InsightAPI(coins['DASH']).base_url)

    main()

    coin, raw_transaction, nodes = broadcast_transaction.call_args.args
    assert coin is coins['DASH']
    assert raw_transaction.startswith('01000000')
    assert nodes == [PeerAddress('1.2.3.4', 9999), PeerAddress('2001:db8::1', 18233)]
    assert sys_stdout.getvalue() == f'{{"txid": "{TXID}"}}\n'


@http_mock.activate
@patch.object(sys, 'argv', ARGS + ['--p2p'])
@patch('sys.stdout', new_callable=StringIO)
@patch('multicrypto.commands.sendcrypto.broadcast_transaction', return_value=TXID)
def test_sendcrypto_p2p_discovered_nodes(broadcast_transaction, sys_stdout):
    add_utxo_responses(InsightAPI(coins['DASH']).base_url)

    main()

    assert broadcast_transaction.call_args.args[2] == []
    assert sys_stdout.getvalue() == f'{{"txid": "{TXID}"}}\n'


@http_mock.activate
@patch.object(sys, 'argv', ARGS + ['--p2p'])
@patch('sys.stdout', new_callable=StringIO)
@patch(
    'multicrypto.commands.sendcrypto.broadcast_transaction',
    side_effect=TransactionRejectedError('Transaction rejected: bad-txns'),
)
def test_sendcrypto_p2p_rejected(_broadcast_transaction, sys_stdout, caplog):
    add_utxo_responses(InsightAPI(coins['DASH']).base_url)

    main()

    assert sys_stdout.getvalue() == ''
    assert 'Transaction rejected: bad-txns' in caplog.text


@patch.object(sys, 'argv', ARGS + ['--node', '1.2.3.4:port'])
@patch('sys.stdout', new_callable=StringIO)
@patch('multicrypto.commands.sendcrypto.broadcast_transaction')
def test_sendcrypto_p2p_invalid_node(broadcast_transaction, sys_stdout, caplog):
    main()

    broadcast_transaction.assert_not_called()
    assert sys_stdout.getvalue() == ''
    assert 'Invalid node port: 1.2.3.4:port' in caplog.text


@patch.object(
    sys,
    'argv',
    [
        '',
        '-a',
        'XuJQq23TpwtSAszL9pXghx3VbNTSngYgC8',
        '-c',
        'DASH',
        '-s',
        '50900000',
        '-p',
        'XG9xRTPCLz3pzWHFVBS8vxZEKQCJyJJWVZNXTrc8XXYqsjPPAoiK',
        '--p2p',
    ],
)
@patch('sys.stdout', new_callable=StringIO)
def test_sendcrypto_p2p_not_supported(sys_stdout, caplog, monkeypatch):
    monkeypatch.delitem(coins['DASH'], 'network')
    main()

    assert sys_stdout.getvalue() == ''
    assert 'No peer-to-peer network has been defined for the coin DASH' in caplog.text


@http_mock.activate
@patch.object(
    sys,
    'argv',
    [
        '',
        '-a',
        'tb1q8kvyc4nelyueadktgx574st0dxkl9xexguyqkm',
        '-c',
        'TBTC',
        '-s',
        '60000',
        '-f',
        '1000',
        '-p',
        'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo',
        '-t',
        'p2wpkh',
        '--p2p',
    ],
)
@patch('sys.stdout', new_callable=StringIO)
@patch('multicrypto.commands.sendcrypto.broadcast_transaction', return_value=TXID)
def test_sendcrypto_from_p2wpkh_address(broadcast_transaction, sys_stdout):
    source_address = 'tb1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uhq9l7n'
    api_url = get_api(coins['TBTC']).base_url
    http_mock.add(
        http_mock.GET,
        f'{api_url}/address/{source_address}/utxo',
        json=[{'txid': '11' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 100000}],
        status=200,
    )

    main()

    raw_transaction = broadcast_transaction.call_args.args[1]
    # version, segwit marker and flag, one input with empty unlocking script
    assert raw_transaction.startswith('010000000001' + '01' + '11' * 32 + '00000000' + '00')
    # destination output and change sent back to the source address
    assert '60ea000000000000' + '16' + '00143d984c5679f9399eb6cb41a9eac16f69adf29b26' in (
        raw_transaction
    )
    assert '5898000000000000' + '16' + '0014925d4028880bd0c9d68fbc7fc7dfee976698629c' in (
        raw_transaction
    )
    assert sys_stdout.getvalue() == f'{{"txid": "{TXID}"}}\n'


@http_mock.activate
@patch.object(
    sys,
    'argv',
    [
        '',
        '-a',
        'tb1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uhq9l7n',
        '-c',
        'TBTC',
        '-s',
        '60000',
        '-f',
        '1000',
        '-p',
        'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo',
        '-t',
        'p2tr',
    ],
)
@patch('sys.stdout', new_callable=StringIO)
def test_sendcrypto_from_p2tr_address(sys_stdout):
    source_address = 'tb1p5z79qpqcp9wf02p2zd5dtz89pxla4qu3zuz5w5hxhz7ds58cce4s9ztvgh'
    api_url = get_api(coins['TBTC']).base_url
    http_mock.add(
        http_mock.GET,
        f'{api_url}/address/{source_address}/utxo',
        json=[{'txid': '11' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 100000}],
        status=200,
    )
    http_mock.add(http_mock.POST, f'{api_url}/tx', body=TXID, status=200)

    main()

    raw_transaction = http_mock.calls[1].request.body
    # version, segwit marker and flag, one input with empty unlocking script
    assert raw_transaction.startswith('010000000001' + '01' + '11' * 32 + '00000000' + '00')
    # destination output and change sent back to the source taproot address
    assert '60ea000000000000' + '16' + '0014925d4028880bd0c9d68fbc7fc7dfee976698629c' in (
        raw_transaction
    )
    p2tr_script = '5120a0bc500418095c97a82a1368d588e509bfda839117054752e6b8bcd850f8c66b'
    assert '5898000000000000' + '22' + p2tr_script in raw_transaction
    # witness with one 64 bytes Schnorr signature
    assert raw_transaction[-140:-136] == '0140'
    assert sys_stdout.getvalue() == f'{{"txid": "{TXID}"}}\n'


@patch.object(sys, 'argv', ARGS + ['-t', 'p2wpkh'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendcrypto_address_type_not_supported(sys_stdout, caplog):
    main()

    assert sys_stdout.getvalue() == ''
    assert 'Address type p2wpkh is not supported for dash, supported types: p2pkh' in caplog.text


@patch('sys.stderr', new_callable=StringIO)
def test_sendcrypto_fee_and_fee_rate_are_exclusive(sys_stderr):
    argv = ['', '-c', 'TBTC', '-a', 'x', '-s', '1000', '-p', 'x', '-f', '100', '-r', '2']
    with patch.object(sys, 'argv', argv), pytest.raises(SystemExit):
        main()

    assert 'not allowed with argument' in sys_stderr.getvalue()
