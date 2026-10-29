"""Communication with Ethereum nodes and block explorers.

Nodes are used through JSON-RPC (https://ethereum.org/developers/docs/apis/json-rpc/): public
nodes from the coin definition or own node (e.g. geth, reth or nethermind on
http://localhost:8545). Requests go to the first node which responds, so an unavailable or rate
limited node is skipped. Blockscout explorer gives the number of transactions of an address,
which nodes don't have (the nonce counts only sent transactions).
"""

import json
import logging
import urllib.error
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from multicrypto.api import DEFAULT_TIMEOUT, InsufficientFundsError, check_response, http_request
from multicrypto.ethereum import (
    SignedTransaction,
    Transaction,
    format_ether,
    private_key_to_address,
    validate_address,
)

logger = logging.getLogger(__name__)

Coin = Dict[str, Any]

# Errors of overloaded nodes (EIP-1474: limit exceeded, internal error, and too many requests used
# by some providers), other nodes are tried
TRANSIENT_ERROR_CODES = (-32005, -32029, -32603)
TRANSIENT_ERROR_MESSAGES = ('rate limit', 'too many requests')
FEE_HISTORY_BLOCKS = 10
FEE_PERCENTILE = 50
MIN_PRIORITY_FEE = 10**7  # 0.01 gwei, some recent blocks can have only transactions without tip


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


def get_rpc(coin: Coin, nodes: Optional[Sequence[str]] = None, timeout=DEFAULT_TIMEOUT):
    """Client for the given node URLs or for the public nodes of the coin."""
    return EthereumRPC(nodes or coin['rpcs'], timeout)


class BlockscoutAPI:
    """HTTP client for the API v2 of Blockscout explorer, which doesn't require a key."""

    def __init__(self, base_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout

    def get_tx_count(self, address: str) -> int:
        """Number of transactions sent and received by the address."""
        response = http_request(f'{self.base_url}/addresses/{address}/counters', self.timeout)
        return int(check_response(response, self.base_url).json()['transactions_count'])


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


@dataclass(frozen=True)
class PreparedEthereumTransaction:
    """Signed transaction which can be shown for confirmation before broadcasting."""

    transaction: Transaction
    signed: SignedTransaction
    sender: str
    balance: int

    @property
    def max_total(self) -> int:
        return self.transaction.value + self.transaction.max_fee


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
    if max_priority_fee_per_gas is None or max_fee_per_gas is None:
        suggestion = suggest_fees(rpc)
        if max_priority_fee_per_gas is None:
            max_priority_fee_per_gas = suggestion.max_priority_fee_per_gas
            if max_fee_per_gas is not None:
                max_priority_fee_per_gas = min(max_priority_fee_per_gas, max_fee_per_gas)
        if max_fee_per_gas is None:
            max_fee_per_gas = 2 * suggestion.base_fee_per_gas + max_priority_fee_per_gas
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
    return PreparedEthereumTransaction(transaction, transaction.sign(private_key), sender, balance)


def broadcast_transaction(rpc: EthereumRPC, prepared: PreparedEthereumTransaction) -> str:
    """Send the transaction to the node, return its hash. A node which already has
    the transaction (e.g. sent before by another node) is not an error."""
    try:
        return rpc.send_raw_transaction(prepared.signed.raw_hex)
    except RpcError as error:
        if 'already known' in error.message.lower():
            return prepared.signed.hash
        raise
