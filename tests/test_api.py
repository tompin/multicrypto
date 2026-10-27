import urllib.error
from datetime import date, timedelta

import pytest
from tests import http_mock

from multicrypto.api import (
    EsploraAPI,
    InsightAPI,
    InsufficientFundsError,
    PreparedTransaction,
    broadcast_prepared,
    get_api,
    get_utxo_from_private_keys,
    prepare_from_private_keys,
    prepare_sweep,
    send_from_private_keys,
)
from multicrypto.coins import coins

data = [
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '4417d9e022c8f4adf1ef6d9dbad7a1ee0ae44b7eb5cf61e86fd1a0ed22b1c180',
        'vout': 0,
        'scriptPubKey': '76a913e90a9fcb81a78aa732c5721cc0ac4ba2075b7588ac',
        'amount': 526.37874459,
        'satoshis': 52637874459,
        'confirmations': 41130,
        'height': 114322,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': 'da08e8e2e3ba55f9b45ba7f0ca14f96683c3547419fcfe10e6c8ae9f3eebe4cf',
        'vout': 0,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 250.97513558,
        'satoshis': 25097513558,
        'height': 123456,
        'confirmations': 2,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '7c25ea822bbce5916a331f5851eacbc88d50c0f5a3be8a0dcea772f1baa43965',
        'vout': 0,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 252.52259867,
        'satoshis': 25252259867,
        'height': 123458,
        'confirmations': 16,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '22c66de2660bc913d2d6a2a7013a8762e92374fcb34609eb935d7fa4704f3335',
        'vout': 6,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 118.6299918,
        'satoshis': 11862999180,
        'height': 143434,
        'confirmations': 712,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': 'aea9cdf0a8210238749cc4257ea05db91ea79f33691d691a859c4036ad529f85',
        'vout': 6,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 114.01797238,
        'satoshis': 11401797238,
        'height': 77734,
        'confirmations': 80,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': 'aefcff17bb86ca19742f9418af1048138bd9623ef7936f0292754324c78fff56',
        'vout': 0,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 124.35947057,
        'satoshis': 12435947057,
        'height': 113143,
        'confirmations': 592,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '0e9962f9298ad2615a5caa8425f31b53baaf7c7e8e17053a006c3e9466e65a3d',
        'vout': 1,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 108.42202152,
        'satoshis': 10842202152,
        'height': 112534,
        'confirmations': 548,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': 'd72687288bc0d47317daedebd4be286de936bfdb434034c7aaae8c4d3f90d421',
        'vout': 10,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 108.66682024,
        'satoshis': 10866682024,
        'height': 111935,
        'confirmations': 647,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': 'ba25905edd92bb4d8a030611c255e26988da7700a4f2df3d2777d1077ad62235',
        'vout': 6,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 111.57138797,
        'satoshis': 11157138797,
        'height': 111900,
        'confirmations': 682,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '74410f32a5c57c9780ba28f3c7359d8314766f92d8acf9ce7c914d259463316d',
        'vout': 11,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 107.99130385,
        'satoshis': 10799130385,
        'height': 111677,
        'confirmations': 605,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '51984212a42e924cc1b106400ebd0deda5f1000e9e3fe280c0461f69ac461586',
        'vout': 9,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 113.64462462,
        'satoshis': 11364462462,
        'height': 111610,
        'confirmations': 872,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '75f537c05899d257172d9b1ebb2a2e0f33a564486d10a03bdb4766c84f63ad11',
        'vout': 1,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 830.63988616,
        'satoshis': 83063988616,
        'height': 111421,
        'confirmations': 60961,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'vout': 0,
        'height': 44355,
        'txid': '95c50fb3915eb7a1f87d9cc2369cfd62278029859cc03bf77496674f07a9e902',
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 154.95474469,
        'satoshis': 15495474469,
        'confirmations': 5098,
    },
    {
        'address': 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        'txid': '3fd8c7ea1b87141163d3436f0dbc0f8b8915621f092a3fc12544228590123b3a',
        'vout': 1,
        'scriptPubKey': '76a91413e90a9fcb63a78aa732c5753cc0ac4ba2075b7588ac',
        'amount': 949.9998,
        'satoshis': 94999980000,
        'height': 245617,
        'confirmations': 6666,
    },
]


