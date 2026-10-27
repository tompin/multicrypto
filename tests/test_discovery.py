import pytest
from tests import http_mock

import multicrypto.discovery as discovery
from multicrypto.discovery import (
    Cancelled,
    DiscoveredAccount,
    add_discovered,
    discover,
    scan_account,
    scan_chain,
)
from multicrypto.api import RateLimitError
from multicrypto.coins import coins
from multicrypto.wallet import CHANGE_CHAIN, RECEIVE_CHAIN, HDAccount, Wallet

MNEMONIC = ' '.join(['abandon'] * 11 + ['about'])


def scan(used, **kwargs):
    checked = []
    indexes = scan_chain(
        str, lambda address: int(int(address) in used), checked.append, lambda: False, **kwargs
    )
    return indexes, sum(checked)


def test_scan_chain_continues_after_gap_shorter_than_limit():
    assert scan({0, 5, 24}) == ([0, 5, 24], 45)


def test_scan_chain_stops_after_gap_limit():
    assert scan({0, 21}) == ([0], 21)
    assert scan(set()) == ([], 20)


def test_scan_chain_limit(monkeypatch):
    monkeypatch.setattr(discovery, 'MAX_ADDRESSES', 30)

    with pytest.raises(ValueError, match='Stopped after 30 addresses'):
        scan(set(range(100)))


def test_scan_chain_cancelled():
    with pytest.raises(Cancelled):
        scan_chain(str, lambda address: 0, lambda count: None, lambda: True)


def used_addresses(wallet, items):
    return {
        wallet.address_at(HDAccount('', coin, address_type, number), chain, index)
        for coin, address_type, number, chain, index in items
    }


def test_discover_accounts_of_all_address_types():
    wallet = Wallet.create(MNEMONIC, '')
    used = used_addresses(
        wallet,
        [
            ('BTC', 'p2wpkh', 0, RECEIVE_CHAIN, 0),
            ('BTC', 'p2wpkh', 0, RECEIVE_CHAIN, 1),
            ('BTC', 'p2wpkh', 0, CHANGE_CHAIN, 0),
            ('BTC', 'p2wpkh', 1, RECEIVE_CHAIN, 3),
            ('BTC', 'p2pkh', 0, CHANGE_CHAIN, 2),
        ],
    )
    checked = []

    found = discover(
        wallet, 'BTC', checked.append, lambda: False, tx_count=lambda address: int(address in used)
    )

    assert found == [
        DiscoveredAccount('BTC', 'p2pkh', 0, [], [2]),
        DiscoveredAccount('BTC', 'p2wpkh', 0, [0, 1], [0]),
        DiscoveredAccount('BTC', 'p2wpkh', 1, [3], []),
    ]
    # p2pkh: account 0 (20 receiving, 2 + 1 + 20 change) and 1 (40), p2sh-p2wpkh: 0 (40),
    # p2wpkh: 0 (1 + 1 + 20 receiving, 21 change), 1 (3 + 1 + 20, 20) and 2 (40), p2tr: 0 (40)
    assert sum(checked) == 290


def test_discover_coin_without_api():
    with pytest.raises(ValueError, match='DOGE cannot be scanned'):
        discover(Wallet.create(MNEMONIC, ''), 'DOGE', lambda count: None, lambda: False)


def test_add_discovered():
    wallet = Wallet.create(MNEMONIC, '')
    existing = wallet.add_account('Savings', 'BTC', 'p2wpkh')
    wallet.new_address(existing.id)
    discovered = [
        DiscoveredAccount('BTC', 'p2wpkh', 0, [0, 1], [0]),
        DiscoveredAccount('BTC', 'p2pkh', 0, [], [2]),
    ]

    assert add_discovered(wallet, discovered) == 3
    assert add_discovered(wallet, discovered) == 0
    assert [address.path for address in wallet.account_addresses(existing)] == [
        "m/84'/0'/0'/0/0",
        "m/84'/0'/0'/0/1",
        "m/84'/0'/0'/1/0",
    ]
    added = wallet.accounts[1]
    assert (added.label, added.coin, added.address_type, added.account) == (
        'BTC p2pkh #0',
        'BTC',
        'p2pkh',
        0,
    )
    assert [address.label for address in wallet.account_addresses(added)] == ['Change 2']


