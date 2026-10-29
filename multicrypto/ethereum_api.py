"""Communication with Ethereum nodes and block explorers.

Nodes are used through JSON-RPC (https://ethereum.org/developers/docs/apis/json-rpc/): public
nodes from the coin definition or own node (e.g. geth, reth or nethermind on
http://localhost:8545). Requests go to the first node which responds, so an unavailable or rate
limited node is skipped. Blockscout explorer gives the number of transactions of an address,
which nodes don't have (the nonce counts only sent transactions).
"""

import json
import logging
import time
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from multicrypto.api import DEFAULT_TIMEOUT, InsufficientFundsError, check_response, http_request
from multicrypto.ethereum import (
    SignedTransaction,
    Transaction,
    format_ether,
    format_gwei,
    private_key_to_address,
    validate_address,
)

logger = logging.getLogger(__name__)

Coin = Dict[str, Any]

# Errors of overloaded nodes (EIP-1474: limit exceeded, internal error, and too many requests used
# by some providers), other nodes are tried
TRANSIENT_ERROR_CODES = (-32005, -32029, -32603)
TRANSIENT_ERROR_MESSAGES = ('rate limit', 'too many requests')
NOT_FOUND = 404  # HTTP status of addresses unknown to the explorer
FEE_HISTORY_BLOCKS = 10
FEE_PERCENTILE = 50
MIN_PRIORITY_FEE = 10**7  # 0.01 gwei, some recent blocks can have only transactions without tip
# Max fee per gas above this multiple of the suggested one is probably a mistake
HIGH_FEE_RATIO = 10
RECEIPT_POLL_INTERVAL = 4  # in seconds, blocks are produced every 12 seconds


class RpcError(ValueError):
    """Error returned by the node for the request, e.g. rejected transaction."""

    def __init__(self, code: Optional[int], message: str):
        super().__init__(f'Node error {code}: {message}')
        self.code = code
        self.message = message


class NodeUnavailableError(ValueError):
    """None of the nodes responded to the request."""


class EthereumRPC:
    """JSON-RPC client sending requests to the first node which responds."""

    def __init__(self, urls: Sequence[str], timeout: float = DEFAULT_TIMEOUT):
        if not urls:
            raise ValueError('No Ethereum node has been given')
        self.urls = list(urls)
        self.timeout = timeout

    def call(self, method: str, *params: Any) -> Any:
        request = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': list(params)}
        errors = []
        for url in self.urls:
            try:
                response = http_request(url, self.timeout, json_data=request)
            except (urllib.error.URLError, OSError) as error:
                errors.append(f'{url}: {error}')
                continue
            if not response.ok:
                errors.append(f'{url}: HTTP {response.status} {response.text[:200]}')
                continue
            try:
                data = response.json()
            except json.JSONDecodeError:
                errors.append(f'{url}: response is not JSON {response.text[:200]}')
                continue
            if not isinstance(data, dict) or ('result' not in data and 'error' not in data):
                errors.append(f'{url}: incorrect JSON-RPC response {response.text[:200]}')
                continue
            error = data.get('error')
            if error:
                code, message = error.get('code'), str(error.get('message', ''))
                if code in TRANSIENT_ERROR_CODES or any(
                    text in message.lower() for text in TRANSIENT_ERROR_MESSAGES
                ):
                    errors.append(f'{url}: {message}')
                    continue
                raise RpcError(code, message)
            return data['result']
        raise NodeUnavailableError(f'No Ethereum node responded to {method}: {"; ".join(errors)}')

    def chain_id(self) -> int:
        return int(self.call('eth_chainId'), 16)

    def get_balance(self, address: str) -> int:
        """Balance in wei."""
        return int(self.call('eth_getBalance', address, 'latest'), 16)

    def get_nonce(self, address: str) -> int:
        """Number of transactions sent from the address, including pending ones, which is
        the nonce of the next transaction."""
        return int(self.call('eth_getTransactionCount', address, 'pending'), 16)

    def estimate_gas(self, sender: str, to: str, value: int, data: bytes = b'') -> int:
        transaction = {'from': sender, 'to': to, 'value': hex(value)}
        if data:
            transaction['data'] = '0x' + data.hex()
        return int(self.call('eth_estimateGas', transaction), 16)

    def fee_history(self, blocks: int, percentiles: List[int]) -> Dict[str, Any]:
        return self.call('eth_feeHistory', hex(blocks), 'latest', percentiles)

    def send_raw_transaction(self, raw_transaction: str) -> str:
        """Send the signed transaction in hex (with 0x), return its hash."""
        return self.call('eth_sendRawTransaction', raw_transaction)

    def get_receipt(self, transaction_hash: str) -> Optional['Receipt']:
        """Receipt of the mined transaction, None when it is not mined yet."""
        receipt = self.call('eth_getTransactionReceipt', transaction_hash)
        if not receipt:
            return None
        return Receipt(
            transaction_hash=receipt['transactionHash'],
            success=int(receipt['status'], 16) == 1,
            block_number=int(receipt['blockNumber'], 16),
            gas_used=int(receipt['gasUsed'], 16),
            effective_gas_price=int(receipt['effectiveGasPrice'], 16),
        )


