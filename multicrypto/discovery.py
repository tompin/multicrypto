"""Discovery of used accounts and addresses of the HD wallet (BIP-44 account discovery)."""

import itertools
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from multicrypto.api import RateLimitError, get_api
from multicrypto.coins import coins, get_address_types
from multicrypto.wallet import CHANGE_CHAIN, RECEIVE_CHAIN, HDAccount, Wallet

GAP_LIMIT = 20  # unused addresses after the last used one ending the scan of the chain
THREADS = 2
# seconds of waiting before the next attempt of the request rejected because of the rate limit
RATE_LIMIT_DELAYS = (1, 2, 4, 8, 16, 32, 60)
# seconds between the requests of all threads, public APIs throttle faster requests
REQUEST_INTERVAL = 0.25
MAX_ACCOUNTS = 100
MAX_ADDRESSES = 10000


class Cancelled(Exception):
    """Raised when the discovery has been cancelled."""


@dataclass
class DiscoveredAccount:
    coin: str
    address_type: str
    account: int
    receive: List[int] = field(default_factory=list)
    change: List[int] = field(default_factory=list)


class Pacer:
    """Spaces the calls of wait() from all threads by the interval."""

    def __init__(self, interval: float):
        self.interval = interval
        self.lock = threading.Lock()
        self.next_time = 0.0

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            delay = self.next_time - now
            self.next_time = max(now, self.next_time) + self.interval
        if delay > 0:
            time.sleep(delay)


def coin_tx_count(coin) -> Callable[[str], int]:
    """Transaction count of the address, the requests are spread over all APIs of the coin."""
    clients = itertools.cycle(
        [get_api({**coin, 'current_api_index': index}) for index in range(len(coin['apis']))]
    )
    lock = threading.Lock()
    pacer = Pacer(REQUEST_INTERVAL)

    def tx_count(address: str) -> int:
        with lock:
            client = next(clients)
        pacer.wait()
        return client.get_tx_count(address)

    return tx_count


def _retrying(
    tx_count: Callable[[str], int], cancelled: Callable[[], bool]
) -> Callable[[str], int]:
    """Repeat the requests rejected because of the API rate limit or failed because of the
    connection after increasing delays."""

    def count(address: str) -> int:
        for delay in RATE_LIMIT_DELAYS:
            try:
                return tx_count(address)
            except (RateLimitError, OSError):
                if cancelled():
                    raise Cancelled() from None
                time.sleep(delay)
        return tx_count(address)

    return count


def scan_chain(
    address_at: Callable[[int], str],
    tx_count: Callable[[str], int],
    progress: Callable[[int], None],
    cancelled: Callable[[], bool],
    mapper: Callable = map,
) -> List[int]:
    """Indexes of the used addresses of the chain. Windows of addresses are checked (with the
    mapper, e.g. map of the thread pool) until GAP_LIMIT addresses after the last used one are
    unused."""
    used: List[int] = []
    start = 0
    end = GAP_LIMIT
    while start < end:
        if cancelled():
            raise Cancelled()
        if end > MAX_ADDRESSES:
            raise ValueError(f'Stopped after {MAX_ADDRESSES} addresses of the chain')
        indexes = range(start, end)
        addresses = [address_at(index) for index in indexes]
        counts = list(mapper(tx_count, addresses))
        progress(len(indexes))
        used.extend(index for index, count in zip(indexes, counts, strict=True) if count)
        start, end = end, (used[-1] + 1 if used else 0) + GAP_LIMIT
    return used


def discover(
    wallet: Wallet,
    coin_symbol: str,
    progress: Callable[[int], None],
    cancelled: Callable[[], bool],
    tx_count: Optional[Callable[[str], int]] = None,
) -> List[DiscoveredAccount]:
    """Used accounts of all address types of the coin: accounts are checked from 0 to the first
    one without transactions on the receiving and change chains."""
    coin = coins[coin_symbol]
    if 'slip44' not in coin or not coin.get('apis'):
        raise ValueError(f'{coin_symbol} cannot be scanned, it has no SLIP-44 coin type or API')
    if tx_count is None:
        tx_count = coin_tx_count(coin)
    tx_count = _retrying(tx_count, cancelled)
    found = []
    with ThreadPoolExecutor(THREADS) as executor:
        for address_type in get_address_types(coin):
            for number in range(MAX_ACCOUNTS + 1):
                if number == MAX_ACCOUNTS:
                    raise ValueError(
                        f'Stopped after {MAX_ACCOUNTS} accounts of {coin_symbol} {address_type}'
                    )
                account = HDAccount('', coin_symbol, address_type, number)
                chains = [
                    scan_chain(
                        lambda index, account=account, chain=chain: wallet.address_at(
                            account, chain, index
                        ),
                        tx_count,
                        progress,
                        cancelled,
                        executor.map,
                    )
                    for chain in (RECEIVE_CHAIN, CHANGE_CHAIN)
                ]
                if not any(chains):
                    break
                found.append(DiscoveredAccount(coin_symbol, address_type, number, *chains))
    return found


def add_discovered(wallet: Wallet, discovered: List[DiscoveredAccount]) -> int:
    """Add the discovered accounts and addresses missing in the wallet, return the number of the
    added addresses."""
    added = 0
    for item in discovered:
        account = next(
            (
                account
                for account in wallet.accounts
                if (account.coin, account.address_type, account.account)
                == (item.coin, item.address_type, item.account)
            ),
            None,
        )
        if account is None:
            account = wallet.add_account(
                f'{item.coin} {item.address_type} #{item.account}',
                item.coin,
                item.address_type,
                item.account,
            )
        present = {(address.chain, address.index) for address in account.addresses}
        for chain, indexes in ((RECEIVE_CHAIN, item.receive), (CHANGE_CHAIN, item.change)):
            for index in indexes:
                if (chain, index) not in present:
                    wallet.add_address(account.id, chain, index)
                    added += 1
    return added
