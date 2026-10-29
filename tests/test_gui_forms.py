import pytest
from tests import http_mock

from multicrypto.api import InsufficientFundsError, PreparedTransaction, get_api
from multicrypto.coins import coins, ethereum_coins
from multicrypto.gui.forms import (
    add_private_key,
    address_details,
    address_type_name,
    check_confirmation_words,
    check_passphrase_confirmation,
    check_password_confirmation,
    check_signable,
    check_sources,
    choose_word_positions,
    all_coins,
    all_coins_with_api,
    coins_with_api,
    coins_with_slip44,
    format_coin_amount,
    is_testnet,
    key_entry_address,
    scannable_coins,
    source_wif,
    describe_error,
    describe_ethereum_transaction,
    describe_sweep,
    describe_transaction,
    extract_txid,
    fetch_balances,
    format_amount,
    format_duration,
    parse_address,
    parse_amount,
    parse_ether_amount,
    parse_fee_rate,
    parse_gwei_field,
    parse_int,
    parse_nodes,
    parse_private_key_input,
    parse_rpc_nodes,
    parse_thresholds,
    parse_vanity_pattern,
    parse_wif,
    translate_address_text,
    translated_key_addresses,
    translated_private_key,
)
from multicrypto.ethereum import GWEI, Transaction
from multicrypto.ethereum_api import FeeSuggestion, PreparedEthereumTransaction
from multicrypto.network import PeerAddress
from multicrypto.wallet import Wallet, WalletAddress, WalletError


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
        vsize=200,
    )

    rows = describe_transaction(prepared, 'BTC', ['src'], 'block explorer API')

    assert rows == [
        ('From', 'src'),
        ('To', 'dest'),
        ('Amount', '0.00060000 BTC'),
        ('Fee', '0.00001000 BTC (1000 satoshis, 5.0 sat/vB)'),
        ('Change', '0.00039000 BTC to src'),
        ('Inputs', '2 (0.00100000 BTC)'),
        ('Size', '200 vB (225 bytes)'),
        ('Broadcast', 'block explorer API'),
    ]
    rows = dict(
        describe_transaction(prepared, 'BTC', ['src'], 'block explorer API', "m/84'/0'/0'/1/0")
    )
    assert rows['Change'] == "0.00039000 BTC to src (m/84'/0'/0'/1/0)"


def test_describe_transaction_with_high_fee_rate():
    prepared = PreparedTransaction(
        '00' * 10, [{}], [{'address': 'dest', 'satoshis': 1000}], 3000, 2000, vsize=1
    )

    rows = describe_transaction(prepared, 'BTC', ['src'], 'block explorer API')

    assert rows[-1] == ('Warning', 'Fee rate is above 1000 sat/vB')


def test_describe_transaction_with_high_fee_rate_of_coin():
    # 20000 sat/vB is a usual fee rate of Dogecoin (0.2 DOGE/kB)
    prepared = PreparedTransaction(
        '00' * 10, [{}], [{'address': 'dest', 'satoshis': 10**8}], 2 * 10**8, 20000, vsize=1
    )

    assert describe_transaction(prepared, 'DOGE', ['src'], 'API')[-1][0] != 'Warning'
    prepared = PreparedTransaction(
        '00' * 10, [{}], [{'address': 'dest', 'satoshis': 10**8}], 2 * 10**8, 2 * 10**6, vsize=1
    )
    assert describe_transaction(prepared, 'DOGE', ['src'], 'API')[-1] == (
        'Warning',
        'Fee rate is above 1000000 sat/vB',
    )


def test_describe_transaction_with_change_added_to_fee():
    prepared = PreparedTransaction(
        '00', [{}], [{'address': 'dest', 'satoshis': 98707}], 100000, 1000, 293
    )

    rows = dict(describe_transaction(prepared, 'BTC', ['src'], 'peer-to-peer network'))

    assert rows['Fee'].startswith('0.00001000 BTC (1000 satoshis')
    assert rows['Fee'].endswith(' + 293 satoshis of change below the dust threshold')
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


def test_is_testnet():
    assert [symbol for symbol in sorted(coins) if is_testnet(symbol)] == ['TBTC', 'TLTC']


