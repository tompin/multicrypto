import logging
import time
from binascii import hexlify

from fastecdsa.curve import secp256k1
from fastecdsa.ecdsa import sign

from multicrypto.address import get_public_key_hash, encode_point, calculate_public_key_hash
from multicrypto.consts import OP_DUP, OP_HASH160, OP_PUSH_20, OP_CHECKSIG, OP_EQUALVERIFY, OP_0
from multicrypto.utils import int_to_bytes, hex_to_bytes, der_encode_signature, double_sha256_hex, \
    reverse_byte_hex

logger = logging.getLogger(__name__)


class TransactionInput:
    def __init__(self, transaction_id, output_index, script, satoshis, private_key):
        """
        :param transaction_id: Transaction id in hex format
        :param output_index: Number (int) specifying the output of the transaction which
                             becomes new transaction input
        :param script: Script in hex format
        :param satoshis: Amount in satoshis (int)
        :param private_key: Private key (int) needed to claim the input
        """
        self.transaction_id = hex_to_bytes(transaction_id, byteorder='big')
        self.output_index = output_index.to_bytes(4, byteorder='little')
        self.script = hex_to_bytes(script, byteorder='big')
        self.script_length = int_to_bytes(len(self.script), byteorder='little')
        self.satoshis = satoshis.to_bytes(8, byteorder='little')
        self.private_key = private_key
        self.public_key = private_key * secp256k1.G
        compressed_public_key_hash = calculate_public_key_hash(self.public_key, compressed=True)
        if compressed_public_key_hash.hex() in script:
            compressed_public_key = True
        else:
            compressed_public_key = False
        self.encoded_public_key = encode_point(
            self.public_key, compressed=compressed_public_key)
        self.public_key_len = len(self.encoded_public_key).to_bytes(1, byteorder='little')

    def get_encoded(self, with_script):
        input_data = self.transaction_id + self.output_index
        if with_script:
            input_data += self.script_length + self.script
        else:
            input_data += OP_0
        return input_data


class TransactionOutput:
    def __init__(self, address, satoshis, address_prefix_bytes):
        self.address = address
        self.public_key_hash = get_public_key_hash(address, address_prefix_bytes)
        self.satoshis = satoshis


