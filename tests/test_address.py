import pytest

from multicrypto.address import (
    get_private_key_from_wif_format,
    convert_private_key_to_address,
    translate_address,
    validate_pattern,
    validate_wif_private_key,
)
from multicrypto.base58 import base58
from multicrypto.coins import coins


def test_convert_private_key_to_address():
    # wif private key is '5HwoXVkHoRM8sL2KmNRS217n1g8mPPBomrY7yehCuXC1115WWsh'
    private_key = 7719472615821079694904732333912527190217998977709370935963838933860875309329

    address = convert_private_key_to_address(private_key, coins['BTC']['address_prefix_bytes'])

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


def test_validate_pattern_raise_impossible_prefix():
    pattern = '211'
    coin_symbol = 'BTC'
    btc_range = '1111111111111111111111111-1QLbz7JHiBTspS962RLKV8GndWFwiEaqKL'
    error_message = (
        'Impossible prefix! Choose different one from {} range'
        '(characters order is {})'.format(btc_range, base58)
    )

    with pytest.raises(Exception) as exc_info:
        validate_pattern(pattern, coin_symbol, False)
    assert str(exc_info.value) == error_message


def test_translate_address():
    zcash_address = 't1VhzEoupqVVJoYaMaSZ534hD77L3MFFAXr'
    ltc_address = 'LX4LVgoWwpwmTiDcp9jFBGf44fWEe5mEae'

    translated_address = translate_address(
        zcash_address, coins['ZEC']['address_prefix_bytes'], coins['LTC']['address_prefix_bytes']
    )

    assert translated_address == ltc_address


def test_validate_wif_private_key_compressed_success():
    btc_wif_private_key_compressed = 'KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp'

    result_compressed = validate_wif_private_key(btc_wif_private_key_compressed, 'BTC')

    assert result_compressed


def test_validate_wif_private_key_uncompressed_success():
    btc_wif_private_key_uncompressed = '5HwoXVkHoRM8sL2KmNRS217n1g8mPPBomrY7yehCuXC1115WWsh'

    result_uncompressed = validate_wif_private_key(btc_wif_private_key_uncompressed, 'BTC')

    assert result_uncompressed


def test_validate_wif_private_key_compressd_failure():
    btc_wif_private_key_compressed = 'KwDiDMtpksBAcfyHsVS5XzmirtyjKWSeaeM9U1QppugixMUeKMqp'

    with pytest.raises(Exception) as exc_info:
        validate_wif_private_key(btc_wif_private_key_compressed, 'LTC')
    assert str(exc_info.value) == 'Incorrect secret prefix 0x80 in wif private key for coin LTC'


def test_validate_wif_private_key_uncompressed_failure():
    btc_wif_private_key_uncompressed = '5HwoXVkHoRM8sL2KmNRS217n1g8mPPBomrY7yehCuXC1115WWsh'

    with pytest.raises(Exception) as exc_info:
        validate_wif_private_key(btc_wif_private_key_uncompressed, 'LTC')
    assert str(exc_info.value) == 'Incorrect secret prefix 0x80 in wif private key for coin LTC'
