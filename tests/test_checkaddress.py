import sys
from io import StringIO
from unittest.mock import patch

import pytest
import responses

from multicrypto.apis import API
from multicrypto.coins import coins
from multicrypto.commands.checkaddress import main


@responses.activate
@patch.object(sys, 'argv', [
    '', '-a', 't1cVB16ohqZTScaSeEN2azETd1h4qXpVDnP', '-c', 'HUSH', '-n', '10000000000'])
@patch('sys.stdout', new_callable=StringIO)
def test_checkaddress_success(sys_stdout):
    response_data = [
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
         'txid': 'ff269d70ad429f2f3b8e042cf88f76c2f8a9e10de67f626fce25784fc29adb1e',
         'scriptPubKey': '76a914fa20c5e0689b92014ac4c3ecfc94b5163eaca3ae88ac', 'amount': 0.49999,
         'satoshis': 49999000, 'height': 326169, 'vout': 0, 'confirmations': 100},
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
         'txid': '4417d9e022c8f4adf1ef6d9dbad7a1ee0ae44b7eb5cf61e86fd1a0ed22b1c180', 'vout': 0,
         'scriptPubKey': '76a913e90a9fcb81a78aa732c5721cc0ac4ba2075b7588ac',
         'amount': 526.37874459, 'satoshis': 52637874459, 'confirmations': 41130, 'height': 114322},
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
         'txid': 'da08e8e2e3ba55f9b45ba7f0ca14f96683c3547419fcfe10e6c8ae9f3eebe4cf', 'vout': 0,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 250.97513558, 'satoshis': 25097513558, 'height': 123456, 'confirmations': 2},
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
         'txid': '7c25ea822bbce5916a331f5851eacbc88d50c0f5a3be8a0dcea772f1baa43965', 'vout': 0,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 252.52259867, 'satoshis': 25252259867, 'height': 123458, 'confirmations': 16},
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
         'txid': '22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335', 'vout': 6,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 118.6299918, 'satoshis': 11862999180, 'height': 143434, 'confirmations': 712},
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
         'txid': 'aea9cdf0a8210238749cc4257ea05db91ea79f33691d691a859c4036ad529f85', 'vout': 6,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 114.01797238, 'satoshis': 11401797238, 'height': 77734, 'confirmations': 80},

    ]
    coin = coins['HUSH']
    api = API.get_current_definition(coin)
    address_url = '{}/addr/{}/utxo'.format(api['url'], 't1cVB16ohqZTScaSeEN2azETd1h4qXpVDnP')
    responses.add(responses.GET, address_url, json=response_data, status=200)

    main()

    res = ('HUSH Address t1cVB16ohqZTScaSeEN2azETd1h4qXpVDnP\n'
           'txid: 4417d9e022c8f4adf1ef6d9dbad7a1ee0ae44b7eb5cf61e86fd1a0ed22b1c180, confirmations: '
           '   41130, satoshis:      52637874459, amount: 526.37874459 HUSH\n'
           'txid: da08e8e2e3ba55f9b45ba7f0ca14f96683c3547419fcfe10e6c8ae9f3eebe4cf, confirmations: '
           '       2, satoshis:      25097513558, amount: 250.97513558 HUSH\n'
           'txid: 7c25ea822bbce5916a331f5851eacbc88d50c0f5a3be8a0dcea772f1baa43965, confirmations: '
           '      16, satoshis:      25252259867, amount: 252.52259867 HUSH\n'
           'txid: 22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335, confirmations: '
           '     712, satoshis:      11862999180, amount: 118.62999180 HUSH\n'
           'txid: aea9cdf0a8210238749cc4257ea05db91ea79f33691d691a859c4036ad529f85, confirmations: '
           '      80, satoshis:      11401797238, amount: 114.01797238 HUSH\n'
           '---------------------------------------------------------------------------------------'
           '-----------------------------------------------------\n'
           '        5 inputs                                                                       '
           '          satoshis:     126252444302, amount: 1262.52444302 HUSH\n')
    assert sys_stdout.getvalue() == res


@patch.object(sys, 'argv', [
    '', '-a', 't1cVB16ohqZTScaSeEN2azETd1h4qXpVDnP', '-c', 'HUSH', '-n', '10000000000', '-x', '10'])
def test_checkadress_minimum_input_greater_than_maximum_input_failure():
    with pytest.raises(Exception) as exc_info:
        main()
    exception_message = 'Minimum input threshold cannot be bigger than maximum input value!'
    assert str(exc_info.value) == exception_message


@patch.object(sys, 'argv', ['', '-a', 'ZPgeuuayirrSnBPcpYBKn3bHMFqn71nFB5', '-c', 'ZOIN'])
def test_checkadress_no_api_failure():
    coins['ZOIN'].pop('apis', None)

    with pytest.raises(Exception) as exc_info:
        main()

    assert str(exc_info.value) == 'No api has been defined for the coin ZOIN'


@responses.activate
@patch('multicrypto.commands.checkaddress.get_utxo_from_address',
       side_effect=Exception('Connection error'))
@patch.object(sys, 'argv', ['', '-a', 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt', '-c', 'HUSH'])
def test_checkadress_get_utxo_from_address_failure(get_utxo_mock):
    response_data = [
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
         'txid': '22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335', 'vout': 6,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 118.6299918, 'satoshis': 11862999180, 'height': 143434, 'confirmations': 712},
        {'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt'}
    ]
    coin = coins['HUSH']
    api = API.get_current_definition(coin)
    address_url = '{}/addr/{}/utxo'.format(api['url'], 't1cVB16ohqZTScaSeEN2azETd1h4qXpVDnP')
    responses.add(responses.GET, address_url, json=response_data, status=200)

    with pytest.raises(Exception) as exc_info:
        main()

    assert str(exc_info.value) == 'Connection error'
    assert get_utxo_mock.called
