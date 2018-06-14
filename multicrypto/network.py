import logging
import requests

from multicrypto.address import get_private_key_from_wif_format, convert_private_key_to_address
from multicrypto.transaction import Transaction
from multicrypto.utils import reverse_byte_hex


logger = logging.getLogger(__name__)


def send(coin, wif_private_key, destination_address, satoshis, fee):
    private_key, compressed = get_private_key_from_wif_format(wif_private_key)
    source_addresss = convert_private_key_to_address(
        private_key, coin['address_prefix_bytes'], compressed)
    api = coin['api'][0]
    result = requests.get(api['utxo'].format(source_addresss))
    logger.debug(
        'HTTP GET {} status: {} data: {}'.format(api['utxo'], result.status_code, result.text))
    unspents = result.json()
    inputs = []
    input_satoshis = 0
    for utxo in unspents:
        input_satoshis += utxo['satoshis']
        inputs.append(
            {'transaction_id': reverse_byte_hex(utxo['txid']),
             'output_index': utxo['vout'],
             'script': utxo['scriptPubKey'],
             'satoshis': utxo['satoshis'],
             'private_key': private_key})
        if input_satoshis >= satoshis + fee:
            break
    else:
        raise Exception('Not enough funds in address: {}'.format(source_addresss))
    outputs = [{'address': destination_address, 'satoshis': satoshis}]
    change = input_satoshis - satoshis - fee
    if change > 0:
        outputs.append({'address': source_addresss, 'satoshis': change})
    transaction = Transaction(coin, inputs, outputs)
    raw_transaction = transaction.create()
    result = requests.post(api['send'], json={'rawtx': raw_transaction})
    return {'response status': result.status_code, 'data': result.json()}
