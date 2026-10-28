import validators

from multicrypto.coins import ADDRESS_TYPES, P2PKH, P2SH_P2WPKH, P2WPKH, coins, get_address_types


def test_apis_urls_not_ending_with_slash():
    coins_with_api = [coin for coin in coins.values() if coin.get('apis')]

    for coin in coins_with_api:
        for api in coin['apis']:
            assert not api['url'].endswith('/')


def test_apis_urls_are_valid():
    coins_with_api = [coin for coin in coins.values() if coin.get('apis')]

    for coin in coins_with_api:
        for api in coin['apis']:
            assert validators.url(api['url'])


def test_address_types_are_known():
    for coin in coins.values():
        assert set(get_address_types(coin)) <= set(ADDRESS_TYPES)
        assert P2PKH in get_address_types(coin)


def test_native_segwit_coins_define_bech32_hrp():
    for coin in coins.values():
        assert (P2WPKH in get_address_types(coin)) == bool(coin.get('bech32_hrp'))


def test_segwit_coins():
    segwit_coins = {
        symbol for symbol, coin in coins.items() if P2SH_P2WPKH in get_address_types(coin)
    }

    assert segwit_coins == {'BTC', 'TBTC', 'LTC', 'TLTC'}


def test_slip44_coin_types():
    assert {symbol: coin.get('slip44') for symbol, coin in coins.items()} == {
        'BTC': 0,
        'DASH': 5,
        'DOGE': 3,
        'LTC': 2,
        'TBTC': 1,
        'TLTC': 1,
    }