@http_mock.activate
def test_sendcrypto_success():
    coin = coins['SAFE']
    api_url = InsightAPI(coin).base_url
    send_url = '{}/tx/send'.format(api_url)
    address_url = '{}/addr/{}/utxo'.format(api_url, 'Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM')
    http_mock.add(http_mock.GET, address_url, json=data, status=200)
    http_mock.add(
        http_mock.POST,
        send_url,
        json={'txid': '904c6c12dcd011b30079c3a8646fa744b4d3da0a27f3e67194287a0d0b3bd689'},
        content_type='application/json',
        status=200,
    )

    res = send_from_private_keys(
        coin=coins['SAFE'],
        wif_private_keys=['Uy3kRcw1mKVCecWBasE7BEhkirVEtmLQcJ5JyCZMnQkah7X263R6'],
        input_addresses=None,
        unlocking_scripts=None,
        destination_address='Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
        satoshis=100000000000,
        fee=10000,
        minimum_input_threshold=20000000000,
        maximum_input_threshold=60000000000,
        limit_inputs=250,
    )

    assert res == '{"txid": "904c6c12dcd011b30079c3a8646fa744b4d3da0a27f3e67194287a0d0b3bd689"}'


def test_insight_api_uses_current_api_index():
    coin = {'apis': [{'url': 'https://first.example'}, {'url': 'https://second.example'}]}

    assert InsightAPI(coin).base_url == 'https://first.example'
    assert InsightAPI({**coin, 'current_api_index': 1}).base_url == 'https://second.example'


@http_mock.activate
def test_insight_api_get_history_block():
    coin = coins['ZEN']
    api = InsightAPI(coin, timeout=5)
    block = {'hash': '0000000003ac1a4b', 'height': 1000000}
    http_mock.add(http_mock.GET, f'{api.base_url}/blocks', json={'blocks': [block]}, status=200)

    assert api.get_history_block() == block
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert http_mock.calls[0].request.url == (
        f'{api.base_url}/blocks?limit=1&blockDate={yesterday}'
    )


@http_mock.activate
def test_insight_api_passes_timeout_to_urlopen():
    api = InsightAPI(coins['SAFE'], timeout=5)
    address_url = f'{api.base_url}/addr/Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM/utxo'
    http_mock.add(http_mock.GET, address_url, json=[])

    assert api.get_utxo('Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM') == []

    request = http_mock.calls[0].request
    assert (request.method, request.url, request.body) == ('GET', address_url, None)
    assert request.headers['user-agent'] == 'multicrypto'
    assert http_mock.calls[0].timeout == 5


@http_mock.activate
def test_insight_api_send_raw_transaction_sends_json():
    api = InsightAPI(coins['SAFE'])
    http_mock.add(http_mock.POST, f'{api.base_url}/tx/send', body='Missing inputs', status=400)

    assert api.send_raw_transaction('0100') == 'Missing inputs'

    request = http_mock.calls[0].request
    assert request.body == '{"rawtx": "0100"}'
    assert request.headers['content-type'] == 'application/json'


@http_mock.activate
def test_insight_api_connection_error():
    with pytest.raises(urllib.error.URLError, match='Connection refused'):
        InsightAPI(coins['SAFE']).get_utxo('Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM')


def test_send_from_private_keys_without_inputs():
    with pytest.raises(ValueError, match='Missing required parameters'):
        send_from_private_keys(
            coin=coins['SAFE'],
            wif_private_keys=None,
            input_addresses=None,
            unlocking_scripts=None,
            destination_address='Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
            satoshis=1,
            fee=1,
        )


