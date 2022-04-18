from datetime import date, timedelta

import requests


class API:
    @classmethod
    def get_current_definition(cls, coin):
        index = coin.get('current_api_index', 0)
        api_definition = coin['apis'][index]
        return api_definition

    @classmethod
    def send_raw_transaction(cls, coin, raw_transaction):
        api = cls.get_current_definition(coin)
        send_url = f'{api["url"]}/tx/send'
        result = requests.post(send_url, json={'rawtx': raw_transaction})
        return result.text

    @classmethod
    def get_utxo(cls, coin, address):
        api = cls.get_current_definition(coin)
        address_url = f'{api["url"]}/addr/{address}/utxo'
        result = requests.get(address_url)
        return result.json()

    @classmethod
    def get_history_block(cls, coin):
        api = cls.get_current_definition(coin)
        yesterday = date.today() - timedelta(days=1)
        blocks_url = f'{api["url"]}/blocks?limit=1&blockDate={yesterday.strftime("%Y-%m-%d")}'
        result = requests.get(blocks_url)
        history_block = result.json()['blocks'][0]
        return history_block