def test_discover_retries_rate_limited_requests(monkeypatch):
    delays = []
    monkeypatch.setattr(discovery.time, 'sleep', delays.append)
    failures = iter([RateLimitError('429'), RateLimitError('429')])

    def tx_count(address):
        error = next(failures, None)
        if error:
            raise error
        return 0

    found = discover(
        Wallet.create(MNEMONIC, ''), 'TBTC', lambda count: None, lambda: False, tx_count
    )

    assert found == []
    assert delays == [1, 2]


def test_discover_cancelled_while_rate_limited(monkeypatch):
    monkeypatch.setattr(discovery.time, 'sleep', lambda seconds: None)
    cancelled = iter([False, True])

    def tx_count(address):
        raise RateLimitError('429')

    with pytest.raises(Cancelled):
        discover(
            Wallet.create(MNEMONIC, ''),
            'TBTC',
            lambda count: None,
            lambda: next(cancelled, True),
            tx_count,
        )


def test_discover_retries_connection_errors(monkeypatch):
    delays = []
    monkeypatch.setattr(discovery.time, 'sleep', delays.append)
    failures = iter([ConnectionResetError('Remote end closed connection without response')])

    def tx_count(address):
        error = next(failures, None)
        if error:
            raise error
        return 0

    assert (
        discover(Wallet.create(MNEMONIC, ''), 'TBTC', lambda n: None, lambda: False, tx_count) == []
    )
    assert delays == [1]


@http_mock.activate
def test_requests_are_spread_over_apis_of_the_coin(monkeypatch):
    monkeypatch.setattr(discovery, 'REQUEST_INTERVAL', 0)
    address = 'tb1qmck8k945kxnskh9a7jugz8lf9ed6u80zcgqsgs'
    for api in coins['TBTC']['apis']:
        http_mock.add(
            http_mock.GET,
            f'{api["url"]}/address/{address}',
            json={'chain_stats': {'tx_count': 1}, 'mempool_stats': {'tx_count': 0}},
        )
    tx_count = discovery.coin_tx_count(coins['TBTC'])

    assert [tx_count(address) for _ in range(4)] == [1, 1, 1, 1]
    urls = [call.request.url for call in http_mock.calls]
    assert [url.split('/address/')[0] for url in urls] == [
        api['url'] for api in coins['TBTC']['apis']
    ] * 2


def test_pacer_spaces_requests(monkeypatch):
    now = [100.0]
    delays = []
    monkeypatch.setattr(discovery.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(discovery.time, 'sleep', delays.append)
    pacer = discovery.Pacer(0.25)

    for _ in range(3):
        pacer.wait()

    assert delays == [0.25, 0.5]


def test_scan_account():
    wallet = Wallet.create(MNEMONIC, '')
    account = wallet.add_account('Savings', 'BTC', 'p2wpkh')
    used = used_addresses(
        wallet,
        [('BTC', 'p2wpkh', 0, RECEIVE_CHAIN, 2), ('BTC', 'p2wpkh', 0, CHANGE_CHAIN, 0)],
    )
    checked = []

    found = scan_account(
        wallet, account, checked.append, lambda: False, lambda address: int(address in used)
    )

    assert found == DiscoveredAccount('BTC', 'p2wpkh', 0, [2], [0])
    assert sum(checked) == (2 + 1 + 20) + (0 + 1 + 20)


def test_discover_keeps_accounts_found_before_error():
    wallet = Wallet.create(MNEMONIC, '')
    used = used_addresses(wallet, [('BTC', 'p2pkh', 0, RECEIVE_CHAIN, 0)])
    p2sh_address = wallet.address_at(HDAccount('', 'BTC', 'p2sh-p2wpkh', 0), RECEIVE_CHAIN, 0)
    found = []

    def tx_count(address):
        if address == p2sh_address:
            raise ValueError('API error: broken')
        return int(address in used)

    with pytest.raises(ValueError, match='broken'):
        discover(wallet, 'BTC', lambda count: None, lambda: False, tx_count, found=found)

    assert found == [DiscoveredAccount('BTC', 'p2pkh', 0, [0], [])]
