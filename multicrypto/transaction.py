import hashlib
import logging
import time

from multicrypto.address import calculate_public_key_hash, encode_point
from multicrypto.consts import OP_0
from multicrypto.ecdsa import sign
from multicrypto.ellipticcurve import secp256k1
from multicrypto.schnorr import (
    schnorr_sign,
    tagged_hash,
    taproot_output_key,
    taproot_tweak_private_key,
)
from multicrypto.scripts import (
    P2PKH_SCRIPT,
    P2WPKH_SCRIPT,
    address_to_script,
    is_p2sh,
    is_p2tr,
    is_p2wpkh,
)
from multicrypto.utils import (
    int_to_bytes,
    int_to_varint,
    hex_to_bytes,
    der_encode_signature,
    encode_script,
    reverse_byte_hex,
    double_sha256,
)

SEGWIT_MARKER_AND_FLAG = b'\x00\x01'
# Taproot signature hash types (BIP-341) committing to all inputs and outputs, SIGHASH_DEFAULT
# signature has 64 bytes, SIGHASH_ALL signature has hash type byte appended
SIGHASH_DEFAULT = 0
SIGHASH_ALL = 1

logger = logging.getLogger(__name__)


class TransactionInput:
    def __init__(
        self,
        transaction_id,
        output_index,
        locking_script,
        satoshis,
        private_key=None,
        unlocking_script=None,
    ):
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
        # Script is replaced with unlocking script during signing, taproot signature hash
        # commits to locking scripts of all inputs
        self.locking_script = self.script
        self.script_length = int_to_bytes(len(self.script), byteorder='little')
        self.satoshis = satoshis.to_bytes(8, byteorder='little')
        # Public key hash of P2WPKH or P2SH-P2WPKH input (witness version 0), output key of P2TR
        # input (witness version 1), None for non segwit inputs
        self.witness_program = None
        self.witness_version = None
        self.witness = []
        if private_key:
            self.private_key = private_key
            self.public_key = private_key * secp256k1.G
            compressed_public_key_hash = calculate_public_key_hash(self.public_key, compressed=True)
            nested_segwit_hash = calculate_public_key_hash(
                self.public_key, compressed=True, segwit=True
            )
            is_nested_segwit = is_p2sh(self.script) and self.script[2:22] == nested_segwit_hash
            if is_p2tr(self.script) and self.script[2:] == taproot_output_key(private_key):
                # Taproot key path spend (BIP-86), public key is not revealed in the witness
                self.witness_version = 1
                self.witness_program = self.script[2:]
                is_compressed_public_key = True
            elif is_p2wpkh(self.script) or is_nested_segwit:
                # Segwit requires compressed public keys
                self.witness_version = 0
                self.witness_program = compressed_public_key_hash
                is_compressed_public_key = True
            elif compressed_public_key_hash.hex() not in locking_script:
                is_compressed_public_key = False
            else:
                is_compressed_public_key = True
            self.encoded_public_key = encode_point(
                self.public_key, compressed=is_compressed_public_key
            )
            self.public_key_len = len(self.encoded_public_key).to_bytes(1, byteorder='little')
        self.unlocking_script = hex_to_bytes(unlocking_script, byteorder='big')

    @property
    def is_segwit(self):
        return self.witness_program is not None

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
        self.script = address_to_script(address, coin)


