"""Searching for vanity addresses, which start with the given pattern, in many processes."""

import multiprocessing
import os
import queue
from typing import Optional, Tuple

from multicrypto.address import (
    calculate_address,
    calculate_public_key_hash,
    convert_private_key_to_wif_format,
    get_address_range,
    validate_address_type,
    validate_pattern,
)
from multicrypto.bech32 import CHARSET, encode
from multicrypto.coins import P2PKH, P2SH_P2WPKH, P2WPKH, coins
from multicrypto.ellipticcurve import secp256k1

VANITY_ADDRESS_TYPES = (P2PKH, P2SH_P2WPKH, P2WPKH)
ATTEMPTS_PER_UPDATE = 1000


def _bech32_start(coin) -> str:
    return f'{coin["bech32_hrp"]}1q'


def _base58_range(coin_symbol: str, address_type: str):
    key = 'script_prefix_bytes' if address_type == P2SH_P2WPKH else 'address_prefix_bytes'
    return get_address_range(coins[coin_symbol][key])


def validate_vanity_pattern(pattern: str, coin_symbol: str, address_type: str) -> str:
    """Check that an address of the type can start with the pattern, return the pattern
    (lowercase for bech32 addresses)."""
    if address_type not in VANITY_ADDRESS_TYPES:
        raise ValueError(
            f'Vanity addresses of type {address_type} are not supported, '
            f'choose one of {", ".join(VANITY_ADDRESS_TYPES)}'
        )
    coin = coins[coin_symbol]
    validate_address_type(address_type, coin)
    if address_type != P2WPKH:
        validate_pattern(pattern, coin_symbol, address_type == P2SH_P2WPKH)
        return pattern
    pattern = pattern.lower()
    start = _bech32_start(coin)
    if not pattern.startswith(start):
        raise ValueError(f'Pattern must start with {start}')
    for character in pattern[len(start) :]:
        if character not in CHARSET:
            raise ValueError(
                f'Character {character} is not used in bech32 addresses '
                f'(the characters are {"".join(sorted(CHARSET))})'
            )
    return pattern


def expected_attempts(pattern: str, coin_symbol: str, address_type: str) -> int:
    """Average number of addresses checked before one starts with the pattern."""
    if address_type == P2WPKH:
        return 32 ** max(0, len(pattern) - len(_bech32_start(coins[coin_symbol])))
    fixed = len(os.path.commonprefix(_base58_range(coin_symbol, address_type)))
    return 58 ** max(0, len(pattern) - fixed)


def pattern_hint(coin_symbol: str, address_type: str) -> str:
    if address_type == P2WPKH:
        return f'Addresses start with {_bech32_start(coins[coin_symbol])}'
    start_address, end_address = _base58_range(coin_symbol, address_type)
    return f'Addresses are from {start_address[:4]}… to {end_address[:4]}…'


def _address_function(coin, address_type: str, compressed: bool):
    """Function calculating the address of the type from the public key (point)."""
    if address_type == P2WPKH:
        hrp = coin['bech32_hrp']
        return lambda point: encode(hrp, 0, calculate_public_key_hash(point))
    segwit = address_type == P2SH_P2WPKH
    prefix = coin['script_prefix_bytes' if segwit else 'address_prefix_bytes']
    return lambda point: calculate_address(
        calculate_public_key_hash(point, compressed, segwit), prefix
    )


def find_address(
    coin_symbol: str, address_type: str, pattern: str, compressed: bool, stop, attempts=None
) -> Optional[Tuple[str, str]]:
    """Check consecutive keys from a random one until the address starts with the pattern
    (return the address and WIF) or stop is set (return None). The attempts counter
    (multiprocessing.Value) is increased every ATTEMPTS_PER_UPDATE keys."""
    coin = coins[coin_symbol]
    address_of = _address_function(coin, address_type, compressed)
    seed = secp256k1.gen_private_key()
    point = seed * secp256k1.G
    counter = 0
    while True:
        address = address_of(point)
        if address.startswith(pattern):
            private_key = (seed + counter) % secp256k1.n
            wif = convert_private_key_to_wif_format(
                private_key, coin['secret_prefix_bytes'], compressed
            )
            return address, wif
        point += secp256k1.G
        counter += 1
        if counter % ATTEMPTS_PER_UPDATE == 0:
            if attempts is not None:
                with attempts.get_lock():
                    attempts.value += ATTEMPTS_PER_UPDATE
            if stop.is_set():
                return None


def search_worker(coin_symbol, address_type, pattern, compressed, stop, attempts, results):
    """Process searching for the address, the result is put into the results queue."""
    found = find_address(coin_symbol, address_type, pattern, compressed, stop, attempts)
    if found:
        results.put(found)
        stop.set()


class VanitySearch:
    """Search for the vanity address in processes. They are started with spawn, which is safe in
    programs with threads (e.g. Qt GUI), and the result is passed back in memory. Spawned processes
    import the main module again, so the program has to start in `if __name__ == '__main__':`."""

    def __init__(
        self,
        coin_symbol: str,
        address_type: str,
        pattern: str,
        workers: int,
        compressed: bool = True,
    ):
        if not compressed and address_type != P2PKH:
            raise ValueError('Segwit addresses require compressed public key')
        self.pattern = validate_vanity_pattern(pattern, coin_symbol, address_type)
        self.coin_symbol = coin_symbol
        self.address_type = address_type
        self.workers = workers
        self.compressed = compressed
        self._context = multiprocessing.get_context('spawn')
        self._stop = self._context.Event()
        self._attempts = self._context.Value('Q', 0)
        self._results = self._context.Queue()
        self._processes = []
        self._result = None

    def start(self) -> None:
        for _ in range(self.workers):
            process = self._context.Process(
                target=search_worker,
                args=(
                    self.coin_symbol,
                    self.address_type,
                    self.pattern,
                    self.compressed,
                    self._stop,
                    self._attempts,
                    self._results,
                ),
                daemon=True,
            )
            process.start()
            self._processes.append(process)

    @property
    def attempts(self) -> int:
        return self._attempts.value

    @property
    def running(self) -> bool:
        return any(process.is_alive() for process in self._processes)

    @property
    def failed(self) -> bool:
        """Some process ended with an error before the address was found or the search stopped."""
        return not self._stop.is_set() and any(
            process.exitcode not in (None, 0) for process in self._processes
        )

    def result(self) -> Optional[Tuple[str, str]]:
        """Found address and private key in WIF format or None, it does not block."""
        if self._result is None:
            try:
                self._result = self._results.get_nowait()
            except queue.Empty:
                pass
        return self._result

    def stop(self) -> None:
        self._stop.set()
        self.result()
        for process in self._processes:
            process.join(timeout=5)
            if process.is_alive():
                process.terminate()
                process.join()
        self.result()
