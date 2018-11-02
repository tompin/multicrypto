import sys
from io import StringIO
from unittest.mock import patch

import responses

from multicrypto.apis import API
from multicrypto.coins import coins
from multicrypto.commands.sendcrypto import main


@responses.activate
@patch.object(sys, 'argv', [
    '', '-a', 't1cVB16ohqZTScaSeEN2azETd1h4qXpVDnP', '-c', 'HUSH', '-s', '50900000', '-p',
    'L262yBzq3JRNwBGsTRSGRjNDQNvjXVhG7z2cwLGwDAGkUaFoKkwc,'
    'L3DrZ29vdnLDFNsoDTgz1J79B8QCzU6vrfTacHoYUk6NQYmSoeur'])
@patch('sys.stdout', new_callable=StringIO)
def test_sendcrypto_success(sys_stdout):
    coin = coins['HUSH']
    api = API.get_current_definition(coin)
    send_url = '{}/tx/send'.format(api['url'])
    address_url1 = '{}/addr/{}/utxo'.format(api['url'], 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt')
    address_url2 = '{}/addr/{}/utxo'.format(api['url'], 't1TJ7cjWWBxozgekVWVKzCCXKhK4F59v4HB')

    responses.add(responses.GET, address_url1,
                  json=[{'address': 't1ggACQ3HenPuiwEaL9vBFcDtxQogHvXzvt',
                         'txid': 'ff269d70ad429f2f3b8e042cf88f76c2f8a9e10de67f626fce25784fc29adb1e',
                         'scriptPubKey': '76a914fa20c5e0689b92014ac4c3ecfc94b5163eaca3ae88ac',
                         'amount': 0.49999, 'satoshis': 49999000, 'height': 326169, 'vout': 0,
                         'confirmations': 100}], status=200)
    responses.add(responses.GET, address_url2,
                  json=[{'address': 't1TJ7cjWWBxozgekVWVKzCCXKhK4F59v4HB',
                         'txid': 'e2860bc090fecbe97ebafae2a31c9d9df4aca221002fc8c57d75c5a2ac58af51',
                         'scriptPubKey': '76a914675bd5240d72cb96e7722b0785ccc60cb168b7ad88ac',
                         'amount': 0.01, 'satoshis': 1000000, 'height': 326168, 'vout': 1,
                         'confirmations': 102}], status=200)
    responses.add(responses.POST, send_url,
                  json={'txid': 'a9700b6b18559c2ee976c5a7a5b51f1f9b47daacca96148b3b0afd2b0c6da138'},
                  content_type='application/json', status=200)
    main()

    res = '{"txid": "a9700b6b18559c2ee976c5a7a5b51f1f9b47daacca96148b3b0afd2b0c6da138"}\n'
    assert sys_stdout.getvalue() == res
