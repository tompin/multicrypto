from sha3 import keccak_256

from fastecdsa.curve import secp256k1
from fastecdsa.keys import gen_keypair


def convert_public_key_to_addres(public_key, with_check_sum=False):
    encoded_public_key = '{}{}'.format(public_key.x, public_key.y).encode()
    address = '0x' + keccak_256(encoded_public_key).hexdigest()[24:]
    if with_check_sum:
        address = to_checksum_address(address)
    return address


def generate_address(with_check_sum=False):
    private_key, public_key = gen_keypair(secp256k1)
    return convert_public_key_to_addres(public_key, with_check_sum)


def to_checksum_address(address):
    address_data = address.lower()[2:]
    address_hash = keccak_256(address_data.encode()).hexdigest()
    address_data = ''.join(
        address_data[i].upper() if int(address_hash[i], 16) > 7 else address_data[i]
        for i in range(40))
    return '0x' + address_data
