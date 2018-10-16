import pytest

from multicrypto.ethaddress import to_checksum_address

valid_checksum_eth_addresses = [
    '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed',
    '0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359',
    '0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB',
    '0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb'
]


@pytest.mark.parametrize("address", valid_checksum_eth_addresses)
def test_valid_checksum_eth_addresses(address):
    assert address == to_checksum_address(address)


invalid_checksum_eth_addresses = [
    '0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    '0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
]


@pytest.mark.parametrize("address", invalid_checksum_eth_addresses)
def test_invalid_checksum_eth_addresses(address):
    with pytest.raises(AssertionError):
        assert address == to_checksum_address(address)


# Private key: eff415edb6331f4f67bdb7f1ecc639da9bcc0550b100bb275c7b5b21ce3a7804
# Public key:  d6dd5241c03bf418b333c256057ee878c34975d6abda075d58e4b9780f4a8659fcc096b6ad763d8e5914f7daa0b7351398b1eb6458e95ac41a2711a0651f3fc6
# Address:     0x4206f95fc533483fae4687b86c1d0a0088e3cd48

# Private key: 9442b4b82c8011530f3a363cc87a4ea91efd53552faab2e63fd352db9367bb24
# Public key:  3f538de115393e2a8851b4c19f686b6bb245213c3823e69336583f1d72c53d20831ea0574900b31d833932b3e8e71b4e99d574c6480890d60153fc2dccbc96d6
# Address:     0x083c41ea13af6c2d5aaddf6e73142eb9a7b00183

# Private key: 981679905857953c9a21e1807aab1b897a395ea0c5c96b32794ccb999a3cd781
# Public key:  7454f003941bba7c5e16d8c9fce19104b2f51486e00d47f39e6eb0aea6f1c6f80cad2d239c8b4b1bf903e41960920f735fda4fcc4422aa815416b7d0df62f8a5
# Address:     0x5fe3062B24033113fbf52b2b75882890D7d8CA54
