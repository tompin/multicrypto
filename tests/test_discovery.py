import pytest

import multicrypto.discovery as discovery
from multicrypto.discovery import (
    Cancelled,
    DiscoveredAccount,
    add_discovered,
    discover,
    scan_chain,
)
from multicrypto.api import RateLimitError
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
