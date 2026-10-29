# Types of addresses which can be derived from a private key and spent
P2PKH = 'p2pkh'
P2SH_P2WPKH = 'p2sh-p2wpkh'  # segwit nested in P2SH, e.g. 3... for BTC
P2WPKH = 'p2wpkh'  # native segwit (bech32), e.g. bc1q... for BTC
P2TR = 'p2tr'  # taproot key path only (bech32m, BIP-86), e.g. bc1p... for BTC
ADDRESS_TYPES = (P2PKH, P2SH_P2WPKH, P2WPKH, P2TR)
# Pseudo address type of Ethereum coins, they have one kind of addresses (not in ADDRESS_TYPES,
# which lists the address types of the coins with unspent outputs)
ETHEREUM = 'ethereum'

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
    'DASH': {
        'name': 'dash',
        'message_prefix': 'DarkCoin',
        'slip44': 5,
        'address_prefix_bytes': b'\x4c',
        'secret_prefix_bytes': b'\xcc',
        'script_prefix_bytes': b'\x10',
        'apis': [{'url': 'https://insight.dash.org/insight-api'}],
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
}

# Coins using the account model of Ethereum instead of unspent outputs, they have their own
# addresses, transactions and APIs (JSON-RPC of nodes and Blockscout explorers), so they are kept
# apart from the coins above. 'rpcs' lists JSON-RPC endpoints of public nodes tried in order.
ethereum_coins = {
    'ETH': {
        'name': 'ethereum',
        'slip44': 60,
        'chain_id': 1,
        'rpcs': [
            'https://ethereum-rpc.publicnode.com',
            'https://eth.drpc.org',
            'https://mainnet.gateway.tenderly.co',
        ],
        'explorers': [{'url': 'https://eth.blockscout.com/api/v2', 'type': 'blockscout'}],
    },
    'TETH': {
        'name': 'ethereum sepolia testnet',
        # Ethereum wallets (e.g. MetaMask) use the coin type of the mainnet on testnets too
        'slip44': 60,
        'chain_id': 11155111,
        'rpcs': [
            'https://ethereum-sepolia-rpc.publicnode.com',
            'https://sepolia.gateway.tenderly.co',
            'https://rpc.sepolia.ethpandaops.io',
        ],
        'explorers': [{'url': 'https://eth-sepolia.blockscout.com/api/v2', 'type': 'blockscout'}],
    },
}


def get_address_types(coin):
    if 'chain_id' in coin:
        return (ETHEREUM,)
    return coin.get('address_types', (P2PKH,))


def get_coins_with_api():
    return ','.join(coin['name'].title() for coin in coins.values() if coin.get('apis'))


def get_any_coin(coin_symbol):
    """Definition of the coin with unspent outputs or of the Ethereum coin."""
    if coin_symbol in coins:
        return coins[coin_symbol]
    if coin_symbol in ethereum_coins:
        return ethereum_coins[coin_symbol]
    raise ValueError(f'Unknown coin {coin_symbol}')


def is_ethereum(coin_symbol):
    return coin_symbol in ethereum_coins