class Transaction:
    def __init__(self, coin, inputs, outputs, **params):
        self.id = None
        self.raw = None
        self.coin = coin
        self.version = params.get('version') or coin.get('version') or b'\x01\x00\x00\x00'
        self.sequence = params.get('sequence') or coin.get('sequence') or b'\xff\xff\xff\xff'
        self.lock_time = params.get('lock_time') or coin.get('lock_time') or b'\x00\x00\x00\x00'
        self.hash_type = params.get('hash_type') or coin.get('hash_type') or b'\x01\x00\x00\x00'
        self.last_block = params.get('check_block_at_height')
        self.inputs = [
            TransactionInput(
                transaction_id=input['transaction_id'],
                output_index=input['output_index'],
                script=input['script'],
                satoshis=input['satoshis'],
                private_key=input['private_key'])
            for input in inputs]
        self.inputs_counter = int_to_bytes(len(self.inputs), byteorder='little')
        self.outputs = [
            TransactionOutput(
                address=output['address'],
                satoshis=output['satoshis'],
                address_prefix_bytes=coin['address_prefix_bytes'])
            for output in outputs]
        self.outputs_counter = int_to_bytes(len(self.outputs), byteorder='little')

    def get_encoded_inputs(self, position):
        input_block = b''
        for i, input in enumerate(self.inputs):
            if i in position:
                input_block += input.get_encoded(with_script=True)
            else:
                input_block += input.get_encoded(with_script=False)
            input_block += self.sequence
        return input_block

    def get_encoded_outputs(self):
        output_block = b''
        for output in self.outputs:
            script = OP_DUP + OP_HASH160 + OP_PUSH_20 + output.public_key_hash + \
                OP_EQUALVERIFY + OP_CHECKSIG
            if self.last_block:
                script += b'\x20' + hex_to_bytes(self.last_block['hash'], byteorder='little')
                height_bytes = int_to_bytes(self.last_block['height'], byteorder='little')
                script += len(height_bytes).to_bytes(1, byteorder='big') + height_bytes + b'\xb4'
            output_block += output.satoshis.to_bytes(8, byteorder='little')
            output_block += int_to_bytes(len(script), byteorder='little')
            output_block += script
        return output_block

    def get_data_to_sign(self, position):
        data = (
            # Four-byte version field
            self.version +

            # One-byte varint specifying the number of inputs
            self.inputs_counter +

            # Inputs
            self.get_encoded_inputs([position]) +

            # One-byte varint containing the number of outputs in our new transaction
            self.outputs_counter +

            # Outputs
            self.get_encoded_outputs() +

            # Four-byte "lock time" field
            self.lock_time +

            # Four-byte "hash code type"
            self.hash_type
        )
        return data

    def sign_input(self, position):
        input = self.inputs[position]
        message = self.get_data_to_sign(position)
        #  ECDSA signing is done as follows:
        #  given a message 'm', a sign-secret 'k', a private key 'x'
        #  calculate point R = G * k
        #  r = xcoordinate(R)
        #  s = (m + x * r) / k (mod q)
        #  q is the group order of secp256k1 = 2**256 - 432420386565659656852420866394968145599
        sig = sign(message.hex(), input.private_key, curve=secp256k1, hashfunc=double_sha256_hex)
        encoded_signature = der_encode_signature(sig)
        signature = encoded_signature + self.coin.get('sig_hash', b'\x01')
        script_sig = (
            len(signature).to_bytes(1, byteorder='little') +
            signature +
            input.public_key_len +
            input.encoded_public_key
        )
        input.script = script_sig
        input.script_length = int_to_bytes(len(script_sig), byteorder='little')

    def create(self):
        if self.id:
            raise Exception('Transaction id {} already created'.format(self.id))
        for i in range(len(self.inputs)):
            self.sign_input(i)
        raw_transaction_data = hexlify(
            self.version +
            self.inputs_counter +
            self.get_encoded_inputs(position=range(len(self.inputs))) +
            self.outputs_counter +
            self.get_encoded_outputs() +
            self.lock_time
        )
        self.id = reverse_byte_hex(double_sha256_hex(raw_transaction_data).hexdigest())
        self.raw = raw_transaction_data.decode()
        logger.info('Created transaction with id: {}\nRaw data: {}'.format(
            self.id, self.raw))
        return self.raw


class POSTransaction(Transaction):
    def __init__(self, coin, inputs, outputs, transaction_time=None, **params):
        if transaction_time is None:
            self.transaction_time = int(time.time()).to_bytes(4, byteorder='little')
        else:
            self.transaction_time = transaction_time
        for input in inputs:
            input['transaction_id'] = reverse_byte_hex(input['transaction_id'])
        super().__init__(coin, inputs, outputs, **params)

    def get_data_to_sign(self, position):
        data = (
            # Four-byte version field
            self.version +

            # Transaction creation time
            self.transaction_time +

            # One-byte varint specifying the number of inputs
            self.inputs_counter +

            # Inputs
            self.get_encoded_inputs([position]) +

            # One-byte varint containing the number of outputs in our new transaction
            self.outputs_counter +

            # Outputs
            self.get_encoded_outputs() +

            # Four-byte "lock time" field
            self.lock_time +

            # Four-byte "hash code type"
            self.hash_type
        )
        return data

    def create(self):
        if self.id:
            raise Exception('Transaction id {} already created'.format(self.id))
        for i in range(len(self.inputs)):
            self.sign_input(i)
        raw_transaction_data = hexlify(
            self.version +
            self.transaction_time +
            self.inputs_counter +
            self.get_encoded_inputs(position=range(len(self.inputs))) +
            self.outputs_counter +
            self.get_encoded_outputs() +
            self.lock_time
        )
        self.id = reverse_byte_hex(double_sha256_hex(raw_transaction_data).hexdigest())
        self.raw = raw_transaction_data.decode()
        logger.info('Created transaction with id: {}\nRaw data: {}'.format(
            self.id, self.raw))
        return self.raw
