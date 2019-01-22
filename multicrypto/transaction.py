import logging
import time

from multicrypto.address import decompose_address, encode_point, calculate_public_key_hash
from multicrypto.consts import OP_0
from multicrypto.ecdsa import sign
from multicrypto.ellipticcurve import secp256k1
from multicrypto.scripts import P2PKH_SCRIPT, P2SH_SCRIPT, is_p2sh
from multicrypto.utils import int_to_bytes, hex_to_bytes, der_encode_signature, \
    reverse_byte_hex, double_sha256

logger = logging.getLogger(__name__)


class TransactionInput:
    def __init__(self, transaction_id, output_index, locking_script, satoshis, private_key=None,
                 unlocking_script=None):
        """
        :param transaction_id: Transaction id in hex format
        :param output_index: Number (int) specifying the output of the transaction which
                             becomes new transaction input
        :param locking_script: Locking script in hex format
        :param satoshis: Amount in satoshis (int)
        :param private_key: Private key (int) needed to claim the input
        """
        self.transaction_id = hex_to_bytes(transaction_id, byteorder='big')
        self.output_index = output_index.to_bytes(4, byteorder='little')
        self.script = hex_to_bytes(locking_script, byteorder='big')
        self.script_length = int_to_bytes(len(self.script), byteorder='little')
        self.satoshis = satoshis.to_bytes(8, byteorder='little')
        if private_key:
            self.private_key = private_key
            self.public_key = private_key * secp256k1.G
            compressed_public_key_hash = calculate_public_key_hash(self.public_key, compressed=True)
            if compressed_public_key_hash.hex() not in locking_script:
                is_compressed_public_key = False
            else:
                is_compressed_public_key = True
            self.encoded_public_key = encode_point(
                self.public_key, compressed=is_compressed_public_key)
            self.public_key_len = len(self.encoded_public_key).to_bytes(1, byteorder='little')
        self.unlocking_script = hex_to_bytes(unlocking_script, byteorder='big')

    def get_encoded(self, with_script):
        input_data = self.transaction_id + self.output_index
        if with_script:
            input_data += self.script_length + self.script
        else:
            input_data += OP_0
        return input_data


class TransactionOutput:
    def __init__(self, address, satoshis, coin):
        self.satoshis = satoshis
        self.address = address
        self.prefix, self.address_digest = decompose_address(address, coin)
        if self.prefix == coin['script_prefix_bytes']:
            self.script = P2SH_SCRIPT % self.address_digest
        else:
            self.script = P2PKH_SCRIPT % self.address_digest


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
                locking_script=input['locking_script'],
                satoshis=input['satoshis'],
                private_key=input.get('private_key'),
                unlocking_script=input.get('unlocking_script', ''))
            for input in inputs]
        self.inputs_counter = int_to_bytes(len(self.inputs), byteorder='little')
        self.outputs = [
            TransactionOutput(
                address=output['address'],
                satoshis=output['satoshis'],
                coin=coin)
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
            script = output.script
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
        if is_p2sh(input.script):
            input.script = input.unlocking_script
            input.script_length = int_to_bytes(len(input.script), byteorder='little')
            return
        message = self.get_data_to_sign(position)
        sig = sign(message, input.private_key, secp256k1, double_sha256)  # ECDSA signing
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
            raise Exception('Transaction {} already created'.format(self.id))
        for i in range(len(self.inputs)):
            self.sign_input(i)
        raw_transaction_data = (
            self.version +
            self.inputs_counter +
            self.get_encoded_inputs(position=range(len(self.inputs))) +
            self.outputs_counter +
            self.get_encoded_outputs() +
            self.lock_time
        )
        self.id = reverse_byte_hex(double_sha256(raw_transaction_data).hexdigest())
        self.raw = raw_transaction_data.hex()
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
        raw_transaction_data = (
            self.version +
            self.transaction_time +
            self.inputs_counter +
            self.get_encoded_inputs(position=range(len(self.inputs))) +
            self.outputs_counter +
            self.get_encoded_outputs() +
            self.lock_time
        )
        self.id = reverse_byte_hex(double_sha256(raw_transaction_data).hexdigest())
        self.raw = raw_transaction_data.hex()
        logger.info('Created transaction with id: {}\nRaw data: {}'.format(
            self.id, self.raw))
        return self.raw