def test_address_details():
    wallet = Wallet.create(' '.join(['abandon'] * 11 + ['about']), '')
    group = wallet.add_account_group('', 'BTC')
    [address] = wallet.account_addresses(group.accounts[1])
    imported = wallet.add_wif(
        'Old', 'BTC', 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFUkZ1RnqvVg', 'p2pkh'
    )

    assert address_type_name('p2sh-p2wpkh') == 'SegWit (p2sh-p2wpkh)'
    assert address_details(wallet, address) == [
        ('Account', 'Bitcoin #0'),
        ('Address type', 'Native SegWit (p2wpkh)'),
        ('Path', "m/84'/0'/0'/0/0"),
        ('Label', 'Address 0'),
    ]
    assert address_details(wallet, imported) == [
        ('Account', 'Imported key'),
        ('Address type', 'Legacy (p2pkh)'),
        ('Path', '—'),
        ('Label', 'Old'),
    ]


def test_check_passphrase_confirmation():
    check_passphrase_confirmation('x', 'x')
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


def test_coins_with_slip44(monkeypatch):
    monkeypatch.delitem(coins['DOGE'], 'slip44')
    symbols = coins_with_slip44()

    assert {'BTC', 'TBTC', 'LTC'} <= set(symbols)
    assert 'DOGE' not in symbols
    assert symbols == sorted(symbols)


@http_mock.activate
def test_fetch_balances(monkeypatch):
    api_url = get_api(coins['BTC']).base_url
    failing_address = 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'
    no_api_coin = 'DOGE'
    monkeypatch.delitem(coins[no_api_coin], 'apis')
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

    assert balances == {
        'a': 3000,
        'b': 'error: Too many requests to https://mempool.space/api, try again later',
        'c': 'no API',
    }


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
            '00' * 200, [{}, {}], [{'address': 'dest', 'satoshis': 299000}], 300000, 1000, 0, 150
        ),
        PreparedTransaction(
            '00' * 120, [{}], [{'address': 'dest', 'satoshis': 99000}], 100000, 1000, 0, 100
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
            '1. inputs: 2, amount: 0.00299000 BTC, fee: 0.00001000 BTC (6.7 sat/vB), size: 150 vB\n'
            '2. inputs: 1, amount: 0.00099000 BTC, fee: 0.00001000 BTC (10.0 sat/vB), size: 100 vB',
        ),
    ]


KEY_WIF = 'KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSu'
KEY_INTEGER = '43265286516710475498079662292151387463063605274999989765271924584279496871562'


def test_translate_address_text():
    assert (
        translate_address_text(' 1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi ', 'BTC', 'DOGE')
        == 'DMLko4rFfwapsw1D6cWd1hw5QSTZpJn6vU'
    )
    assert (
        translate_address_text('3DnW8JGpPViEZdpqat8qky1zc26EKbXnmM', 'BTC', 'DOGE')
        == 'A4Xks9LiTZb8U1CK11oG16eNJbUGS6A8JH'
    )
    with pytest.raises(ValueError, match='need the private key'):
        translate_address_text('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu', 'BTC', 'LTC')
    with pytest.raises(ValueError, match='Check sum is not correct'):
        translate_address_text('1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hj', 'BTC', 'DOGE')


@pytest.mark.parametrize(
    'text, integer',
    [
        (KEY_WIF, False),
        (f' {KEY_INTEGER} ', True),
        ('0x5fa748cc9721dec00a3afcbe79e8f264a9cb9d8480a6615295970678344e4e8a', True),
    ],
)
def test_parse_private_key_input(text, integer):
    assert parse_private_key_input(text, integer) == KEY_WIF


@pytest.mark.parametrize(
    'text, integer, error',
    [
        ('', False, 'Enter the private key'),
        ('KzReaUKzSaGarrhFhjNMweTrpUx4gqX1KCMFSWJx9374kYNHpmSv', False, 'checksum'),
        ('KzRea0', False, 'only base58 characters'),
        ('1HCfFoucNXgYLvpcN2X4TwmUXJjGUMJ2hi', False, 'Incorrect private key'),
        ('0', True, 'must be an integer from 1'),
        ('xyz', True, 'must be an integer from 1'),
    ],
)
def test_parse_private_key_input_errors(text, integer, error):
    with pytest.raises(ValueError, match=error):
        parse_private_key_input(text, integer)


def test_translated_key_addresses():
    assert translated_key_addresses(KEY_WIF, 'LTC') == (
        'T6Fv2DdAqxFBdhL8FNKEA11EmLbNkvXu8QFWJJwVi1HEGS1NSUTV',
        [
            ('p2pkh', 'LbRcX2DSTBvbbjWmYAWMjxqEjX6YWvssUp'),
            ('p2sh-p2wpkh', '3Png2L1DD4tqaHeu5p6USVcUuo55MmrWoR'),
            ('p2wpkh', 'ltc1qkxmgtft32j3uxfjmseypq84xlwaglttjrr3k59'),
            ('p2tr', 'ltc1pk5jxttt9wcct7sp4eg4m2gdhd49tpns2kz8wqfzt79z4amzyqkeqgrc3cz'),
        ],
    )
    _, addresses = translated_key_addresses(
        '5KYZdUEo39z3FPrtuX2QbbwGnNP5zTd7yyr2SC1j299sBCnWjss', 'LTC'
    )
    assert [address_type for address_type, _ in addresses] == ['p2pkh']


