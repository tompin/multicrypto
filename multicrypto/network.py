import logging
import requests

from multicrypto.address import get_private_key_from_wif_format, convert_private_key_to_address
from multicrypto.transaction import Transaction
from multicrypto.utils import reverse_byte_hex


logger = logging.getLogger(__name__)


def send(coin, wif_private_keys, destination_address, satoshis, fee, minimum_input_threshold=None,
         maximum_input_threshold=None):
    source_data = []
    for wif_private_key in wif_private_keys:
        private_key, compressed = get_private_key_from_wif_format(wif_private_key)
        source_address = convert_private_key_to_address(
            private_key, coin['address_prefix_bytes'], compressed)
        source_data.append((private_key, source_address))
    api = coin['api'][0]
    inputs = []
    input_satoshis = 0
    for private_key, source_address in source_data:
        address_url = api['utxo'].format(source_address)
        result = requests.get(address_url)
        unspents = result.json()
        for utxo in unspents:
            if minimum_input_threshold and utxo['satoshis'] < minimum_input_threshold:
                continue
            if maximum_input_threshold and utxo['satoshis'] > maximum_input_threshold:
                continue
            input_satoshis += utxo['satoshis']
            inputs.append(
                {'transaction_id': reverse_byte_hex(utxo['txid']),
                 'output_index': utxo['vout'],
                 'script': utxo['scriptPubKey'],
                 'satoshis': utxo['satoshis'],
                 'private_key': private_key})
            logger.info('Using address: {}, input: {}, satoshis: {}'.format(
                source_address, utxo['txid'], utxo['satoshis']))
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
                return result.json()
    else:
        raise Exception('Not enough funds in addresses: {}\nSum of inputs {} < {} + {}(fee)'.format(
            ', '.join(source_address for private_key, source_address in source_data),
            input_satoshis, satoshis, fee))