@dataclass(frozen=True)
class Receipt:
    """Result of the mined transaction, a failed transaction (reverted) pays the fee too."""

    transaction_hash: str
    success: bool
    block_number: int
    gas_used: int
    effective_gas_price: int  # base fee of the block plus the paid priority fee

    @property
    def fee(self) -> int:
        return self.gas_used * self.effective_gas_price


def get_rpc(coin: Coin, nodes: Optional[Sequence[str]] = None, timeout=DEFAULT_TIMEOUT):
    """Client for the given node URLs or for the public nodes of the coin."""
    return EthereumRPC(nodes or coin['rpcs'], timeout)


class BlockscoutAPI:
    """HTTP client for the API v2 of Blockscout explorer, which doesn't require a key."""

    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def _get(self, path: str) -> Any:
        response = http_request(f'{self.base_url}/{path}', self.timeout)
        return check_response(response, self.base_url).json()

    def get_tx_count(self, address: str) -> int:
        """Number of transactions sent and received by the address. The counters of Blockscout
        are cached (they were not updated hours after new transactions of an address), so
        the first page of transactions gives the number when there are no more pages."""
        page = self._get(f'addresses/{address}/transactions')
        if page.get('next_page_params') is None:
            return len(page['items'])
        counters = self._get(f'addresses/{address}/counters')
        return max(int(counters['transactions_count']), len(page['items']))

    def get_usage(self, address: str) -> int:
        """Number of transactions of the address plus 1 when it has ether or tokens, 0 for
        unused addresses (also unknown to the explorer). The balance and the tokens find
        addresses which received ether only by internal transactions (e.g. from contracts) or
        received only tokens, they have no transactions in the list."""
        response = http_request(f'{self.base_url}/addresses/{address}', self.timeout)
        if response.status == NOT_FOUND:
            return 0
        info = check_response(response, self.base_url).json()
        holds = (
            int(info.get('coin_balance') or 0) > 0
            or bool(info.get('has_token_transfers'))
            or bool(info.get('has_tokens'))
        )
        return self.get_tx_count(address) + int(holds)


def get_explorer(coin: Coin, timeout: float = DEFAULT_TIMEOUT) -> BlockscoutAPI:
    return BlockscoutAPI(coin['explorers'][0]['url'], timeout)


@dataclass(frozen=True)
class FeeSuggestion:
    """Fees per gas in wei, max fee covers doubling of the base fee in the next blocks."""

    base_fee_per_gas: int
    max_priority_fee_per_gas: int

    @property
    def max_fee_per_gas(self) -> int:
        return 2 * self.base_fee_per_gas + self.max_priority_fee_per_gas


