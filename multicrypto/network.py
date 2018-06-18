import logging
import requests

from multicrypto.address import get_private_key_from_wif_format, convert_private_key_to_address
from multicrypto.transaction import Transaction
from multicrypto.utils import reverse_byte_hex


logger = logging.getLogger(__name__)


def get_utxo_from_address(coin, address, minimum_input_threshold=None, maximum_input_threshold=None,
                          limit_inputs=None):
    api = coin['api'][0]
    utxos = []
    counter_inputs = 0
    address_url = api['utxo'].format(address)
    result = requests.get(address_url)
    unspents = result.json()
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


def get_utxo_from_private_keys(coin, wif_private_keys, minimum_input_threshold=None,
                               maximum_input_threshold=None, limit_inputs=None):
    for wif_private_key in set(wif_private_keys):
        private_key, compressed = get_private_key_from_wif_format(wif_private_key)
        source_address = convert_private_key_to_address(
            private_key, coin['address_prefix_bytes'], compressed)
        utxos = get_utxo_from_address(
            coin, source_address, minimum_input_threshold, maximum_input_threshold, limit_inputs)
        for utxo in utxos:
            yield private_key, source_address, utxo


def send(coin, wif_private_keys, destination_address, satoshis, fee, minimum_input_threshold=None,
         maximum_input_threshold=None, limit_inputs=None):
    api = coin['api'][0]
    inputs = []
    input_satoshis = 0
    counter_inputs = 0
    for private_key, source_address, utxo in get_utxo_from_private_keys(
            coin, wif_private_keys, minimum_input_threshold, maximum_input_threshold, limit_inputs):
        input_satoshis += utxo['satoshis']
        inputs.append(
            {'transaction_id': reverse_byte_hex(utxo['txid']),
             'output_index': utxo['vout'],
             'script': utxo['scriptPubKey'],
             'satoshis': utxo['satoshis'],
             'private_key': private_key})
        counter_inputs += 1
        logger.info('{}. address: {}, input: {}, satoshis: {}'.format(
            counter_inputs, source_address, utxo['txid'], utxo['satoshis']))
        if input_satoshis >= satoshis + fee:
            outputs = [{'address': destination_address, 'satoshis': satoshis}]
            change = input_satoshis - satoshis - fee
            if change > 0:
                outputs.append({'address': source_address, 'satoshis': change})
            last_block = {}
            if 'check_block_at_height' in coin.get('params', {}):
                result = requests.get(api['blocks'])
                last_block = result.json()['blocks'][0]
            transaction = Transaction(coin, inputs, outputs, check_block_at_height=last_block)
            raw_transaction = transaction.create()
            result = requests.post(api['send'], json={'rawtx': raw_transaction})
            return result.text
    else:
        raise Exception('Not enough funds in addresses.\nSum of inputs {} < {} + {}(fee)'.format(
            input_satoshis, satoshis, fee))