class Transaction:
    def __init__(self, coin, inputs, outputs, **params):
        self.id = None
        self.raw = None
        self.coin = coin
        self.version = params.get('version') or coin.get('version') or b'\x01\x00\x00\x00'
        self.sequence = params.get('sequence') or coin.get('sequence') or b'\xff\xff\xff\xff'
        self.lock_time = params.get('lock_time') or coin.get('lock_time') or b'\x00\x00\x00\x00'
        self.hash_type = params.get('hash_type') or coin.get('hash_type') or b'\x01\x00\x00\x00'
        self.history_block = params.get('check_block_at_height')
        self.inputs = [
            TransactionInput(
                transaction_id=inp['transaction_id'],
                output_index=inp['output_index'],
                locking_script=inp['locking_script'],
                satoshis=inp['satoshis'],
                private_key=inp.get('private_key'),
                unlocking_script=inp.get('unlocking_script', ''),
            )
            for inp in inputs
        ]
        self.inputs_counter = int_to_bytes(len(self.inputs), byteorder='little')
        self.outputs = [
            TransactionOutput(address=output['address'], satoshis=output['satoshis'], coin=coin)
            for output in outputs
        ]
        self.outputs_counter = int_to_bytes(len(self.outputs), byteorder='little')

    @property
    def is_segwit(self):
        return any(inp.is_segwit for inp in self.inputs)

    def get_encoded_inputs(self, position):
        input_block = b''
        for i, inp in enumerate(self.inputs):
            if i in position:
                input_block += inp.get_encoded(with_script=True)
            else:
                input_block += inp.get_encoded(with_script=False)
            input_block += self.sequence
        return input_block

    def get_encoded_outputs(self):
        output_block = b''
        for output in self.outputs:
            script = output.script
            if self.history_block:
                script += b'\x20' + hex_to_bytes(self.history_block['hash'], byteorder='little')
                height_bytes = int_to_bytes(self.history_block['height'], byteorder='little')
                script += len(height_bytes).to_bytes(1, byteorder='big') + height_bytes + b'\xb4'
            output_block += output.satoshis.to_bytes(8, byteorder='little')
            output_block += int_to_bytes(len(script), byteorder='little')
            output_block += script
        return output_block

    def get_data_to_sign(self, position):
        data = (
            # Four-byte version field
            self.version
            +
            # One-byte varint specifying the number of inputs
            self.inputs_counter
            +
            # Inputs
            self.get_encoded_inputs([position])
            +
            # One-byte varint containing the number of outputs in our new transaction
            self.outputs_counter
            +
            # Outputs
            self.get_encoded_outputs()
            +
            # Four-byte "lock time" field
            self.lock_time
            +
            # Four-byte "hash code type"
            self.hash_type
        )
        return data

    def get_segwit_data_to_sign(self, position):
        """Signature hash preimage for segwit version 0 inputs according to BIP-143"""
        inp = self.inputs[position]
        prevouts = b''.join(i.transaction_id + i.output_index for i in self.inputs)
        sequences = self.sequence * len(self.inputs)
        # For P2WPKH script code is the same as P2PKH locking script
        script_code = encode_script(P2PKH_SCRIPT % inp.witness_program)
        data = (
            self.version
            + double_sha256(prevouts).digest()
            + double_sha256(sequences).digest()
            # Outpoint of the signed input
            + inp.transaction_id
            + inp.output_index
            + script_code
            + inp.satoshis
            + self.sequence
            + double_sha256(self.get_encoded_outputs()).digest()
            + self.lock_time
            + self.hash_type
        )
        return data

    def sign_segwit_input(self, position):
        inp = self.inputs[position]
        message = self.get_segwit_data_to_sign(position)
        sig = sign(message, inp.private_key, secp256k1, double_sha256)
        signature = der_encode_signature(sig) + self.coin.get('sig_hash', b'\x01')
        inp.witness = [signature, inp.encoded_public_key]
        if is_p2sh(inp.script):
            # P2SH-P2WPKH: unlocking script only pushes the redeem script (witness program)
            redeem_script = P2WPKH_SCRIPT % inp.witness_program
            inp.script = encode_script(redeem_script)
        else:
            # P2WPKH: unlocking script is empty
            inp.script = b''
        inp.script_length = int_to_varint(len(inp.script))

    def get_taproot_data_to_sign(self, position):
        return get_taproot_signature_message(
            version=self.version,
            lock_time=self.lock_time,
            prevouts=[inp.transaction_id + inp.output_index for inp in self.inputs],
            amounts=[inp.satoshis for inp in self.inputs],
            locking_scripts=[inp.locking_script for inp in self.inputs],
            sequences=[self.sequence] * len(self.inputs),
            encoded_outputs=self.get_encoded_outputs(),
            position=position,
        )

    def sign_taproot_input(self, position):
        inp = self.inputs[position]
        message = self.get_taproot_data_to_sign(position)
        private_key = taproot_tweak_private_key(inp.private_key)
        # SIGHASH_DEFAULT signature has no hash type byte appended
        inp.witness = [schnorr_sign(tagged_hash('TapSighash', message), private_key)]
        # P2TR: unlocking script is empty
        inp.script = b''
        inp.script_length = int_to_varint(len(inp.script))

    def get_encoded_witnesses(self):
        witness_block = b''
        for inp in self.inputs:
            witness_block += int_to_varint(len(inp.witness))
            for item in inp.witness:
                witness_block += int_to_varint(len(item)) + item
        return witness_block

    def sign_input(self, position):
        inp = self.inputs[position]
        if inp.witness_version == 1:
            self.sign_taproot_input(position)
            return
        if inp.is_segwit:
            self.sign_segwit_input(position)
            return
        if is_p2sh(inp.script):
            inp.script = inp.unlocking_script
            inp.script_length = int_to_bytes(len(inp.script), byteorder='little')
            return
        message = self.get_data_to_sign(position)
        sig = sign(message, inp.private_key, secp256k1, double_sha256)  # ECDSA signing
        encoded_signature = der_encode_signature(sig)
        signature = encoded_signature + self.coin.get('sig_hash', b'\x01')
        script_sig = (
            len(signature).to_bytes(1, byteorder='little')
            + signature
            + inp.public_key_len
            + inp.encoded_public_key
        )
        inp.script = script_sig
        inp.script_length = int_to_bytes(len(script_sig), byteorder='little')

    def create(self):
        if self.id:
            raise Exception(f'Transaction {self.id} already created')
        for i in range(len(self.inputs)):
            self.sign_input(i)
        inputs_and_outputs = (
            self.inputs_counter
            + self.get_encoded_inputs(position=range(len(self.inputs)))
            + self.outputs_counter
            + self.get_encoded_outputs()
        )
        raw_transaction_data = self.version + inputs_and_outputs + self.lock_time
        # Transaction id is calculated without witness data (BIP-141)
        self.id = reverse_byte_hex(double_sha256(raw_transaction_data).hexdigest())
        if self.is_segwit:
            # Serialization with witness data according to BIP-144
            raw_transaction_data = (
                self.version
                + SEGWIT_MARKER_AND_FLAG
                + inputs_and_outputs
                + self.get_encoded_witnesses()
                + self.lock_time
            )
        self.raw = raw_transaction_data.hex()
        logger.info('Created transaction with id: %s\nRaw data: %s', self.id, self.raw)
        return self.raw