def suggest_fees(rpc: EthereumRPC) -> FeeSuggestion:
    """Base fee of the next block and the median priority fee paid in the recent blocks."""
    history = rpc.fee_history(FEE_HISTORY_BLOCKS, [FEE_PERCENTILE])
    # the list has also the base fee of the block after the newest one
    base_fee = int(history['baseFeePerGas'][-1], 16)
    tips = sorted(int(rewards[0], 16) for rewards in history.get('reward') or [] if rewards)
    tip = tips[len(tips) // 2] if tips else MIN_PRIORITY_FEE
    return FeeSuggestion(base_fee, max(tip, MIN_PRIORITY_FEE))


def _resolve_fees(
    suggestion: FeeSuggestion,
    max_priority_fee_per_gas: Optional[int],
    max_fee_per_gas: Optional[int],
):
    """Fees per gas: the given ones, missing ones from the suggestion (the priority fee is not
    above the given max fee)."""
    if max_priority_fee_per_gas is None:
        max_priority_fee_per_gas = suggestion.max_priority_fee_per_gas
        if max_fee_per_gas is not None:
            max_priority_fee_per_gas = min(max_priority_fee_per_gas, max_fee_per_gas)
    if max_fee_per_gas is None:
        max_fee_per_gas = 2 * suggestion.base_fee_per_gas + max_priority_fee_per_gas
    return max_priority_fee_per_gas, max_fee_per_gas


@dataclass(frozen=True)
class PreparedEthereumTransaction:
    """Signed transaction which can be shown for confirmation before broadcasting."""

    transaction: Transaction
    signed: SignedTransaction
    sender: str
    balance: int
    fee_suggestion: FeeSuggestion

    @property
    def max_total(self) -> int:
        return self.transaction.value + self.transaction.max_fee

    def fee_warnings(self) -> List[str]:
        """Warnings about fees which are probably mistakes, to show before sending."""
        transaction = self.transaction
        suggestion = self.fee_suggestion
        warnings = []
        if transaction.max_fee_per_gas < suggestion.base_fee_per_gas:
            warnings.append(
                f'Max fee per gas {format_gwei(transaction.max_fee_per_gas)} gwei is lower than '
                f'the base fee {format_gwei(suggestion.base_fee_per_gas)} gwei of the next block, '
                'the transaction will wait until the base fee drops'
            )
        if transaction.max_fee_per_gas > HIGH_FEE_RATIO * suggestion.max_fee_per_gas:
            warnings.append(
                f'Max fee per gas {format_gwei(transaction.max_fee_per_gas)} gwei is more than '
                f'{HIGH_FEE_RATIO} times the suggested '
                f'{format_gwei(suggestion.max_fee_per_gas)} gwei'
            )
        if 0 < transaction.value < transaction.max_fee:
            warnings.append(
                f'Max fee {format_ether(transaction.max_fee)} is higher than the sent value '
                f'{format_ether(transaction.value)}'
            )
        return warnings


def prepare_transfer(
    coin: Coin,
    rpc: EthereumRPC,
    private_key: int,
    destination: str,
    value: int,
    nonce: Optional[int] = None,
    gas_limit: Optional[int] = None,
    max_priority_fee_per_gas: Optional[int] = None,
    max_fee_per_gas: Optional[int] = None,
) -> PreparedEthereumTransaction:
    """Sign the transfer of value wei from the address of the private key. Missing parameters are
    taken from the node: the nonce of the next transaction, the estimated gas and the fees."""
    destination = validate_address(destination)
    chain_id = rpc.chain_id()
    if chain_id != coin['chain_id']:
        raise ValueError(
            f'Node is on the chain {chain_id}, but {coin["name"]} has chain id {coin["chain_id"]}'
        )
    sender = private_key_to_address(private_key)
    balance = rpc.get_balance(sender)
    if balance < value:
        raise InsufficientFundsError(
            f'Balance {format_ether(balance)} of {sender} is lower than {format_ether(value)}'
        )
    if nonce is None:
        nonce = rpc.get_nonce(sender)
    if gas_limit is None:
        gas_limit = rpc.estimate_gas(sender, destination, value)
    suggestion = suggest_fees(rpc)
    max_priority_fee_per_gas, max_fee_per_gas = _resolve_fees(
        suggestion, max_priority_fee_per_gas, max_fee_per_gas
    )
    transaction = Transaction(
        chain_id=chain_id,
        nonce=nonce,
        max_priority_fee_per_gas=max_priority_fee_per_gas,
        max_fee_per_gas=max_fee_per_gas,
        gas_limit=gas_limit,
        to=destination,
        value=value,
    )
    if balance < transaction.value + transaction.max_fee:
        raise InsufficientFundsError(
            f'Balance {format_ether(balance)} of {sender} does not cover '
            f'{format_ether(value)} and the max fee {format_ether(transaction.max_fee)}'
        )
    signed = transaction.sign(private_key)
    return PreparedEthereumTransaction(transaction, signed, sender, balance, suggestion)


def broadcast_transaction(rpc: EthereumRPC, prepared: PreparedEthereumTransaction) -> str:
    """Send the transaction to the node, return its hash. A node which already has
    the transaction (e.g. sent before by another node) is not an error."""
    try:
        return rpc.send_raw_transaction(prepared.signed.raw_hex)
    except RpcError as error:
        if 'already known' in error.message.lower():
            return prepared.signed.hash
        raise


def wait_for_receipt(
    rpc: EthereumRPC,
    transaction_hash: str,
    timeout: float,
    interval: float = RECEIPT_POLL_INTERVAL,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> Optional[Receipt]:
    """Receipt of the transaction when it is mined before the timeout (in seconds), else None."""
    deadline = clock() + timeout
    while True:
        receipt = rpc.get_receipt(transaction_hash)
        if receipt is not None or clock() >= deadline:
            return receipt
        sleep(min(interval, max(0.0, deadline - clock())))


@dataclass(frozen=True)
class MaxValue:
    """The most wei which can be sent with the fees, the fees are used for the transaction."""

    value: int
    max_priority_fee_per_gas: int
    max_fee_per_gas: int


def max_value(
    rpc: EthereumRPC,
    sender: str,
    destination: str,
    max_priority_fee_per_gas: Optional[int] = None,
    max_fee_per_gas: Optional[int] = None,
) -> MaxValue:
    """The balance minus the max fee of the transfer to the destination. Gas is estimated with
    1 wei, because creating an account by sending ether costs more gas than a transfer without
    value. The unused part of the max fee stays on the address."""
    destination = validate_address(destination)
    balance = rpc.get_balance(sender)
    gas_limit = rpc.estimate_gas(sender, destination, 1)
    max_priority_fee_per_gas, max_fee_per_gas = _resolve_fees(
        suggest_fees(rpc), max_priority_fee_per_gas, max_fee_per_gas
    )
    max_fee = gas_limit * max_fee_per_gas
    if balance <= max_fee:
        raise InsufficientFundsError(
            f'Balance {format_ether(balance)} of {sender} does not cover the max fee '
            f'{format_ether(max_fee)}'
        )
    return MaxValue(balance - max_fee, max_priority_fee_per_gas, max_fee_per_gas)
