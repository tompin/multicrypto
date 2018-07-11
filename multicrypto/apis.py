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
        send_url = '{}/tx/send'.format(api['url'])
        result = requests.post(send_url, json={'rawtx': raw_transaction})
        return result.text

    @classmethod
    def get_utxo(cls, coin, address):
        api = cls.get_current_definition(coin)
        address_url = '{}/addr/{}/utxo'.format(api['url'], address)
        result = requests.get(address_url)
        return result.json()

    @classmethod
    def get_last_block(cls, coin):
        api = cls.get_current_definition(coin)
        blocks_url = '{}/blocks?limit=1'.format(api['url'])
        result = requests.get(blocks_url)
        last_block = result.json()['blocks'][0]
        return last_block
