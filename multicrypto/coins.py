# Dictionary with coins definition with coin symbols as keys
coins = {
    'BTC': {
        'name': 'bitcoin',
        'address_prefix_bytes': b'\x00',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x05',
        'bech32_hrp': 'bc',
        'witness_version': 1,
        'apis': []
    },
    'BTG': {
        'name': 'bitcoin gold',
        'address_prefix_bytes': b'\x26',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x17',
        'sig_hash': b'\x41',
        'apis': [
            {'url': 'https://explorer.bitcoingold.org/insight-api'}
        ]
    },
    'BTCH': {
        'name': 'bitcoin hush',
        'address_prefix_bytes': b'\x00',
        'secret_prefix_bytes': b'\xbc',
        'script_prefix_bytes': b'\x05',
        'apis': [
            {'url': 'https://btch.explorer.dexstats.info/api'}
        ]
    },
    'BTCZ': {
        'name': 'bitcoinz',
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': [
            {'url': 'https://explorer.btcz.rocks/api'}
        ]
    },
    'DASH': {
        'name': 'dash',
        'address_prefix_bytes': b'\x4c',
        'secret_prefix_bytes': b'\xcc',
        'script_prefix_bytes': b'\x10',
        'apis': [
            {'url': 'https://insight.dash.org/api'}
        ]
    },
    'DOGE': {
        'name': 'dogecoin',
        'address_prefix_bytes': b'\x1e',
        'secret_prefix_bytes': b'\x9e',
        'script_prefix_bytes': b'\x16'
    },
    'LTC': {
        'name': 'litecoin',
        'address_prefix_bytes': b'\x30',
        'secret_prefix_bytes': b'\xb0',
        'script_prefix_bytes': b'\x05',
        'apis': [
            {'url': 'https://insight.litecore.io/api'}
        ]
    },
    'SAFE': {
        'name': 'safecoin',
        'address_prefix_bytes': b'\x3d',
        'secret_prefix_bytes': b'\xbd',
        'script_prefix_bytes': b'\x56',
        'apis': [
            {'url': 'https://explorer.safecoin.org/api'}
        ]
    },
    'TENT': {
        'name': 'TENT',
        'address_prefix_bytes': b'\x1c\x28',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\x2d',
        'apis': [
            {'url': 'https://explorer.tent.app/api'}
        ]
    },
    'SMART': {
        'name': 'smartcash',
        'address_prefix_bytes': b'\x3f',
        'secret_prefix_bytes': b'\xbf',
        'script_prefix_bytes': b'\x12'
    },
    'TBTC': {
        'name': 'bitcoin testnet',
        'address_prefix_bytes': b'\x6f',
        'secret_prefix_bytes': b'\xef',
        'script_prefix_bytes': b'\xc4',
        'bech32_hrp': 'tb',
        'apis': [
            {'url': 'https://test-insight.bitpay.com/api'}
        ]
    },
    'TBCH': {
        'name': 'bitcoin cash testnet',
        'address_prefix_bytes': b'\x6f',
        'secret_prefix_bytes': b'\xef',
        'script_prefix_bytes': b'\xc4',
        'apis': [
            {'url': 'https://test-insight.bitpay.com/api'}
        ]
    },
    'ZEC': {
        'name': 'zcash',
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': [
            {'url': 'https://explorer.zcashfr.io/api'}
        ]
    },
    'ZCL': {
        'name': 'zclassic',
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': []
    },
    'ZEIT': {
        'name': 'zeit',
        'address_prefix_bytes': b'\x33',
        'secret_prefix_bytes': b'\xb3',
        'script_prefix_bytes': b'\x08'
    },
    'ZEN': {
        'name': 'zen cash',
        'address_prefix_bytes': b'\x20\x89',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'params': {'check_block_at_height': True},
        'apis': [
            {'url': 'https://explorer.zensystem.io/insight-api-zen'}
        ]
    },
    'ZERO': {
        'name': 'zero',
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': [
            {'url': 'https://insight.zeromachine.io/insight-api-zero'},
        ]
    },
}