def test_parse_vanity_pattern():
    assert parse_vanity_pattern(' BC1QXY ', 'BTC', 'p2wpkh') == 'bc1qxy'
    with pytest.raises(ValueError, match='Enter the beginning of the address'):
        parse_vanity_pattern(' ', 'BTC', 'p2pkh')


@pytest.mark.parametrize(
    'seconds, text',
    [(0.4, '0 s'), (42, '42 s'), (150, '2 min'), (7200, '2 h'), (3 * 86400, '3 days')],
)
def test_format_duration(seconds, text):
    assert format_duration(seconds) == text


@pytest.mark.parametrize('text, rate', [('2', 2.0), (' 2,5 ', 2.5), ('0.1', 0.1)])
def test_parse_fee_rate(text, rate):
    assert parse_fee_rate(text) == rate


@pytest.mark.parametrize(
    'text, error',
    [
        ('', 'Enter the fee rate or press Estimate'),
        ('abc', 'Incorrect fee rate'),
        ('0', 'greater than zero'),
        ('1.25', 'at most one decimal place'),
    ],
)
def test_parse_fee_rate_errors(text, error):
    with pytest.raises(ValueError, match=error):
        parse_fee_rate(text)


ETH_KEY = '46' * 32
ETH_KEY_ADDRESS = '0x9d8A62f656a8d1615C1294fd71e9CFb3E4855A4F'
ETH_NODE = 'https://ethereum-rpc.publicnode.com'


def test_coin_lists_with_ethereum():
    assert all_coins() == sorted([*coins, 'ETH', 'TETH'])
    assert {'ETH', 'TETH'} <= set(all_coins_with_api())
    assert {'ETH', 'TETH'} <= set(coins_with_slip44())
    assert 'ETH' not in coins_with_api()  # coins with unspent outputs, e.g. for Sweep
    assert {'ETH', 'TETH'} <= set(scannable_coins())
    assert is_testnet('TETH') and not is_testnet('ETH')


def test_format_coin_amount():
    assert format_coin_amount('BTC', 150000000) == '1.50000000'
    assert format_coin_amount('ETH', 10**18 + 5) == '1.000000000000000005'
    assert format_coin_amount('TETH', 0) == '0'


def test_address_type_name_of_ethereum():
    assert address_type_name('ethereum') == 'Ethereum'
    assert address_type_name('p2wpkh') == 'Native SegWit (p2wpkh)'


