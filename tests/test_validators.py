import pytest

from multicrypto.validators import check_coin_symbol, check_non_negative, check_positive

negative_values = ['-9999999', '-1']
non_positive_values = ['-9999999', '-1', '0']


@pytest.mark.parametrize("value", negative_values)
def test_check_non_negative_raise_exception(value):
    with pytest.raises(Exception) as exc_info:
        check_non_negative(value)
    assert str(exc_info.value) == '{} is an invalid non negative int value'.format(value)


@pytest.mark.parametrize("value", non_positive_values)
def test_check_positive_raise_exception(value):
    with pytest.raises(Exception) as exc_info:
        check_positive(value)
    assert str(exc_info.value) == '{} is an invalid positive int value'.format(value)


def test_validate_coin_raise_unsupported_coin():
    coin_symbol = 'XYZ'

    with pytest.raises(Exception) as exc_info:
        check_coin_symbol(coin_symbol)
    assert str(exc_info.value) == 'XYZ is not supported coin symbol'