@http_mock.activate
def test_send_from_private_keys_insufficient_funds():
    coin = coins['SAFE']
    api_url = InsightAPI(coin).base_url
    address_url = f'{api_url}/addr/Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM/utxo'
    http_mock.add(http_mock.GET, address_url, json=data[:1], status=200)

    with pytest.raises(InsufficientFundsError, match='Sum of inputs is 52637874459'):
        send_from_private_keys(
            coin=coin,
            wif_private_keys=['Uy3kRcw1mKVCecWBasE7BEhkirVEtmLQcJ5JyCZMnQkah7X263R6'],
            input_addresses=None,
            unlocking_scripts=None,
            destination_address='Rt2NesjPyEEDrHiC5xtYus9tBJTgdtWBfM',
            satoshis=100000000000,
            fee=10000,
        )


ESPLORA_URL = 'https://mempool.space/api'
SEGWIT_ADDRESS = 'bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q'


def test_get_api_selects_client_by_type():
    coin = coins['BTC']

    assert isinstance(get_api(coins['SAFE']), InsightAPI)
    assert isinstance(get_api(coin), EsploraAPI)
    assert get_api(coin).base_url == ESPLORA_URL
    assert get_api({**coin, 'current_api_index': 1}).base_url == 'https://blockstream.info/api'


@http_mock.activate
def test_esplora_api_get_utxo():
    http_mock.add(
        http_mock.GET,
        f'{ESPLORA_URL}/address/{SEGWIT_ADDRESS}/utxo',
        json=[
            {
                'txid': '11' * 32,
                'vout': 1,
                'status': {'confirmed': True, 'block_height': 900000},
                'value': 150000000,
            },
            {'txid': '22' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 5000},
        ],
        status=200,
    )
    http_mock.add(http_mock.GET, f'{ESPLORA_URL}/blocks/tip/height', body='900009', status=200)

    utxos = EsploraAPI(coins['BTC']).get_utxo(SEGWIT_ADDRESS)

    script = '0014925d4028880bd0c9d68fbc7fc7dfee976698629c'
    assert utxos == [
        {
            'address': SEGWIT_ADDRESS,
            'txid': '11' * 32,
            'vout': 1,
            'scriptPubKey': script,
            'satoshis': 150000000,
            'amount': 1.5,
            'height': 900000,
            'confirmations': 10,
        },
        {
            'address': SEGWIT_ADDRESS,
            'txid': '22' * 32,
            'vout': 0,
            'scriptPubKey': script,
            'satoshis': 5000,
            'amount': 0.00005,
            'height': None,
            'confirmations': 0,
        },
    ]


@http_mock.activate
def test_esplora_api_get_utxo_error():
    http_mock.add(
        http_mock.GET,
        f'{ESPLORA_URL}/address/{SEGWIT_ADDRESS}/utxo',
        body='Too many unspent outputs',
        status=400,
    )

    with pytest.raises(ValueError, match='API error: Too many unspent outputs'):
        EsploraAPI(coins['BTC']).get_utxo(SEGWIT_ADDRESS)


@http_mock.activate
def test_esplora_api_send_raw_transaction():
    http_mock.add(http_mock.POST, f'{ESPLORA_URL}/tx', body='ab' * 32, status=200)

    result = EsploraAPI(coins['BTC']).send_raw_transaction('0100')

    assert result == '{"txid": "%s"}' % ('ab' * 32)
    assert http_mock.calls[0].request.body == '0100'
    assert http_mock.calls[0].request.headers['content-type'] == 'text/plain'


@http_mock.activate
def test_esplora_api_send_raw_transaction_rejected():
    http_mock.add(
        http_mock.POST, f'{ESPLORA_URL}/tx', body='sendrawtransaction RPC error', status=400
    )

    with pytest.raises(ValueError, match='Transaction rejected: sendrawtransaction RPC error'):
        EsploraAPI(coins['BTC']).send_raw_transaction('0100')


