import itertools
import logging

from multicrypto.address import get_private_key_from_wif_format, convert_private_key_to_address
from multicrypto.apis import API
from multicrypto.transaction import Transaction
from multicrypto.utils import reverse_byte_hex

logger = logging.getLogger(__name__)


def get_utxo_from_address(coin, address, minimum_input_threshold=None, maximum_input_threshold=None,
                          limit_inputs=None):
    utxos = []
    counter_inputs = 0
    unspents = API.get_utxo(coin, address)
    for utxo in unspents:
        if limit_inputs and counter_inputs == limit_inputs:
            break
        if minimum_input_threshold and utxo['satoshis'] < minimum_input_threshold:
            continue
        if maximum_input_threshold and utxo['satoshis'] > maximum_input_threshold:
            continue
        utxos.append(utxo)
        counter_inputs += 1
    return utxos


def get_utxo_from_addresses(coin, addresses, unlocking_scripts, minimum_input_threshold,
                            maximum_input_threshold, limit_inputs):
    for address, unlocking_script in zip(addresses, unlocking_scripts):
        utxos = get_utxo_from_address(
            coin, address, minimum_input_threshold, maximum_input_threshold, limit_inputs)
        for utxo in utxos:
            utxo['source_address'] = address
            utxo['unlocking_script'] = unlocking_script
            yield utxo


def get_utxo_from_private_keys(coin, wif_private_keys, is_script=False,
                               minimum_input_threshold=None,
                               maximum_input_threshold=None, limit_inputs=None):
    for wif_private_key in set(wif_private_keys):
        private_key, compressed = get_private_key_from_wif_format(wif_private_key)
        if is_script:
            prefix_bytes = coin['script_prefix_bytes']
        else:
            prefix_bytes = coin['address_prefix_bytes']
        source_address = convert_private_key_to_address(
            private_key, prefix_bytes, compressed, is_script)
        utxos = get_utxo_from_address(
            coin, source_address, minimum_input_threshold, maximum_input_threshold, limit_inputs)
        for utxo in utxos:
            utxo['private_key'] = private_key
            utxo['source_address'] = source_address
            yield utxo


def send_inputs(coin, inputs, destination_address, source_address, input_satoshis, satoshis, fee):
    outputs = [{'address': destination_address, 'satoshis': satoshis}]
    change = input_satoshis - satoshis - fee
    if change > 0:
        outputs.append({'address': source_address, 'satoshis': change})
    last_block = {}
    if 'check_block_at_height' in coin.get('params', {}):
        last_block = API.get_last_block(coin)
    transaction = Transaction(coin, inputs, outputs, check_block_at_height=last_block)
    raw_transaction = transaction.create()
    result = API.send_raw_transaction(coin, raw_transaction)
    return result


def send_from_private_keys(
        coin, wif_private_keys, input_addresses, unlocking_scripts, destination_address, satoshis, fee,
        minimum_input_threshold=None, maximum_input_threshold=None, limit_inputs=None):
    if not input_addresses and not wif_private_keys:
        raise Exception('Missing required parameters input_addresses or wif_private_keys')
    utxos = None
    if input_addresses:
        utxos = get_utxo_from_addresses(
            coin, input_addresses, unlocking_scripts, minimum_input_threshold,
            maximum_input_threshold, limit_inputs)
    if wif_private_keys:
        wif_private_keys_utxos = get_utxo_from_private_keys(
            coin, wif_private_keys, False, minimum_input_threshold, maximum_input_threshold,
            limit_inputs)
        if utxos:
            utxos = itertools.chain(utxos, wif_private_keys_utxos)
        else:
            utxos = wif_private_keys_utxos
    return send_utxos(coin, utxos, destination_address, satoshis, fee)


def send_utxos(coin, utxos, destination_address, satoshis, fee):
    inputs = []
    input_satoshis = 0
    counter_inputs = 0
    for utxo in utxos:
        if not utxo:
            continue
        input_satoshis += utxo['satoshis']
        inputs.append({
            'transaction_id': reverse_byte_hex(utxo['txid']),
            'output_index': utxo['vout'],
            'locking_script': utxo['scriptPubKey'],
            'satoshis': utxo['satoshis'],
            'private_key': utxo.get('private_key'),
            'unlocking_script': utxo.get('unlocking_script', '')})
        counter_inputs += 1
        logger.debug('{}. address: {}, input: {}, satoshis: {}'.format(
            counter_inputs, utxo['source_address'], utxo['txid'], utxo['satoshis']))
        if input_satoshis >= satoshis + fee:
            return send_inputs(coin, inputs, destination_address, utxo['source_address'],
                               input_satoshis, satoshis, fee)
    else:
        raise Exception(
            'Not enough funds in addresses.\nSum of inputs is {} which is less than {} ({} + {})'.
            format(input_satoshis, satoshis + fee, satoshis, fee)
        )
