# Types of addresses which can be derived from a private key and spent
P2PKH = 'p2pkh'
P2SH_P2WPKH = 'p2sh-p2wpkh'  # segwit nested in P2SH, e.g. 3... for BTC
P2WPKH = 'p2wpkh'  # native segwit (bech32), e.g. bc1q... for BTC
P2TR = 'p2tr'  # taproot key path only (bech32m, BIP-86), e.g. bc1p... for BTC
ADDRESS_TYPES = (P2PKH, P2SH_P2WPKH, P2WPKH, P2TR)

# Dictionary with coins definition with coin symbols as keys. Optional 'address_types' lists
# supported address types (only P2PKH by default), P2WPKH and P2TR require also 'bech32_hrp'.
# Optional 'slip44' is the coin type from SLIP-44 used in BIP-44 derivation paths, coins without it
# support only imported private keys. Optional 'message_prefix' is the name used in signed messages
# (by default the capitalized name).
coins = {
    'BTC': {
        'name': 'bitcoin',
        'slip44': 0,
        'address_prefix_bytes': b'\x00',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x05',
        'bech32_hrp': 'bc',
        'address_types': (P2PKH, P2SH_P2WPKH, P2WPKH, P2TR),
        'apis': [
            {'url': 'https://mempool.space/api', 'type': 'esplora'},
            {'url': 'https://blockstream.info/api', 'type': 'esplora'},
        ],
        'network': {
            'magic': b'\xf9\xbe\xb4\xd9',
            'port': 8333,
            'protocol_version': 70016,
            'seeds': [
                'dnsseed.bluematt.me',
                'seed.bitcoin.jonasschnelli.ch',
                'seed.btc.petertodd.net',
                'seed.bitcoin.sprovoost.nl',
                'dnsseed.emzy.de',
                'seed.bitcoin.wiz.biz',
            ],
        },
    },
    'BTG': {
        'name': 'bitcoin gold',
        'message_prefix': 'Bitcoin Gold',
        'slip44': 156,
        'address_prefix_bytes': b'\x26',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x17',
        'sig_hash': b'\x41',
        'apis': [{'url': 'https://explorer.bitcoingold.org/insight-api'}],
        'network': {
            'magic': b'\xe1\x47\x6d\x44',
            'port': 8338,
            'protocol_version': 70016,
            'seeds': [
                'eu-dnsseed.bitcoingold-official.org',
                'dnsseed.btgofficial.org',
                'dnsseed.bitcoingold.dev',
                'dnsseed.4btg.org',
            ],
        },
    },
    'BTCH': {
        'name': 'bitcoin hush',
        'address_prefix_bytes': b'\x00',
        'secret_prefix_bytes': b'\xbc',
        'script_prefix_bytes': b'\x05',
        'apis': [{'url': 'https://btch.explorer.dexstats.info/api'}],
    },
    'BTCZ': {
        'name': 'bitcoinz',
        'slip44': 177,
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': [{'url': 'https://explorer.btcz.rocks/api'}],
    },
    'DASH': {
        'name': 'dash',
        'message_prefix': 'DarkCoin',
        'slip44': 5,
        'address_prefix_bytes': b'\x4c',
        'secret_prefix_bytes': b'\xcc',
        'script_prefix_bytes': b'\x10',
        'apis': [{'url': 'https://insight.dash.org/api'}],
        'network': {
            'magic': b'\xbf\x0c\x6b\xbd',
            'port': 9999,
            'protocol_version': 70240,
            'seeds': [
                'dnsseed.dash.org',
            ],
        },
    },
    'DOGE': {
        'name': 'dogecoin',
        'slip44': 3,
        'address_prefix_bytes': b'\x1e',
        'secret_prefix_bytes': b'\x9e',
        'script_prefix_bytes': b'\x16',
        'network': {
            'magic': b'\xc0\xc0\xc0\xc0',
            'port': 22556,
            'protocol_version': 70015,
            'seeds': [
                'seed.multidoge.org',
                'seed2.multidoge.org',
            ],
        },
    },
    'LTC': {
        'name': 'litecoin',
        'slip44': 2,
        'address_prefix_bytes': b'\x30',
        'secret_prefix_bytes': b'\xb0',
        'script_prefix_bytes': b'\x05',
        'bech32_hrp': 'ltc',
        'address_types': (P2PKH, P2SH_P2WPKH, P2WPKH, P2TR),
        'apis': [{'url': 'https://litecoinspace.org/api', 'type': 'esplora'}],
        'network': {
            'magic': b'\xfb\xc0\xb6\xdb',
            'port': 9333,
            'protocol_version': 70016,
            'seeds': [
                'seed-a.litecoin.loshan.co.uk',
                'dnsseed.thrasher.io',
                'dnsseed.litecointools.com',
                'dnsseed.ltcpool.org',
                'dnsseed.koin-project.com',
            ],
        },
    },
    'SAFE': {
        'name': 'safecoin',
        'slip44': 19165,
        'address_prefix_bytes': b'\x3d',
        'secret_prefix_bytes': b'\xbd',
        'script_prefix_bytes': b'\x56',
        'apis': [{'url': 'https://explorer.safecoin.org/api'}],
    },
    'TENT': {
        'name': 'TENT',
        'slip44': 410,
        'address_prefix_bytes': b'\x1c\x28',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\x2d',
        'apis': [{'url': 'https://explorer.tent.app/api'}],
    },
    'SMART': {
        'name': 'smartcash',
        'slip44': 224,
        'address_prefix_bytes': b'\x3f',
        'secret_prefix_bytes': b'\xbf',
        'script_prefix_bytes': b'\x12',
    },
    'TBTC': {
        'name': 'bitcoin testnet',
        'message_prefix': 'Bitcoin',
        'slip44': 1,
        'address_prefix_bytes': b'\x6f',
        'secret_prefix_bytes': b'\xef',
        'script_prefix_bytes': b'\xc4',
        'bech32_hrp': 'tb',
        'address_types': (P2PKH, P2SH_P2WPKH, P2WPKH, P2TR),
        'apis': [
            {'url': 'https://mempool.space/testnet/api', 'type': 'esplora'},
            {'url': 'https://blockstream.info/testnet/api', 'type': 'esplora'},
        ],
        'network': {
            'magic': b'\x0b\x11\x09\x07',
            'port': 18333,
            'protocol_version': 70016,
            'seeds': [
                'testnet-seed.bitcoin.jonasschnelli.ch',
                'seed.tbtc.petertodd.net',
                'testnet-seed.bluematt.me',
                'seed.testnet.achownodes.xyz',
            ],
        },
    },
    'TBCH': {
        'name': 'bitcoin cash testnet',
        'message_prefix': 'Bitcoin',
        'slip44': 1,
        'address_prefix_bytes': b'\x6f',
        'secret_prefix_bytes': b'\xef',
        'script_prefix_bytes': b'\xc4',
        'apis': [{'url': 'https://test-insight.bitpay.com/api'}],
    },
    'TLTC': {
        'name': 'litecoin testnet',
        'message_prefix': 'Litecoin',
        'slip44': 1,
        'address_prefix_bytes': b'\x6f',
        'secret_prefix_bytes': b'\xef',
        'script_prefix_bytes': b'\xc4',
        'bech32_hrp': 'tltc',
        'address_types': (P2PKH, P2SH_P2WPKH, P2WPKH, P2TR),
        'apis': [{'url': 'https://litecoinspace.org/testnet/api', 'type': 'esplora'}],
        'network': {
            'magic': b'\xfd\xd2\xc8\xf1',
            'port': 19335,
            'protocol_version': 70016,
            'seeds': [
                'seed-b.litecoin.loshan.co.uk',
                'dnsseed-testnet.thrasher.io',
            ],
        },
    },
    'ZEC': {
        'name': 'zcash',
        'slip44': 133,
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': [{'url': 'https://explorer.zcashfr.io/api'}],
        'network': {
            'magic': b'\x24\xe9\x27\x64',
            'port': 8233,
            'protocol_version': 170150,
            'seeds': [
                'dnsseed.z.cash',
                'dnsseed.str4d.xyz',
                'mainnet.seeder.zfnd.org',
                'mainnet.is.yolo.money',
            ],
        },
    },
    'ZCL': {
        'name': 'zclassic',
        'slip44': 147,
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': [],
    },
    'ZEIT': {
        'name': 'zeit',
        'address_prefix_bytes': b'\x33',
        'secret_prefix_bytes': b'\xb3',
        'script_prefix_bytes': b'\x08',
    },
    'ZEN': {
        'name': 'horizen',
        'slip44': 121,
        'address_prefix_bytes': b'\x20\x89',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'params': {'check_block_at_height': True},
        'apis': [{'url': 'https://explorer.zensystem.io/insight-api-zen'}],
        'network': {
            'magic': b'\x63\x61\x73\x68',
            'port': 9033,
            'protocol_version': 170002,
            'seeds': [
                'dnsseed.horizen.global',
                'dnsseed.zensystem.io',
                'mainnet.horizen.global',
                'mainnet.zensystem.io',
            ],
        },
    },
    'ZERO': {
        'name': 'zero',
        'slip44': 323,
        'address_prefix_bytes': b'\x1c\xb8',
        'secret_prefix_bytes': b'\x80',
        'script_prefix_bytes': b'\x1c\xbd',
        'apis': [
            {'url': 'https://insight.zeromachine.io/insight-api-zero'},
        ],
    },
}


def get_address_types(coin):
    return coin.get('address_types', (P2PKH,))


def get_coins_with_api():
    return ','.join(coin['name'].title() for coin in coins.values() if coin.get('apis'))
