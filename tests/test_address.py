import pytest

from multicrypto.address import (
    convert_private_key_to_coin_address,
    decode_segwit_address,
    get_private_key_from_wif_format,
    convert_private_key_to_address,
    validate_address,
    translate_address,
    validate_pattern,
    validate_wif_private_key,
)
from multicrypto.base58 import BASE58_ALPHABET
from multicrypto.coins import P2PKH, P2SH_P2WPKH, P2TR, P2WPKH, coins


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
        'Impossible prefix! Choose different one from {} range(characters order is {})'.format(
            btc_range, BASE58_ALPHABET
        )
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


@pytest.mark.parametrize(
    'coin_symbol,address_type,expected_address',
    [
        ('BTC', P2PKH, '1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH'),
        ('BTC', P2SH_P2WPKH, '3JvL6Ymt8MVWiCNHC7oWU6nLeHNJKLZGLN'),
        ('BTC', P2WPKH, 'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4'),
        ('TBTC', P2WPKH, 'tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx'),
        ('LTC', P2WPKH, 'ltc1qw508d6qejxtdg4y5r3zarvary0c5xw7kgmn4n9'),
        ('TLTC', P2WPKH, 'tltc1qw508d6qejxtdg4y5r3zarvary0c5xw7klfsuq0'),
        ('LTC', P2PKH, 'LVuDpNCSSj6pQ7t9Pv6d6sUkLKoqDEVUnJ'),
        ('BTC', P2TR, 'bc1pmfr3p9j00pfxjh0zmgp99y8zftmd3s5pmedqhyptwy6lm87hf5sspknck9'),
        ('TBTC', P2TR, 'tb1pmfr3p9j00pfxjh0zmgp99y8zftmd3s5pmedqhyptwy6lm87hf5ssk79hv2'),
        ('LTC', P2TR, 'ltc1pmfr3p9j00pfxjh0zmgp99y8zftmd3s5pmedqhyptwy6lm87hf5sszjagvq'),
        ('TLTC', P2TR, 'tltc1pmfr3p9j00pfxjh0zmgp99y8zftmd3s5pmedqhyptwy6lm87hf5ssfaekn4'),
    ],
)
def test_convert_private_key_to_coin_address(coin_symbol, address_type, expected_address):
    address = convert_private_key_to_coin_address(1, coins[coin_symbol], True, address_type)

    assert address == expected_address


def test_convert_private_key_to_p2tr_address_bip341():
    """Key path only output from BIP-341 wallet test vectors"""
    private_key = 0x6B973D88838F27366ED61C9AD6367663045CB456E28335C109E30717AE0C6BAA

    address = convert_private_key_to_coin_address(private_key, coins['BTC'], True, P2TR)

    assert address == 'bc1p2wsldez5mud2yam29q22wgfh9439spgduvct83k3pm50fcxa5dps59h4z5'


@pytest.mark.parametrize(
    'coin_symbol,compressed,address_type,error',
    [
        ('BTC', False, P2WPKH, 'Segwit addresses require compressed public key'),
        ('BTC', False, P2SH_P2WPKH, 'Segwit addresses require compressed public key'),
        ('ZEC', True, P2WPKH, 'Address type p2wpkh is not supported for zcash'),
        ('ZEC', True, P2SH_P2WPKH, 'supported types: p2pkh'),
        ('BTC', False, P2TR, 'Segwit addresses require compressed public key'),
        ('ZEC', True, P2TR, 'Address type p2tr is not supported for zcash'),
        ('BTC', True, 'p2wsh', 'Unknown address type p2wsh'),
    ],
)
def test_convert_private_key_to_coin_address_failure(coin_symbol, compressed, address_type, error):
    with pytest.raises(ValueError, match=error):
        convert_private_key_to_coin_address(1, coins[coin_symbol], compressed, address_type)


def test_decode_segwit_address():
    witness_version, witness_program = decode_segwit_address(
        'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4', coins['BTC']
    )

    assert witness_version == 0
    assert bytes(witness_program).hex() == '751e76e8199196d454941c45d1b3a323f1433bd6'
    assert (
        decode_segwit_address('bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4', coins['TBTC']) is None
    )
    assert decode_segwit_address('bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4', coins['ZEC']) is None


@pytest.mark.parametrize(
    'address,coin_symbol',
    [
        ('bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4', 'BTC'),
        ('BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4', 'BTC'),
        ('bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0', 'BTC'),
        ('tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx', 'TBTC'),
    ],
)
def test_validate_segwit_address_success(address, coin_symbol):
    assert validate_address(address, coin_symbol)


@pytest.mark.parametrize(
    'address',
    [
        'bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t5',  # incorrect checksum
        'bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7k7grplx',  # bech32 v1
    ],
)
def test_validate_segwit_address_failure(address):
    with pytest.raises(ValueError, match='Incorrect bech32 address'):
        validate_address(address, 'BTC')
