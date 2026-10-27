import pytest
from tests import http_mock

from multicrypto.api import InsufficientFundsError, PreparedTransaction, get_api
from multicrypto.coins import coins
from multicrypto.gui.forms import (
    address_description,
    check_confirmation_words,
    check_passphrase_confirmation,
    check_password_confirmation,
    check_signable,
    check_sources,
    choose_word_positions,
    coins_with_api,
    coins_with_slip44,
    describe_error,
    describe_sweep,
    describe_transaction,
    extract_txid,
    fetch_balances,
    format_amount,
    parse_address,
    parse_amount,
    parse_int,
    parse_nodes,
    parse_thresholds,
    parse_wif,
)
from multicrypto.network import PeerAddress
from multicrypto.wallet import WalletAddress, WalletError


@pytest.mark.parametrize(
    'text, satoshis',
    [('1', 100000000), ('0.25', 25000000), (' 0,00000001 ', 1), ('21000000', 2100000000000000)],
)
def test_parse_amount(text, satoshis):
    assert parse_amount(text) == satoshis


@pytest.mark.parametrize(
    'text, message',
    [
        ('', 'Incorrect amount'),
        ('abc', 'Incorrect amount'),
        ('0', 'greater than zero'),
        ('-1', 'greater than zero'),
        ('nan', 'greater than zero'),
        ('0.000000001', 'at most 8 decimal places'),
    ],
)
def test_parse_amount_rejects_incorrect_values(text, message):
    with pytest.raises(ValueError, match=message):
        parse_amount(text)


def test_format_amount():
    assert format_amount(25000000) == '0.25000000'
    assert format_amount(1) == '0.00000001'


def test_parse_int():
    assert parse_int(' 10 ', 'Fee', minimum=0) == 10
    assert parse_int('0', 'Fee', minimum=0) == 0
    with pytest.raises(ValueError, match='Fee must be an integer'):
        parse_int('1.5', 'Fee')
    with pytest.raises(ValueError, match='Limit must be at least 1'):
        parse_int('0', 'Limit')


def test_parse_thresholds():
    assert parse_thresholds('', ' ', '') == (None, None, None)
    assert parse_thresholds('100', '200', '5') == (100, 200, 5)
    with pytest.raises(ValueError, match='Minimum input cannot be bigger'):
        parse_thresholds('300', '200', '')


def test_parse_address():
    assert parse_address(' 1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG ', 'BTC') == (
        '1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKG'
    )


@pytest.mark.parametrize(
    'address, message',
    [
        ('', 'Enter the address'),
        ('abc0', 'Incorrect address abc0'),
        ('xyz', 'Incorrect address xyz'),
        ('1BTC1NNjeiAmFqe2n1QJjkEa4aMyAhkpKH', 'Check sum is not correct'),
    ],
)
def test_parse_address_rejects_incorrect_address(address, message):
    with pytest.raises(ValueError, match=message):
        parse_address(address, 'BTC')


def test_check_password_confirmation():
    check_password_confirmation('long password', 'long password')
    with pytest.raises(ValueError, match='at least 10 characters'):
        check_password_confirmation('short', 'short')
    with pytest.raises(ValueError, match='do not match'):
        check_password_confirmation('long password', 'long passwort')


def test_parse_nodes():
    assert parse_nodes('1.2.3.4, [2001:db8::1]:18233  5.6.7.8:9', 8333) == [
        PeerAddress('1.2.3.4', 8333),
        PeerAddress('2001:db8::1', 18233),
        PeerAddress('5.6.7.8', 9),
    ]
    assert parse_nodes('  ', 8333) == []


def test_extract_txid():
    assert extract_txid('{"txid": "ab"}') == 'ab'
    with pytest.raises(ValueError, match='not accepted: Missing inputs'):
        extract_txid('Missing inputs')


def test_coins_with_api():
    symbols = coins_with_api()
    assert 'BTC' in symbols
    assert symbols == sorted(symbols)


def test_describe_transaction():
    prepared = PreparedTransaction(
        raw_transaction='00' * 225,
        inputs=[{}, {}],
        outputs=[{'address': 'dest', 'satoshis': 60000}, {'address': 'src', 'satoshis': 39000}],
        input_satoshis=100000,
        fee=1000,
    )

    rows = describe_transaction(prepared, 'BTC', ['src'], 'block explorer API')

    assert rows == [
        ('From', 'src'),
        ('To', 'dest'),
        ('Amount', '0.00060000 BTC'),
        ('Fee', '0.00001000 BTC'),
        ('Change', '0.00039000 BTC to src'),
        ('Inputs', '2 (0.00100000 BTC)'),
        ('Size', '225 bytes'),
        ('Broadcast', 'block explorer API'),
    ]


def test_describe_transaction_with_change_added_to_fee():
    prepared = PreparedTransaction(
        '00', [{}], [{'address': 'dest', 'satoshis': 98707}], 100000, 1000, 293
    )

    rows = dict(describe_transaction(prepared, 'BTC', ['src'], 'peer-to-peer network'))

    assert rows['Fee'] == '0.00001000 BTC + 293 satoshis of change below the dust threshold'
    assert rows['Change'] == 'none'


@pytest.mark.parametrize(
    'error',
    [
        ValueError('bad value'),
        WalletError('Wallet is locked'),
        InsufficientFundsError('Not enough funds'),
        OSError('disk full'),
    ],
)
def test_describe_expected_error(error):
    assert describe_error(error) == str(error)