def get_taproot_signature_message(
    version,
    lock_time,
    prevouts,
    amounts,
    locking_scripts,
    sequences,
    encoded_outputs,
    position,
    hash_type=SIGHASH_DEFAULT,
):
    """Signature message (with epoch prefix) for taproot key path spending according to
    BIP-341, hashed with tagged hash 'TapSighash' gives signed message. Only SIGHASH_DEFAULT
    and SIGHASH_ALL without annex are supported.

    :param prevouts: Outpoints (transaction id and output index) of all inputs
    :param amounts: Amounts (8 bytes little-endian) of all inputs
    :param locking_scripts: Locking scripts of all inputs
    :param sequences: Sequences of all inputs
    :param encoded_outputs: Serialized outputs of the transaction
    :param position: Index of the signed input
    """
    if hash_type not in (SIGHASH_DEFAULT, SIGHASH_ALL):
        raise ValueError(f'Unsupported taproot signature hash type {hash_type}')

    def sha256(data):
        return hashlib.sha256(data).digest()

    return (
        # Epoch
        b'\x00'
        + hash_type.to_bytes(1, byteorder='little')
        + version
        + lock_time
        + sha256(b''.join(prevouts))
        + sha256(b''.join(amounts))
        + sha256(b''.join(int_to_varint(len(script)) + script for script in locking_scripts))
        + sha256(b''.join(sequences))
        + sha256(encoded_outputs)
        # Spend type: key path spending without annex
        + b'\x00'
        + position.to_bytes(4, byteorder='little')
    )


class POSTransaction(Transaction):
    def __init__(self, coin, inputs, outputs, transaction_time=None, **params):
        if transaction_time is None:
            self.transaction_time = int(time.time()).to_bytes(4, byteorder='little')
        else:
            self.transaction_time = transaction_time
        for inp in inputs:
            inp['transaction_id'] = reverse_byte_hex(inp['transaction_id'])
        super().__init__(coin, inputs, outputs, **params)

    def get_data_to_sign(self, position):
        data = (
            # Four-byte version field
            self.version
            # Transaction creation time
            + self.transaction_time
            # One-byte varint specifying the number of inputs
            + self.inputs_counter
            # Inputs
            + self.get_encoded_inputs([position])
            # One-byte varint containing the number of outputs in our new transaction
            + self.outputs_counter
            # Outputs
            + self.get_encoded_outputs()
            # Four-byte "lock time" field
            + self.lock_time
            # Four-byte "hash code type"
            + self.hash_type
        )
        return data

    def create(self):
        if self.id:
            raise Exception(f'Transaction id {self.id} already created')
        for i in range(len(self.inputs)):
            self.sign_input(i)
        raw_transaction_data = (
            self.version
            + self.transaction_time
            + self.inputs_counter
            + self.get_encoded_inputs(position=range(len(self.inputs)))
            + self.outputs_counter
            + self.get_encoded_outputs()
            + self.lock_time
        )
        self.id = reverse_byte_hex(double_sha256(raw_transaction_data).hexdigest())
        self.raw = raw_transaction_data.hex()
        logger.info('Created transaction with id: %s\nRaw data: %s', self.id, self.raw)
        return self.raw
