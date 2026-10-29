import sys
from io import StringIO
from unittest.mock import patch

import pytest
from tests import http_mock

from multicrypto.api import InsightAPI
from multicrypto.coins import coins, ethereum_coins
from multicrypto.commands.checkaddress import main

pytestmark = pytest.mark.usefixtures('dash_insight')


@http_mock.activate
@patch.object(
    sys,
    'argv',
    ['', '-a', 'XuJQq23TpwtSAszL9pXghx3VbNTSngYgC8', '-c', 'DASH', '-n', '10000000000'],
)
@patch('sys.stdout', new_callable=StringIO)
def test_checkaddress_success(sys_stdout):
    response_data = [
        {
            'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
            'txid': 'ff269d70ad429f2f3b8e042cf88f76c2f8a9e10de67f626fce25784fc29adb1e',
            'scriptPubKey': '76a914fa20c5e0689b92014ac4c3ecfc94b5163eaca3ae88ac',
            'amount': 0.49999,
            'satoshis': 49999000,
            'height': 326169,
            'vout': 0,
            'confirmations': 100,
        },
        {
            'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
            'txid': '4417d9e022c8f4adf1ef6d9dbad7a1ee0ae44b7eb5cf61e86fd1a0ed22b1c180',
            'vout': 0,
            'scriptPubKey': '76a913e90a9fcb81a78aa732c5721cc0ac4ba2075b7588ac',
            'amount': 526.37874459,
            'satoshis': 52637874459,
            'confirmations': 41130,
            'height': 114322,
        },
        {
            'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
            'txid': 'da08e8e2e3ba55f9b45ba7f0ca14f96683c3547419fcfe10e6c8ae9f3eebe4cf',
            'vout': 0,
            'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
            'amount': 250.97513558,
            'satoshis': 25097513558,
            'height': 123456,
            'confirmations': 2,
        },
        {
            'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
            'txid': '7c25ea822bbce5916a331f5851eacbc88d50c0f5a3be8a0dcea772f1baa43965',
            'vout': 0,
            'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
            'amount': 252.52259867,
            'satoshis': 25252259867,
            'height': 123458,
            'confirmations': 16,
        },
        {
            'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
            'txid': '22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335',
            'vout': 6,
            'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
            'amount': 118.6299918,
            'satoshis': 11862999180,
            'height': 143434,
            'confirmations': 712,
        },
        {
            'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
            'txid': 'aea9cdf0a8210238749cc4257ea05db91ea79f33691d691a859c4036ad529f85',
            'vout': 6,
            'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
            'amount': 114.01797238,
            'satoshis': 11401797238,
            'height': 77734,
            'confirmations': 80,
        },
    ]
    coin = coins['DASH']
    api_url = InsightAPI(coin).base_url
    address_url = '{}/addr/{}/utxo'.format(api_url, 'XuJQq23TpwtSAszL9pXghx3VbNTSngYgC8')
    http_mock.add(http_mock.GET, address_url, json=response_data, status=200)

    main()

    res = (
        'DASH address XuJQq23TpwtSAszL9pXghx3VbNTSngYgC8\n'
        'txid: 4417d9e022c8f4adf1ef6d9dbad7a1ee0ae44b7eb5cf61e86fd1a0ed22b1c180, confirmations: '
        '   41130, satoshis:      52637874459, amount: 526.37874459 DASH\n'
        'txid: da08e8e2e3ba55f9b45ba7f0ca14f96683c3547419fcfe10e6c8ae9f3eebe4cf, confirmations: '
        '       2, satoshis:      25097513558, amount: 250.97513558 DASH\n'
        'txid: 7c25ea822bbce5916a331f5851eacbc88d50c0f5a3be8a0dcea772f1baa43965, confirmations: '
        '      16, satoshis:      25252259867, amount: 252.52259867 DASH\n'
        'txid: 22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335, confirmations: '
        '     712, satoshis:      11862999180, amount: 118.62999180 DASH\n'
        'txid: aea9cdf0a8210238749cc4257ea05db91ea79f33691d691a859c4036ad529f85, confirmations: '
        '      80, satoshis:      11401797238, amount: 114.01797238 DASH\n'
        '---------------------------------------------------------------------------------------'
        '-----------------------------------------------------\n'
        '        5 inputs                                                                       '
        '          satoshis:     126252444302, amount: 1262.52444302 DASH\n'
    )
    assert sys_stdout.getvalue() == res


