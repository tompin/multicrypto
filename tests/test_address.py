import pytest
from multicrypto.coins import coins, validate_coin_symbol

from multicrypto.address import get_private_key_from_wif_format, \
    convert_private_key_to_address, translate_address, validate_pattern


def test_convert_private_key_to_address():
    # wif private key is '5HwoXVkHoRM8sL2KmNRS217n1g8mPPBomrY7yehCuXC1115WWsh'
    private_key = 7719472615821079694904732333912527190217998977709370935963838933860875309329

    address = convert_private_key_to_address(
        private_key, address_prefix_bytes=coins['BTC']['address_prefix_bytes'])

    assert address == '1Q1pE5vPGEEMqRcVRMbtBK842Y6Pzo6nK9'


def test_get_private_key_from_wif_format_uncompressed():
    pk_wif_uncompressed = '5HwoXVkHoRM8sL2KmNRS217n1g8mPPBomrY7yehCuXC1115WWsh'

    priv_key, is_compressed = get_private_key_from_wif_format(pk_wif_uncompressed)

    assert 7719472615821079694904732333912527190217998977709370935963838933860875309329 == priv_key
    assert is_compressed is False


def test_get_private_key_from_wif_format_compressed():
    pk_wif_compressed = 'KwntMbt59tTsj8xqpqYqRRWufyjGunvhSyeMo3NTYpFYzZbXJ5Hp'

    priv_key, is_compressed = get_private_key_from_wif_format(pk_wif_compressed)

    assert 7719472615821079694904732333912527190217998977709370935963838933860875309329 == priv_key
    assert is_compressed is True


def test_validate_pattern_success():
    pattern = '123456'
    coin_symbol = 'BTC'

    result = validate_pattern(pattern, coin_symbol, False)

    assert result is True


def test_validate_pattern_raise_no_base58_characters():
    pattern = 'containIO'
    coin_symbol = 'BTC'

    with pytest.raises(Exception) as exc_info:
        validate_pattern(pattern, coin_symbol, False)
    assert str(exc_info.value) == 'pattern containIO contains not allowed characters: IO'


def test_validate_coin_raise_unsupported_coin():
    coin_symbol = 'XYZ'

    with pytest.raises(Exception) as exc_info:
        validate_coin_symbol(coin_symbol)
    assert str(exc_info.value) == 'Coin XYZ is not supported'


def test_validate_pattern_raise_impossible_prefix():
    pattern = '211'
    coin_symbol = 'BTC'
    btc_range = '1111111111111111111111111-1QLbz7JHiBTspS962RLKV8GndWFwiEaqKL'
    error_message = 'Impossible prefix! Choose different one from {} range.'.format(btc_range)

    with pytest.raises(Exception) as exc_info:
        validate_pattern(pattern, coin_symbol, False)
    assert str(exc_info.value) == error_message


def test_translate_address():
    hush_address = 't1VhzEoupqVVJoYaMaSZ534hD77L3MFFAXr'
    kmd_address = 'RM7aJzNyTzWHGutf7Bj4zmvVcibZCnvXKS'

    translated_address = translate_address(
        hush_address, coins['HUSH']['address_prefix_bytes'], coins['KMD']['address_prefix_bytes'])

    assert translated_address == kmd_address