def test_describe_unexpected_error(caplog):
    message = describe_error(KeyError('x'))

    assert message == "Unexpected error KeyError: 'x'"
    assert 'Unexpected error' in caplog.text


SEGWIT_ADDRESS = 'bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q'


def make_address(address_id='a', coin='BTC', address_type='p2wpkh', address=SEGWIT_ADDRESS):
    return WalletAddress(
        address_id, 'Savings', coin, address_type, address, "m/84'/0'/0'/0/0", 'acc', 0
    )


def test_check_sources():
    savings = make_address('a')
    other = make_address('b')
    legacy = make_address('c', address_type='p2pkh')

    assert check_sources([savings, other]) == ('BTC', 'p2wpkh')
    with pytest.raises(ValueError, match='Select at least one'):
        check_sources([])
    with pytest.raises(ValueError, match='same coin and address type'):
        check_sources([savings, legacy])


def test_address_description():
    imported = WalletAddress('i', 'Old', 'ZEN', 'p2pkh', 'znXk')

    assert address_description(make_address()) == (
        f"Savings · BTC p2wpkh · m/84'/0'/0'/0/0 · {SEGWIT_ADDRESS}"
    )
    assert address_description(imported) == 'Old · ZEN p2pkh · imported · znXk'


def test_check_passphrase_confirmation():
    check_passphrase_confirmation('x', 'x')
    with pytest.raises(ValueError, match='cannot be empty'):
        check_passphrase_confirmation('', '')
    with pytest.raises(ValueError, match='do not match'):
        check_passphrase_confirmation('a', 'b')


def test_choose_word_positions():
    positions = choose_word_positions(24)

    assert len(positions) == 3
    assert positions == sorted(set(positions))
    assert all(1 <= position <= 24 for position in positions)


def test_check_confirmation_words():
    mnemonic = 'one two three four'

    check_confirmation_words(mnemonic, {2: ' TWO ', 4: 'four'})
    with pytest.raises(ValueError, match='Word 3 is not correct'):
        check_confirmation_words(mnemonic, {2: 'two', 3: 'tree'})


def test_coins_with_slip44():
    symbols = coins_with_slip44()

    assert {'BTC', 'TBTC', 'LTC'} <= set(symbols)
    assert 'BTCH' not in symbols
    assert symbols == sorted(symbols)


@http_mock.activate
def test_fetch_balances():
    api_url = get_api(coins['BTC']).base_url
    failing_address = 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'
    no_api_coin = next(symbol for symbol, coin in coins.items() if not coin.get('apis'))
    http_mock.add(
        http_mock.GET,
        f'{api_url}/address/{SEGWIT_ADDRESS}/utxo',
        json=[
            {'txid': '11' * 32, 'vout': 0, 'status': {'confirmed': False}, 'value': 1000},
            {'txid': '22' * 32, 'vout': 1, 'status': {'confirmed': False}, 'value': 2000},
        ],
    )
    http_mock.add(
        http_mock.GET, f'{api_url}/address/{failing_address}/utxo', body='limit', status=429
    )

    balances = fetch_balances(
        [
            make_address('a'),
            make_address('b', address=failing_address),
            make_address('c', coin=no_api_coin, address_type='p2pkh', address='x'),
        ]
    )

    assert balances == {'a': 3000, 'b': 'error: API error: limit', 'c': 'no API'}


SWEEP_WIF = 'cMahea7zqjxrtgAbB7LSGbcQUr1uX1ojuat9jZodMN8kokULeTxo'


def test_parse_wif():
    assert parse_wif(f'  {SWEEP_WIF} ', 'TBTC', 'p2wpkh') == (
        SWEEP_WIF,
        'tb1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uhq9l7n',
    )
    with pytest.raises(ValueError, match='Enter the private key'):
        parse_wif(' ', 'TBTC', 'p2wpkh')
    with pytest.raises(ValueError, match='not in WIF format of BTC'):
        parse_wif(SWEEP_WIF, 'BTC', 'p2wpkh')
    with pytest.raises(ValueError, match='require compressed public key'):
        parse_wif('5KYZdUEo39z3FPrtuX2QbbwGnNP5zTd7yyr2SC1j299sBCnWjss', 'BTC', 'p2wpkh')


def test_check_signable():
    check_signable(make_address())
    with pytest.raises(ValueError, match='Taproot addresses cannot sign messages'):
        check_signable(make_address(address_type='p2tr'))


def test_describe_sweep():
    prepared = [
        PreparedTransaction(
            '00' * 200, [{}, {}], [{'address': 'dest', 'satoshis': 299000}], 300000, 1000
        ),
        PreparedTransaction(
            '00' * 120, [{}], [{'address': 'dest', 'satoshis': 99000}], 100000, 1000
        ),
    ]

    rows = describe_sweep(prepared, 'BTC', 'src', 'dest')

    assert rows == [
        ('From', 'src'),
        ('To', 'dest'),
        ('Transactions', '2'),
        ('Inputs', '3 (0.00400000 BTC)'),
        ('Fee', '0.00002000 BTC'),
        ('Received', '0.00398000 BTC'),
        (
            'Batches',
            '1. inputs: 2, amount: 0.00299000 BTC, fee: 0.00001000 BTC, size: 200 bytes\n'
            '2. inputs: 1, amount: 0.00099000 BTC, fee: 0.00001000 BTC, size: 120 bytes',
        ),
    ]