@patch.object(
    sys,
    'argv',
    [
        '',
        '-a',
        'XuJQq23TpwtSAszL9pXghx3VbNTSngYgC8',
        '-c',
        'DASH',
        '-n',
        '10000000000',
        '-x',
        '10',
    ],
)
def test_checkadress_minimum_input_greater_than_maximum_input_failure():
    with pytest.raises(Exception) as exc_info:
        main()
    exception_message = 'Minimum input threshold cannot be bigger than maximum input value!'
    assert str(exc_info.value) == exception_message


@patch.object(sys, 'argv', ['', '-a', 'DGyUmjSLAabzjui4NbjWT1ktjasFpzxXRm', '-c', 'DOGE'])
def test_checkadress_no_api_failure():
    with pytest.raises(Exception) as exc_info:
        main()

    assert str(exc_info.value) == 'No API has been defined for the coin DOGE'


@http_mock.activate
@patch(
    'multicrypto.commands.checkaddress.get_utxo_from_address',
    side_effect=Exception('Connection error'),
)
@patch.object(sys, 'argv', ['', '-a', 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5', '-c', 'DASH'])
def test_checkadress_get_utxo_from_address_failure(get_utxo_mock):
    response_data = [
        {
            'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5',
            'txid': '22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335',
            'vout': 6,
            'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
            'amount': 118.6299918,
            'satoshis': 11862999180,
            'height': 143434,
            'confirmations': 712,
        },
        {'address': 'XyVQ2KH3eApuHEnGFcRGyKomY6CHXWt6U5'},
    ]
    coin = coins['DASH']
    api_url = InsightAPI(coin).base_url
    address_url = '{}/addr/{}/utxo'.format(api_url, 'XuJQq23TpwtSAszL9pXghx3VbNTSngYgC8')
    http_mock.add(http_mock.GET, address_url, json=response_data, status=200)

    with pytest.raises(Exception) as exc_info:
        main()

    assert str(exc_info.value) == 'Connection error'
    assert get_utxo_mock.called


ETH_ADDRESS = '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'
ETH_NODE = ethereum_coins['ETH']['rpcs'][0]
ETH_TRANSACTIONS = f'https://eth.blockscout.com/api/v2/addresses/{ETH_ADDRESS}/transactions'


def add_ethereum_account_responses(node=ETH_NODE):
    for result in ('0x16345785d8a0000', '0x3'):  # 0.1 ether, nonce 3
        http_mock.add(http_mock.POST, node, json={'jsonrpc': '2.0', 'id': 1, 'result': result})


@http_mock.activate
@patch.object(sys, 'argv', ['', '-a', ETH_ADDRESS.lower(), '-c', 'eth'])
@patch('sys.stdout', new_callable=StringIO)
def test_checkaddress_ethereum(sys_stdout):
    add_ethereum_account_responses()
    page = {'items': [{'hash': '0x1'}] * 5, 'next_page_params': None}
    http_mock.add(http_mock.GET, ETH_TRANSACTIONS, json=page)

    main()

    assert sys_stdout.getvalue() == (
        f'ETH address {ETH_ADDRESS}\n'
        'balance: 0.1 ETH (100000000000000000 wei)\n'
        'sent transactions (nonce): 3\n'
        'all transactions: 5\n'
    )


@http_mock.activate
@patch.object(sys, 'argv', ['', '-a', ETH_ADDRESS, '-c', 'ETH', '--node', 'http://localhost:8545'])
@patch('sys.stdout', new_callable=StringIO)
def test_checkaddress_ethereum_with_own_node_and_unavailable_explorer(sys_stdout, caplog):
    add_ethereum_account_responses('http://localhost:8545')
    http_mock.add(http_mock.GET, ETH_TRANSACTIONS, status=500, body='error')

    main()

    output = sys_stdout.getvalue()
    assert 'Number of transactions is not available: API error: error' in caplog.text
    assert 'sent transactions (nonce): 3\n' in output
    assert 'all transactions' not in output


@patch.object(sys, 'argv', ['', '-a', '0x1234', '-c', 'ETH'])
@patch('sys.stdout', new_callable=StringIO)
def test_checkaddress_ethereum_incorrect_address(sys_stdout, caplog):
    main()

    assert 'must have 40 hexadecimal digits' in caplog.text
    assert sys_stdout.getvalue() == ''