@http_mock.activate
def test_send_from_private_keys_esplora_p2wpkh():
    http_mock.add(
        http_mock.GET,
        f'{ESPLORA_URL}/address/{SEGWIT_ADDRESS}/utxo',
        json=[{'txid': '11' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 100000}],
        status=200,
    )
    http_mock.add(http_mock.POST, f'{ESPLORA_URL}/tx', body='cd' * 32, status=200)

    result = send_from_private_keys(
        coin=coins['BTC'],
        wif_private_keys=['KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'],
        input_addresses=None,
        unlocking_scripts=None,
        destination_address='15ZTYi2AhyAAqzfhbFnsRMMXXZnwiymnU4',
        satoshis=60000,
        fee=1000,
        address_type='p2wpkh',
    )

    assert result == '{"txid": "%s"}' % ('cd' * 32)
    raw_transaction = http_mock.calls[1].request.body
    assert raw_transaction.startswith('010000000001' + '01' + '11' * 32 + '00000000' + '00')


def send_p2wpkh_with_change(satoshis):
    """Send from P2WPKH address with single 100000 satoshis input and 1000 satoshis fee."""
    http_mock.add(
        http_mock.GET,
        f'{ESPLORA_URL}/address/{SEGWIT_ADDRESS}/utxo',
        json=[{'txid': '11' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 100000}],
        status=200,
    )
    http_mock.add(http_mock.POST, f'{ESPLORA_URL}/tx', body='cd' * 32, status=200)
    send_from_private_keys(
        coin=coins['BTC'],
        wif_private_keys=['KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'],
        input_addresses=None,
        unlocking_scripts=None,
        destination_address='15ZTYi2AhyAAqzfhbFnsRMMXXZnwiymnU4',
        satoshis=satoshis,
        fee=1000,
        address_type='p2wpkh',
    )
    raw_transaction = http_mock.calls[1].request.body
    inputs = '01' + '11' * 32 + '00000000' + '00' + 'ffffffff'
    assert raw_transaction.startswith('010000000001' + inputs)
    return raw_transaction[len('010000000001' + inputs) :]


CHANGE_P2WPKH_SCRIPT = '16' + '0014925d4028880bd0c9d68fbc7fc7dfee976698629c'


@http_mock.activate
def test_send_from_private_keys_dust_change_added_to_fee(caplog):
    caplog.set_level('INFO')

    outputs = send_p2wpkh_with_change(satoshis=98707)  # 293 satoshis change

    assert outputs.startswith('01' + '9381010000000000' + '1976a914')
    assert CHANGE_P2WPKH_SCRIPT not in outputs
    assert 'Change 293 is below dust threshold 294 and was added to the fee' in caplog.text


@http_mock.activate
def test_send_from_private_keys_change_at_dust_threshold():
    outputs = send_p2wpkh_with_change(satoshis=98706)  # 294 satoshis change

    assert outputs.startswith('02' + '9281010000000000' + '1976a914')
    assert '2601000000000000' + CHANGE_P2WPKH_SCRIPT in outputs


P2WPKH_SEND_ARGS = dict(
    coin=coins['BTC'],
    wif_private_keys=['KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'],
    input_addresses=None,
    unlocking_scripts=None,
    destination_address='15ZTYi2AhyAAqzfhbFnsRMMXXZnwiymnU4',
    satoshis=60000,
    fee=1000,
    address_type='p2wpkh',
)


def add_p2wpkh_responses():
    http_mock.add(
        http_mock.GET,
        f'{ESPLORA_URL}/address/{SEGWIT_ADDRESS}/utxo',
        json=[{'txid': '11' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 100000}],
        status=200,
    )
    http_mock.add(http_mock.POST, f'{ESPLORA_URL}/tx', body='cd' * 32, status=200)


