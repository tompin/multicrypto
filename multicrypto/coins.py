coins = {
    '1337': {'name': 'elite', 'address_prefix_bytes': b'\x30', 'secret_prefix_bytes': b'\x80',
             'script_prefix_bytes': b'\x1c'},
    'BTC': {'name': 'bitcoin', 'address_prefix_bytes': b'\x00', 'secret_prefix_bytes': b'\x80',
            'script_prefix_bytes': b'\x05', 'api': [
                {'utxo': 'https://insight.bitpay.com/api/addr/{}/utxo',
                 'send': 'https://insight.bitpay.com/api/tx/send'}]
            },
    'BTG': {'name': 'bitcoin gold', 'address_prefix_bytes': b'\x26', 'secret_prefix_bytes': b'\x80',
            'script_prefix_bytes': b'\x17', 'sig_hash': b'\x41', 'api': [
                {'utxo': 'https://explorer.bitcoingold.org/insight-api/addr/{}/utxo',
                 'send': 'https://explorer.bitcoingold.org/insight-api/tx/send'}]
            },
    'BITS': {'name': 'bitstar', 'address_prefix_bytes': b'\x19', 'secret_prefix_bytes': b'\x99',
             'script_prefix_bytes': b'\x08'},
    'BTCH': {'name': 'bitcoin hush', 'address_prefix_bytes': b'\x3c',
             'secret_prefix_bytes': b'\xbc', 'script_prefix_bytes': b'\x55'},
    'BTCP': {'name': 'bitcoin private', 'address_prefix_bytes': b'\x13\x25',
             'secret_prefix_bytes': b'\x80', 'script_prefix_bytes': b'\x13\xaf',
             'sig_hash': b'\x41', 'api': [
                 {'utxo': 'https://explorer.btcprivate.org/api/addr/{}/utxo',
                  'send': 'https://explorer.btcprivate.org/api/tx/send'}]
             },
    'BTCZ': {'name': 'bitcoinz', 'address_prefix_bytes': b'\x1c\xb8',
             'secret_prefix_bytes': b'\x80', 'script_prefix_bytes': b'\x1c\xbd', 'api': [
                 {'utxo': 'https://explorer.btcz.rocks/api/addr/{}/utxo',
                  'send': 'https://explorer.btcz.rocks/api/tx/send'}]
             },
    'BUCK': {'name': 'buck', 'address_prefix_bytes': b'\x1c\xb8',
             'secret_prefix_bytes': b'\x80', 'script_prefix_bytes': b'\x1c\xbd'},
    'CRAVE': {'name': 'crave', 'address_prefix_bytes': b'\x46', 'secret_prefix_bytes': b'\x99',
              'script_prefix_bytes': b'\x55'},
    'DASH': {'name': 'dash', 'address_prefix_bytes': b'\x4c', 'secret_prefix_bytes': b'\xcc',
             'script_prefix_bytes': b'\x10'},
    'DOGE': {'name': 'dogecoin', 'address_prefix_bytes': b'\x1e', 'secret_prefix_bytes': b'\x9e',
             'script_prefix_bytes': b'\x16'},
    'DMD': {'name': 'diamond', 'address_prefix_bytes': b'\x5a', 'secret_prefix_bytes': b'\xda',
            'script_prefix_bytes': b'\x08'},
    'HUSH': {'name': 'hush', 'address_prefix_bytes': b'\x1c\xb8', 'secret_prefix_bytes': b'\x80',
             'script_prefix_bytes': b'\x1c\xbd', 'api': [
                 {'utxo': 'https://explorer.myhush.org/api/addr/{}/utxo',
                  'send': 'https://explorer.myhush.org/api/tx/send'}]
             },
    'KMD': {'name': 'komodo', 'address_prefix_bytes': b'\x3c', 'secret_prefix_bytes': b'\xbc',
            'script_prefix_bytes': b'\x55'},
    'LTC': {'name': 'litecoin', 'address_prefix_bytes': b'\x30', 'secret_prefix_bytes': b'\xb0',
            'script_prefix_bytes': b'\x05', 'api': [
                {'utxo': 'https://insight.litecore.io/api/addr/{}/utxo',
                 'send': 'https://insight.litecore.io/api/tx/send'}]
            },
    'LTZ': {'name': 'litecoinz', 'address_prefix_bytes': b'\x0a\xb3',
            'secret_prefix_bytes': b'\xb0', 'script_prefix_bytes': b'\x0a\xb8'},
    'MOON': {'name': 'mooncoin', 'address_prefix_bytes': b'\x03', 'secret_prefix_bytes': b'\x83',
             'script_prefix_bytes': b'\x32'},
    'QTUM': {'name': 'qtum', 'address_prefix_bytes': b'\x3a', 'secret_prefix_bytes': b'\x80',
             'script_prefix_bytes': b'\x32'},
    'SAFE': {'name': 'safecoin', 'address_prefix_bytes': b'\x3d', 'secret_prefix_bytes': b'\xbd',
             'script_prefix_bytes': b'\x56', 'api': [
                 {'utxo': 'https://explorer.safecoin.org/api/addr/{}/utxo',
                  'send': 'https://explorer.safecoin.org/api/tx/send'}]
             },
    'XSG': {'name': 'snowgem', 'address_prefix_bytes': b'\x1c\x28',
            'secret_prefix_bytes': b'\x80', 'script_prefix_bytes': b'\x1c\x2d', 'api': [
                {'utxo': 'https://insight.snowgem.org/api/addr/{}/utxo',
                 'send': 'https://insight.snowgem.org/api/tx/send'}]
            },
    'SIRX': {'name': 'sirius', 'address_prefix_bytes': b'\x3f', 'secret_prefix_bytes': b'\x80',
             'script_prefix_bytes': b'\x32'},
    'SMART': {'name': 'smartcash', 'address_prefix_bytes': b'\x3f', 'secret_prefix_bytes': b'\xbf',
              'script_prefix_bytes': b'\x12'},
    'UNIFY': {'name': 'unify', 'address_prefix_bytes': b'\x44', 'secret_prefix_bytes': b'\x80',
              'script_prefix_bytes': b'\x05'},
    'UNO': {'name': 'unobtanium', 'address_prefix_bytes': b'\x82', 'secret_prefix_bytes': b'\xe0',
            'script_prefix_bytes': b'\x1e'},
    'VOT': {'name': 'votecoin', 'address_prefix_bytes': b'\x1c\xb8', 'secret_prefix_bytes': b'\x80',
            'script_prefix_bytes': b'\x1c\xbd', 'api': [
                {'utxo': 'http://explorer.votecoin.site/insight-api-zcash/addr/{}/utxo',
                 'send': 'http://explorer.votecoin.site/insight-api-zcash/tx/send'}]
            },
    'VTC': {'name': 'vertcoin', 'address_prefix_bytes': b'\x47', 'secret_prefix_bytes': b'\x80',
            'script_prefix_bytes': b'\x05'},
    'ZEC': {'name': 'zcash', 'address_prefix_bytes': b'\x1c\xb8', 'secret_prefix_bytes': b'\x80',
            'script_prefix_bytes': b'\x1c\xbd', 'api': [
                {'utxo': 'https://zcash.blockexplorer.com/api/addr/{}/utxo',
                 'send': 'https://zcash.blockexplorer.com/api/tx/send'}]
            },
    'ZCL': {'name': 'zclassic', 'address_prefix_bytes': b'\x1c\xb8',
            'secret_prefix_bytes': b'\x80', 'script_prefix_bytes': b'\x1c\xbd', 'api': [
                {'utxo': 'http://explorer.zclmine.pro/insight-api-zcash/addr/{}/utxo',
                 'send': 'http://explorer.zclmine.pro/insight-api-zcash/tx/send'}]
            },
    'ZEIT': {'name': 'zeit', 'address_prefix_bytes': b'\x33', 'secret_prefix_bytes': b'\x80',
             'script_prefix_bytes': b'\x08'},
    'ZEN': {'name': 'zen cash', 'address_prefix_bytes': b'\x20\x89',
            'secret_prefix_bytes': b'\x80', 'script_prefix_bytes': b'\x1c\xbd',
            'params': {'check_block_at_height': True}, 'api': [
                {'utxo': 'https://explorer.zensystem.io/insight-api-zen/addr/{}/utxo',
                 'send': 'https://explorer.zensystem.io/insight-api-zen/tx/send',
                 'blocks': 'https://explorer.zensystem.io/insight-api-zen/blocks?limit=1'}]
            },
    'ZERO': {'name': 'zero', 'address_prefix_bytes': b'\x1c\xb8', 'secret_prefix_bytes': b'\x80',
             'script_prefix_bytes': b'\x1c\xbd', 'api': [
                 {'utxo': 'https://zero-insight.mining4.co.uk/insight-api-zcash/addr/{}/utxo',
                  'send': 'https://zero-insight.mining4.co.uk/insight-api-zcash/tx/send'}]
             },
    'ZOIN': {'name': 'zoin', 'address_prefix_bytes': b'\x50', 'secret_prefix_bytes': b'\xd0',
             'script_prefix_bytes': b'\x07'},
}


def validate_coin_symbol(coin_symbol):
    if coin_symbol not in coins:
        raise Exception('Coin {} is not supported'.format(coin_symbol))
    return True
