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


def test_discover_scans_account_groups():
    wallet = Wallet.create(MNEMONIC, '')
    used = used_addresses(
        wallet,
        [
            ('BTC', 'p2tr', 0, RECEIVE_CHAIN, 0),
            ('BTC', 'p2wpkh', 1, RECEIVE_CHAIN, 0),
            ('BTC', 'p2wpkh', 1, RECEIVE_CHAIN, 1),
            ('BTC', 'p2pkh', 3, RECEIVE_CHAIN, 0),  # after the unused group 2, it is not found
        ],
    )
    checked = []

    found = discover(
        wallet, 'BTC', checked.append, lambda: False, tx_count=lambda address: int(address in used)
    )

    assert found == [
        DiscoveredAccount('BTC', 'p2tr', 0, [0], []),
        DiscoveredAccount('BTC', 'p2wpkh', 1, [0, 1], []),
    ]
    # group 0: p2tr 1 + 20 receiving and 20 change, 3 unused accounts (40 each), group 1: p2wpkh
    # 2 + 20 and 20, 3 unused accounts, group 2: 4 unused accounts
    assert sum(checked) == (41 + 120) + (42 + 120) + 160


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
        DiscoveredAccount('BTC', 'p2tr', 1, [0], []),
    ]

    # p2wpkh 0/1 and 1/0, p2pkh 1/2 and the addresses 0/0 of four accounts of the new group 1
    assert add_discovered(wallet, discovered) == 7
    assert add_discovered(wallet, discovered) == 0
    assert [address.path for address in wallet.account_addresses(existing)] == [
        "m/84'/0'/0'/0/0",
        "m/84'/0'/0'/0/1",
        "m/84'/0'/0'/1/0",
    ]
    group = wallet.get_group('BTC', 0)
    assert [(account.label, account.address_type) for account in group.accounts] == [
        ('Savings', 'p2wpkh'),
        ('Savings', 'p2pkh'),
    ]
    assert [address.label for address in wallet.account_addresses(group.accounts[1])] == [
        'Change 2'
    ]
    new_group = wallet.get_group('BTC', 1)
    assert new_group.label == 'Bitcoin #1'
    assert [len(account.addresses) for account in new_group.accounts] == [1, 1, 1, 1]


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
    used = used_addresses(wallet, [('BTC', 'p2wpkh', 0, RECEIVE_CHAIN, 0)])
    p2sh_address = wallet.address_at(HDAccount('', 'BTC', 'p2sh-p2wpkh', 0), RECEIVE_CHAIN, 0)
    found = []

    def tx_count(address):
        if address == p2sh_address:
            raise ValueError('API error: broken')
        return int(address in used)

    with pytest.raises(ValueError, match='broken'):
        discover(wallet, 'BTC', lambda count: None, lambda: False, tx_count, found=found)

    assert found == [DiscoveredAccount('BTC', 'p2wpkh', 0, [0], [])]


def test_discover_ethereum_scans_only_receiving_chain():
    wallet = Wallet.create(MNEMONIC, '')
    used = used_addresses(
        wallet,
        [('ETH', 'ethereum', 0, RECEIVE_CHAIN, 3), ('ETH', 'ethereum', 1, RECEIVE_CHAIN, 0)],
    )
    checked = []

    found = discover(
        wallet, 'ETH', checked.append, lambda: False, tx_count=lambda address: int(address in used)
    )

    assert found == [
        DiscoveredAccount('ETH', 'ethereum', 0, [3], []),
        DiscoveredAccount('ETH', 'ethereum', 1, [0], []),
    ]
    assert sum(checked) == 24 + 21 + 20  # accounts 0, 1 and unused 2, no change chains


def test_discover_ethereum_uses_explorer(monkeypatch):
    explorers = []

    def ethereum_usage(coin):
        explorers.append(coin['chain_id'])
        return lambda address: 0

    monkeypatch.setattr(discovery, 'ethereum_usage', ethereum_usage)

    assert discover(Wallet.create(MNEMONIC, ''), 'TETH', lambda count: None, lambda: False) == []
    assert explorers == [11155111]


def test_add_discovered_ethereum_account():
    wallet = Wallet.create(MNEMONIC, '')

    added = add_discovered(wallet, [DiscoveredAccount('ETH', 'ethereum', 0, [0, 2], [])])

    assert added == 2  # the address 0 of the new group and the address 2
    [account] = wallet.get_group('ETH', 0).accounts
    assert [address.index for address in wallet.account_addresses(account)] == [0, 2]
