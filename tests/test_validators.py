import pytest

from multicrypto.validators import check_coin_symbol


def test_validate_coin_raise_unsupported_coin():
    coin_symbol = 'XYZ'

    with pytest.raises(Exception) as exc_info:
        check_coin_symbol(coin_symbol)
    assert str(exc_info.value) == 'XYZ is not supported coin symbol'
