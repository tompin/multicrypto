import pytest

from multicrypto.coins import coins
from multicrypto.scripts import address_to_script, get_dust_threshold


@pytest.mark.parametrize(
    'address, dust_threshold',
    [
        ('15ZTYi2AhyAAqzfhbFnsRMMXXZnwiymnU4', 546),  # P2PKH
        ('3P14159f73E4gFr7JterCCQh9QjiTjiZrG', 540),  # P2SH
        ('bc1qjfw5q2ygp0gvn450h3lu0hlwjanfsc5uax7v9q', 294),  # P2WPKH
        ('bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3', 330),  # P2WSH
        ('bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0', 330),  # P2TR
    ],
)
def test_get_dust_threshold(address, dust_threshold):
    script = address_to_script(address, coins['BTC'])

    assert get_dust_threshold(script) == dust_threshold
