import sys
from io import StringIO
from unittest.mock import patch

import responses

from multicrypto.coins import coins
from multicrypto.commands.sweepaddress import main

data = [{'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '4417d9e022c8f4adf1ef6d9dbad7a1ee0ae44b7eb5cf61e86fd1a0ed22b1c180', 'vout': 0,
         'scriptPubKey': '76a913e90a9fcb81a78aa732c5721cc0ac4ba2075b7588ac',
         'amount': 526.37874459, 'satoshis': 52637874459, 'confirmations': 41130, 'height': 114322},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': 'da08e8e2e3ba55f9b45ba7f0ca14f96683c3547419fcfe10e6c8ae9f3eebe4cf', 'vout': 0,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 250.97513558, 'satoshis': 25097513558, 'height': 123456, 'confirmations': 2},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '7c25ea822bbce5916a331f5851eacbc88d50c0f5a3be8a0dcea772f1baa43965', 'vout': 0,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 252.52259867, 'satoshis': 25252259867, 'height': 123458, 'confirmations': 16},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335', 'vout': 6,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 118.6299918, 'satoshis': 11862999180, 'height': 143434, 'confirmations': 712},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': 'aea9cdf0a8210238749cc4257ea05db91ea79f33691d691a859c4036ad529f85', 'vout': 6,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 114.01797238, 'satoshis': 11401797238, 'height': 77734, 'confirmations': 80},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': 'aefcff17bb86ca19742f9418af1048138bd9623ef7936f0292754324c78fff56', 'vout': 0,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 124.35947057, 'satoshis': 12435947057, 'height': 113143, 'confirmations': 592},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '0e9962f9298ad2615a5caa8425f31b53baaf7c7e8e17053a006c3e9466e65a3d', 'vout': 1,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 108.42202152, 'satoshis': 10842202152, 'height': 112534, 'confirmations': 548},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': 'd72687288bc0d47317daedebd4be286de936bfdb434034c7aaae8c4d3f90d421', 'vout': 10,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 108.66682024, 'satoshis': 10866682024, 'height': 111935, 'confirmations': 647},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': 'ba25905edd92bb4d8a030611c255e26988da7700a4f2df3d2777d1077ad62235', 'vout': 6,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 111.57138797, 'satoshis': 11157138797, 'height': 111900, 'confirmations': 682},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '74410f32a5c57c9780ba28f3c7359d8314766f92d8acf9ce7c914d259463316d', 'vout': 11,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 107.99130385, 'satoshis': 10799130385, 'height': 111677, 'confirmations': 605},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '51984212a42e924cc1b106400ebd0deda5f1000e9e3fe280c0461f69ac461586', 'vout': 9,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 113.64462462, 'satoshis': 11364462462, 'height': 111610, 'confirmations': 872},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '75f537c05899d257172d9b1ebb2a2e0f33a564486d10a03bdb4766c84f63ad11', 'vout': 1,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 830.63988616, 'satoshis': 83063988616, 'height': 111421,
         'confirmations': 60961},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM', 'vout': 0, 'height': 44355,
         'txid': '95c50fb3915eb7a1f87d9cc2369cfd62278029859cc03bf77496674f07a9e902',
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
         'amount': 154.95474469, 'satoshis': 15495474469, 'confirmations': 5098},
        {'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
         'txid': '3fd8c7ea1b87141163d3436f0dbc0f8b8915621f092a3fc12544228590123b3a', 'vout': 1,
         'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac', 'amount': 949.9998,
         'satoshis': 94999980000, 'height': 245617, 'confirmations': 6666}]


@responses.activate
@patch.object(sys, 'argv', [
    '', '-c', 'SAFE', '-b', '5', '-p', 'Uy3kRcw1mKVCecWBasE7BEhkirVEtmLQcJ5JyCZMnQkah7X263R6'])
@patch('sys.stdout', new_callable=StringIO)
def test_sweepaddress_succes(sys_stdout):
    api = coins['SAFE']['api'][0]
    responses.add(responses.GET, api['utxo'].format('Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM'),
                  json=data, status=200)
    responses.add(responses.POST, api['send'], content_type='application/json', status=200,
                  json={'txid': '480048710f7443a1fbfe9038e846cd8e30a94dde9b3e9f4507fea923f62c662f'})
    responses.add(responses.POST, api['send'], content_type='application/json', status=200,
                  json={'txid': '7c8cfe3ceceba3e03457d62fbcbe272012ecafcd8006e3a4b366efdaf726ac98'})
    responses.add(responses.POST, api['send'], content_type='application/json', status=200,
                  json={'txid': 'a6c82d9295579275cc3b7a4ca80210230a104c159818cfd203b71a6370daff62'})

    main()

    res = '{"txid": "480048710f7443a1fbfe9038e846cd8e30a94dde9b3e9f4507fea923f62c662f"}\n' \
          '{"txid": "7c8cfe3ceceba3e03457d62fbcbe272012ecafcd8006e3a4b366efdaf726ac98"}\n' \
          '{"txid": "a6c82d9295579275cc3b7a4ca80210230a104c159818cfd203b71a6370daff62"}\n'
    assert sys_stdout.getvalue() == res
