"""Communication with block explorer APIs.

The module consists of two layers:

* thin HTTP clients for the block explorer configured for a coin: :class:`InsightAPI` and
  :class:`EsploraAPI` (mempool.space, blockstream.info), selected by the ``type`` of the API
  definition (``insight`` by default) using :func:`get_api`,
* UTXO helpers which collect unspent outputs, build transactions and broadcast them
  using the client.
"""

import itertools
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

from multicrypto.address import convert_private_key_to_coin_address, get_private_key_from_wif_format
from multicrypto.coins import P2PKH
from multicrypto.scripts import address_to_script, get_dust_threshold
from multicrypto.transaction import Transaction
from multicrypto.utils import reverse_byte_hex

logger = logging.getLogger(__name__)

Coin = Dict[str, Any]
Utxo = Dict[str, Any]
Broadcast = Callable[[str], str]

DEFAULT_TIMEOUT = 30  # in seconds
# Some APIs behind Cloudflare reject the default Python-urllib user agent
USER_AGENT = 'multicrypto'


class InsufficientFundsError(Exception):
    """Raised when the sum of available inputs does not cover the amount and the fee."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    text: str

    @property
    def ok(self) -> bool:
        return self.status < 400

    def json(self) -> Any:
        return json.loads(self.text)


def http_request(
    url: str,
    timeout: float,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[str] = None,
    json_data: Any = None,
) -> HttpResponse:
    """Send GET request, or POST request when data or json_data is given.

    Unlike urlopen, HTTP error statuses don't raise exceptions, they are returned in the response.
    """
    if params:
        url = f'{url}?{urllib.parse.urlencode(params)}'
    headers = {'User-Agent': USER_AGENT}
    if json_data is not None:
        data = json.dumps(json_data)
        headers['Content-Type'] = 'application/json'
    elif data is not None:
        headers['Content-Type'] = 'text/plain'
    body = data.encode() if data is not None else None
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, response.read().decode())
    except urllib.error.HTTPError as error:
        with error:
            return HttpResponse(error.code, error.read().decode())


class InsightAPI:
    """HTTP client for the Insight API selected in the coin definition."""

    def __init__(self, coin: Coin, timeout: float = DEFAULT_TIMEOUT):
        definition = coin['apis'][coin.get('current_api_index', 0)]
        self.base_url = definition['url']
        self.timeout = timeout

    def get_utxo(self, address: str) -> List[Utxo]:
        response = http_request(f'{self.base_url}/addr/{address}/utxo', timeout=self.timeout)
        return response.json()

    def send_raw_transaction(self, raw_transaction: str) -> str:
        response = http_request(
            f'{self.base_url}/tx/send', json_data={'rawtx': raw_transaction}, timeout=self.timeout
        )
        return response.text

    def get_history_block(self) -> Dict[str, Any]:
        """Return the first block mined yesterday, required by coins with replay protection."""
        yesterday = date.today() - timedelta(days=1)
        response = http_request(
            f'{self.base_url}/blocks',
            params={'limit': 1, 'blockDate': yesterday.isoformat()},
            timeout=self.timeout,
        )
        return response.json()['blocks'][0]


class EsploraAPI:
    """HTTP client for the Esplora API (e.g. mempool.space, blockstream.info) selected in the
    coin definition. Responses are converted to the Insight API format."""

    def __init__(self, coin: Coin, timeout: float = DEFAULT_TIMEOUT):
        definition = coin['apis'][coin.get('current_api_index', 0)]
        self.coin = coin
        self.base_url = definition['url']
        self.timeout = timeout

    def _get(self, path: str) -> HttpResponse:
        response = http_request(f'{self.base_url}/{path}', timeout=self.timeout)
        if not response.ok:
            raise ValueError(f'API error: {response.text}')
        return response

    def get_utxo(self, address: str) -> List[Utxo]:
        esplora_utxos = self._get(f'address/{address}/utxo').json()
        # Esplora doesn't return locking script, but it is the same for all outputs of an address
        script = address_to_script(address, self.coin).hex()
        tip_height = None
        if any(utxo['status']['confirmed'] for utxo in esplora_utxos):
            tip_height = int(self._get('blocks/tip/height').text)
        utxos = []
        for utxo in esplora_utxos:
            height = utxo['status'].get('block_height')
            utxos.append(
                {
                    'address': address,
                    'txid': utxo['txid'],
                    'vout': utxo['vout'],
                    'scriptPubKey': script,
                    'satoshis': utxo['value'],
                    'amount': utxo['value'] / 10**8,
                    'height': height,
                    'confirmations': tip_height - height + 1 if height else 0,
                }
            )
        return utxos

    def send_raw_transaction(self, raw_transaction: str) -> str:
        response = http_request(f'{self.base_url}/tx', data=raw_transaction, timeout=self.timeout)
        if not response.ok:
            raise ValueError(f'Transaction rejected: {response.text}')
        return json.dumps({'txid': response.text})


API_CLIENTS = {'insight': InsightAPI, 'esplora': EsploraAPI}


def get_api(coin: Coin, timeout: float = DEFAULT_TIMEOUT):
    """Return client for the API selected in the coin definition."""
    definition = coin['apis'][coin.get('current_api_index', 0)]
    return API_CLIENTS[definition.get('type', 'insight')](coin, timeout)


def get_utxo_from_address(
    coin: Coin,
    address: str,
    minimum_input_threshold: Optional[int] = None,
    maximum_input_threshold: Optional[int] = None,
    limit_inputs: Optional[int] = None,
) -> List[Utxo]:
    utxos = []
    for utxo in get_api(coin).get_utxo(address):
        if limit_inputs and len(utxos) == limit_inputs:
            break
        if minimum_input_threshold and utxo['satoshis'] < minimum_input_threshold:
            continue
        if maximum_input_threshold and utxo['satoshis'] > maximum_input_threshold:
            continue
        utxos.append(utxo)
    return utxos


def get_utxo_from_addresses(
    coin: Coin,
    addresses: Iterable[str],
    unlocking_scripts: Iterable[str],
    minimum_input_threshold: Optional[int] = None,
    maximum_input_threshold: Optional[int] = None,
    limit_inputs: Optional[int] = None,
) -> Iterator[Utxo]:
    for address, unlocking_script in zip(addresses, unlocking_scripts, strict=True):
        utxos = get_utxo_from_address(
            coin, address, minimum_input_threshold, maximum_input_threshold, limit_inputs
        )
        for utxo in utxos:
            utxo['source_address'] = address
            utxo['unlocking_script'] = unlocking_script
            yield utxo


def get_utxo_from_private_keys(
    coin: Coin,
    wif_private_keys: Iterable[str],
    address_type: str = P2PKH,
    minimum_input_threshold: Optional[int] = None,
    maximum_input_threshold: Optional[int] = None,
    limit_inputs: Optional[int] = None,
) -> Iterator[Utxo]:
    """Collect UTXOs of addresses of the given type (one of ADDRESS_TYPES) for private keys."""
    for wif_private_key in set(wif_private_keys):
        private_key, compressed = get_private_key_from_wif_format(wif_private_key)
        source_address = convert_private_key_to_coin_address(
            private_key, coin, compressed, address_type
        )
        utxos = get_utxo_from_address(
            coin, source_address, minimum_input_threshold, maximum_input_threshold, limit_inputs
        )
        for utxo in utxos:
            utxo['private_key'] = private_key
            utxo['source_address'] = source_address
            yield utxo


@dataclass(frozen=True)
class PreparedTransaction:
    """Signed transaction which has not been broadcast yet.

    :param inputs: Transaction inputs (including private keys used to sign them)
    :param outputs: Destination output and optional change output sent back to the source address
    :param change_added_to_fee: Change below the dust threshold, which was added to the fee
    """

    raw_transaction: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    input_satoshis: int
    fee: int
    change_added_to_fee: int = 0
    vsize: int = 0


def build_transaction(
    coin: Coin,
    inputs: List[Dict[str, Any]],
    destination_address: str,
    source_address: str,
    input_satoshis: int,
    satoshis: int,
    fee: int,
) -> PreparedTransaction:
    """Create signed transaction, the change is sent back to the source address."""
    outputs = [{'address': destination_address, 'satoshis': satoshis}]
    change = input_satoshis - satoshis - fee
    change_added_to_fee = 0
    dust_threshold = get_dust_threshold(address_to_script(source_address, coin))
    if change >= dust_threshold:
        outputs.append({'address': source_address, 'satoshis': change})
    elif change > 0:
        change_added_to_fee = change
        logger.info(
            'Change %s is below dust threshold %s and was added to the fee', change, dust_threshold
        )
    history_block = {}
    if 'check_block_at_height' in coin.get('params', {}):
        history_block = get_api(coin).get_history_block()
    transaction = Transaction(coin, inputs, outputs, check_block_at_height=history_block)
    return PreparedTransaction(
        transaction.create(),
        inputs,
        outputs,
        input_satoshis,
        fee,
        change_added_to_fee,
        transaction.vsize,
    )


def broadcast_prepared(
    coin: Coin, prepared: PreparedTransaction, broadcast: Optional[Broadcast] = None
) -> str:
    """Broadcast the prepared transaction.

    :param broadcast: Function sending raw transaction (hex) and returning the result, by default
                      the transaction is sent to the coin block explorer API
    """
    if broadcast is None:
        return get_api(coin).send_raw_transaction(prepared.raw_transaction)
    return broadcast(prepared.raw_transaction)


def prepare_from_private_keys(
    coin: Coin,
    wif_private_keys: Optional[List[str]],
    input_addresses: Optional[List[str]],
    unlocking_scripts: Optional[List[str]],
    destination_address: str,
    satoshis: int,
    fee: int,
    minimum_input_threshold: Optional[int] = None,
    maximum_input_threshold: Optional[int] = None,
    limit_inputs: Optional[int] = None,
    address_type: str = P2PKH,
) -> PreparedTransaction:
    if not input_addresses and not wif_private_keys:
        raise ValueError('Missing required parameters input_addresses or wif_private_keys')
    utxo_sources = []
    if input_addresses:
        utxo_sources.append(
            get_utxo_from_addresses(
                coin,
                input_addresses,
                unlocking_scripts,
                minimum_input_threshold,
                maximum_input_threshold,
                limit_inputs,
            )
        )
    if wif_private_keys:
        utxo_sources.append(
            get_utxo_from_private_keys(
                coin,
                wif_private_keys,
                address_type,
                minimum_input_threshold,
                maximum_input_threshold,
                limit_inputs,
            )
        )
    utxos = itertools.chain.from_iterable(utxo_sources)
    return prepare_utxos(coin, utxos, destination_address, satoshis, fee)


def send_from_private_keys(
    coin: Coin,
    wif_private_keys: Optional[List[str]],
    input_addresses: Optional[List[str]],
    unlocking_scripts: Optional[List[str]],
    destination_address: str,
    satoshis: int,
    fee: int,
    minimum_input_threshold: Optional[int] = None,
    maximum_input_threshold: Optional[int] = None,
    limit_inputs: Optional[int] = None,
    broadcast: Optional[Broadcast] = None,
    address_type: str = P2PKH,
) -> str:
    prepared = prepare_from_private_keys(
        coin,
        wif_private_keys,
        input_addresses,
        unlocking_scripts,
        destination_address,
        satoshis,
        fee,
        minimum_input_threshold,
        maximum_input_threshold,
        limit_inputs,
        address_type,
    )
    return broadcast_prepared(coin, prepared, broadcast)


def prepare_utxos(
    coin: Coin,
    utxos: Iterable[Utxo],
    destination_address: str,
    satoshis: int,
    fee: int,
) -> PreparedTransaction:
    inputs = []
    input_satoshis = 0
    for utxo in utxos:
        if not utxo:
            continue
        input_satoshis += utxo['satoshis']
        inputs.append(
            {
                'transaction_id': reverse_byte_hex(utxo['txid']),
                'output_index': utxo['vout'],
                'locking_script': utxo['scriptPubKey'],
                'satoshis': utxo['satoshis'],
                'private_key': utxo.get('private_key'),
                'unlocking_script': utxo.get('unlocking_script', ''),
            }
        )
        logger.debug(
            '%s. address: %s, input: %s, satoshis: %s',
            len(inputs),
            utxo['source_address'],
            utxo['txid'],
            utxo['satoshis'],
        )
        if input_satoshis >= satoshis + fee:
            return build_transaction(
                coin,
                inputs,
                destination_address,
                utxo['source_address'],
                input_satoshis,
                satoshis,
                fee,
            )
    raise InsufficientFundsError(
        f'Not enough funds in address(es).\n'
        f'Sum of inputs is {input_satoshis} which is less than '
        f'{satoshis + fee} ({satoshis} + {fee})'
    )


def send_utxos(
    coin: Coin,
    utxos: Iterable[Utxo],
    destination_address: str,
    satoshis: int,
    fee: int,
    broadcast: Optional[Broadcast] = None,
) -> str:
    prepared = prepare_utxos(coin, utxos, destination_address, satoshis, fee)
    return broadcast_prepared(coin, prepared, broadcast)


def prepare_sweep(
    coin: Coin,
    utxos: List[Utxo],
    destination_address: str,
    fee: int,
    batch_size: int,
) -> List[PreparedTransaction]:
    """Prepare transactions sending all inputs to the address without change, each transaction
    spends at most batch_size inputs and pays the fee. Nothing is prepared when any batch cannot
    be sent."""
    utxos = [utxo for utxo in utxos if utxo]
    if not utxos:
        raise ValueError('No inputs found for the private key')
    dust_threshold = get_dust_threshold(address_to_script(destination_address, coin))
    prepared = []
    for start in range(0, len(utxos), batch_size):
        batch = utxos[start : start + batch_size]
        satoshis = sum(utxo['satoshis'] for utxo in batch)
        if satoshis <= fee:
            raise ValueError(f'Fee {fee} is not smaller than sum of batch inputs {satoshis}')
        if satoshis - fee < dust_threshold:
            raise ValueError(
                f'Amount {satoshis - fee} of the batch is below the dust threshold {dust_threshold}'
            )
        prepared.append(prepare_utxos(coin, batch, destination_address, satoshis - fee, fee))
    return prepared
