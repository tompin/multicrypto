import validators

from multicrypto.coins import coins


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