@http_mock.activate
def test_prepare_from_private_keys_does_not_broadcast():
    add_p2wpkh_responses()

    prepared = prepare_from_private_keys(**P2WPKH_SEND_ARGS)

    assert [call.request.method for call in http_mock.calls] == ['GET']
    assert prepared.input_satoshis == 100000
    assert prepared.fee == 1000
    assert prepared.change_added_to_fee == 0
    assert len(prepared.inputs) == 1
    assert prepared.outputs == [
        {'address': '15ZTYi2AhyAAqzfhbFnsRMMXXZnwiymnU4', 'satoshis': 60000},
        {'address': SEGWIT_ADDRESS, 'satoshis': 39000},
    ]
    assert prepared.raw_transaction.startswith('010000000001' + '01' + '11' * 32 + '00000000')


@http_mock.activate
def test_broadcast_prepared_sends_the_same_transaction_as_send_from_private_keys():
    add_p2wpkh_responses()

    prepared = prepare_from_private_keys(**P2WPKH_SEND_ARGS)
    result = broadcast_prepared(coins['BTC'], prepared)
    send_from_private_keys(**P2WPKH_SEND_ARGS)

    assert result == '{"txid": "%s"}' % ('cd' * 32)
    assert http_mock.calls[1].request.body == prepared.raw_transaction
    assert http_mock.calls[3].request.body == prepared.raw_transaction


def test_broadcast_prepared_with_broadcast_function():
    prepared = PreparedTransaction('0100', [], [], 0, 0)

    result = broadcast_prepared(coins['BTC'], prepared, broadcast=lambda raw: f'sent {raw}')

    assert result == 'sent 0100'


@http_mock.activate
def test_prepare_from_private_keys_reports_change_added_to_fee():
    add_p2wpkh_responses()

    prepared = prepare_from_private_keys(**{**P2WPKH_SEND_ARGS, 'satoshis': 98707})

    assert prepared.change_added_to_fee == 293
    assert len(prepared.outputs) == 1


SWEEP_WIF = 'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo'
SWEEP_ADDRESS = 'tb1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uhq9l7n'
SWEEP_DESTINATION = 'tb1qerzrlxcfu24davlur5sqmgzzgsal6wusda40er'


def sweep_utxos(values):
    api_url = get_api(coins['TBTC']).base_url
    http_mock.add(
        http_mock.GET,
        f'{api_url}/address/{SWEEP_ADDRESS}/utxo',
        json=[
            {'txid': f'{i:02x}' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': value}
            for i, value in enumerate(values)
        ],
    )
    return list(get_utxo_from_private_keys(coins['TBTC'], [SWEEP_WIF], 'p2wpkh'))


@http_mock.activate
def test_prepare_sweep_splits_inputs_into_batches():
    utxos = sweep_utxos([100000, 200000, 300000])

    prepared = prepare_sweep(coins['TBTC'], utxos, SWEEP_DESTINATION, 1000, 2)

    assert [len(transaction.inputs) for transaction in prepared] == [2, 1]
    assert [transaction.outputs for transaction in prepared] == [
        [{'address': SWEEP_DESTINATION, 'satoshis': 299000}],
        [{'address': SWEEP_DESTINATION, 'satoshis': 299000}],
    ]
    assert [transaction.fee for transaction in prepared] == [1000, 1000]
    assert len(http_mock.calls) == 1  # nothing was broadcast


def test_prepare_sweep_without_inputs():
    with pytest.raises(ValueError, match='No inputs found for the private key'):
        prepare_sweep(coins['TBTC'], [], SWEEP_DESTINATION, 1000, 50)


@pytest.mark.parametrize(
    'value, error',
    [
        (10000, 'Fee 10000 is not smaller than sum of batch inputs 10000'),
        (10100, 'Amount 100 of the batch is below the dust threshold 294'),
    ],
)
@http_mock.activate
def test_prepare_sweep_batch_cannot_be_sent(value, error):
    utxos = sweep_utxos([value])

    with pytest.raises(ValueError, match=error):
        prepare_sweep(coins['TBTC'], utxos, SWEEP_DESTINATION, 10000, 50)
