import pytest

from multicrypto.api import InsufficientFundsError, PreparedTransaction
from multicrypto.gui.forms import (
    check_password_confirmation,
    check_sources,
    coins_with_api,
    describe_error,
    describe_transaction,
    entry_description,
    extract_txid,
    format_amount,
    parse_address,
    parse_amount,
    parse_int,
    parse_nodes,
    parse_thresholds,
)
from multicrypto.network import PeerAddress
from multicrypto.wallet import WalletEntry, WalletError

BTC_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg'


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


def test_check_sources():
    savings = WalletEntry('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    other = WalletEntry('Other', 'BTC', BTC_WIF, 'p2wpkh')
    legacy = WalletEntry('Legacy', 'BTC', BTC_WIF, 'p2pkh')

    assert check_sources([savings, other]) == ('BTC', 'p2wpkh')
    with pytest.raises(ValueError, match='Select at least one'):
        check_sources([])
    with pytest.raises(ValueError, match='same coin and address type'):
        check_sources([savings, legacy])


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


def test_entry_description():
    entry = WalletEntry('Savings', 'BTC', BTC_WIF, 'p2wpkh')
    assert entry_description(entry) == (
        'Savings · BTC p2wpkh · bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q'
    )


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