def test_key_entry_address():
    assert key_entry_address('ETH', '0x' + ETH_KEY, 'ethereum') == ETH_KEY_ADDRESS
    with pytest.raises(ValueError, match='64 hexadecimal digits'):
        key_entry_address('ETH', 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn', 'ethereum')


def test_add_private_key():
    wallet = Wallet.create(' '.join(['abandon'] * 11 + ['about']), '')

    eth = add_private_key(wallet, 'Eth', 'ETH', ETH_KEY, 'ethereum')
    btc = add_private_key(
        wallet, 'Btc', 'BTC', 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn', 'p2pkh'
    )

    assert eth.address == ETH_KEY_ADDRESS
    assert btc.address == '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'


def test_parse_ethereum_address():
    assert parse_address(' ' + ETH_KEY_ADDRESS.lower(), 'TETH') == ETH_KEY_ADDRESS
    with pytest.raises(ValueError, match='checksum'):
        parse_address(ETH_KEY_ADDRESS.replace('d', 'D', 1), 'ETH')


@http_mock.activate
def test_fetch_balances_of_ethereum_addresses():
    http_mock.add(http_mock.POST, ETH_NODE, json={'jsonrpc': '2.0', 'id': 1, 'result': hex(10**18)})

    balances = fetch_balances(
        [make_address('e', coin='ETH', address_type='ethereum', address=ETH_KEY_ADDRESS)]
    )

    assert balances == {'e': 10**18}


def test_parse_ether_amount():
    assert parse_ether_amount(' 0,5 ') == 5 * 10**17
    for text, message in (('0', 'greater than zero'), ('abc', 'not a number'), ('', 'Enter')):
        with pytest.raises(ValueError, match=message):
            parse_ether_amount(text)


def test_parse_gwei_field():
    assert parse_gwei_field('', 'Max fee') is None
    assert parse_gwei_field('1,5', 'Max fee') == 15 * 10**8
    with pytest.raises(ValueError, match='Max fee: abc is not a number'):
        parse_gwei_field('abc', 'Max fee')


def test_parse_rpc_nodes():
    assert parse_rpc_nodes('') == []
    assert parse_rpc_nodes('http://localhost:8545, https://node.example') == [
        'http://localhost:8545',
        'https://node.example',
    ]
    with pytest.raises(ValueError, match='must start with http'):
        parse_rpc_nodes('localhost:8545')


def make_prepared(max_fee_per_gas=22 * GWEI, value=10**17):
    transaction = Transaction(
        chain_id=11155111,
        nonce=3,
        max_priority_fee_per_gas=2 * GWEI,
        max_fee_per_gas=max_fee_per_gas,
        gas_limit=21000,
        to='0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed',
        value=value,
    )
    return PreparedEthereumTransaction(
        transaction,
        transaction.sign(1),
        '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf',
        10**18,
        FeeSuggestion(10 * GWEI, 2 * GWEI),
    )


def test_describe_ethereum_transaction():
    rows = describe_ethereum_transaction(make_prepared(), 'TETH', 'public nodes')

    assert rows == [
        ('From', '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'),
        ('To', '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed'),
        ('Amount', '0.1 TETH'),
        ('Nonce', '3'),
        ('Gas limit', '21000'),
        ('Max fee per gas', '22 gwei'),
        ('Priority fee per gas', '2 gwei'),
        ('Max fee', '0.000462 TETH'),
        ('Balance after', 'at least 0.899538 TETH'),
        ('Broadcast', 'public nodes'),
    ]


def test_describe_ethereum_transaction_with_warning():
    rows = describe_ethereum_transaction(make_prepared(max_fee_per_gas=5 * GWEI), 'ETH', 'own node')

    assert rows[-1] == (
        'Warning',
        'Max fee per gas 5 gwei is lower than the base fee 10 gwei of the next block, '
        'the transaction will wait until the base fee drops',
    )


KEY_1_WIF = 'KwDiBf89QgGbjEhKnhXJuH7LrciVrZi3qYjgd9M7rFU73sVHnoWn'


def test_translated_key_addresses_to_ethereum():
    key, addresses = translated_key_addresses(KEY_1_WIF, 'ETH')

    assert key == '0x' + '00' * 31 + '01'
    assert addresses == [('ethereum', '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf')]


def test_translated_private_key():
    assert translated_private_key(KEY_1_WIF, 'TETH') == '0x' + '00' * 31 + '01'
    assert translated_private_key(KEY_1_WIF, 'LTC').startswith('T')


def test_source_wif_of_ethereum_address():
    wallet = Wallet.create(' '.join(['abandon'] * 11 + ['about']), '')
    address = wallet.add_ethereum_key('Key', 'ETH', '00' * 31 + '01')

    assert source_wif(wallet, address) == KEY_1_WIF


@http_mock.activate
def test_fetch_balances_skips_coin_after_connection_error():
    api_url = get_api(coins['BTC']).base_url
    ltc = [make_address(name, coin='LTC', address=f'ltc-{name}') for name in 'ab']
    http_mock.add(http_mock.GET, f'{api_url}/address/{SEGWIT_ADDRESS}/utxo', json=[])

    # no response for LTC, http_mock refuses the connection like an unavailable API
    balances = fetch_balances(ltc + [make_address('c')])

    assert (
        balances['a']
        == balances['b']
        == (
            'error: <urlopen error Connection refused by http_mock: '
            'https://litecoinspace.org/api/address/ltc-a/utxo>'
        )
    )
    assert balances['c'] == 0
    requested = [call.request.url for call in http_mock.calls]
    assert not any('ltc-b' in url for url in requested)


@http_mock.activate
def test_fetch_balances_skips_ethereum_coin_when_no_node_responds():
    addresses = [
        make_address(name, coin='ETH', address_type='ethereum', address=ETH_KEY_ADDRESS)
        for name in 'ab'
    ]

    balances = fetch_balances(addresses)

    assert balances['a'] == balances['b']
    assert balances['a'].startswith('error: No Ethereum node responded')
    assert len(http_mock.calls) == len(ethereum_coins['ETH']['rpcs'])
