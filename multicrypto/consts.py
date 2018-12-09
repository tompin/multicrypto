OP_0 = OP_FALSE = b'\x00'  # An empty array of bytes is pushed onto the stack (this is not a no-op)
OP_1 = OP_TRUE = b'\x51'  # The number 1 is pushed onto the stack.
OP_2 = b'\x52'  # The number 2 is pushed onto the stack.
OP_3 = b'\x53'  # The number 3 is pushed onto the stack.
OP_4 = b'\x54'  # The number 4 is pushed onto the stack.
OP_5 = b'\x55'  # The number 5 is pushed onto the stack.
OP_6 = b'\x56'  # The number 6 is pushed onto the stack.
OP_7 = b'\x57'  # The number 7 is pushed onto the stack.
OP_8 = b'\x58'  # The number 8 is pushed onto the stack.
OP_9 = b'\x59'  # The number 9 is pushed onto the stack.
OP_10 = b'\x5a'  # The number 10 is pushed onto the stack.
OP_11 = b'\x5b'  # The number 11 is pushed onto the stack.
OP_12 = b'\x5c'  # The number 12 is pushed onto the stack.
OP_13 = b'\x5d'  # The number 13 is pushed onto the stack.
OP_14 = b'\x5e'  # The number 14 is pushed onto the stack.
OP_15 = b'\x5f'  # The number 15 is pushed onto the stack.
OP_16 = b'\x60'  # The number 16 is pushed onto the stack.

OP_1ADD = b'\x8b'  # 1 is added to the input.
OP_1SUB = b'\x8c'  # 1 is subtracted from the input.
OP_NEGATE = b'\x8f'  # The sign of the input is flipped.
OP_ABS = b'\x90'  # The input is made positive.
OP_NOT = b'\x91'  # If the input is 0 or 1, it is flipped. Otherwise the output will be 0.
OP_0NOTEQUAL = b'\x92'  # Returns 0 if the input is 0. 1 otherwise.
OP_ADD = b'\x93'  # a is added to b.
OP_SUB = b'\x94'  # b is subtracted from a.
OP_BOOLAND = b'\x9a'  # If both a and b are not "" (null string), the output is 1. Otherwise 0.
OP_BOOLOR = b'\x9b'  # If a or b is not "" (null string), the output is 1. Otherwise 0.
OP_NUMEQUAL = b'\x9c'  # Returns 1 if the numbers are equal, 0 otherwise.
OP_NUMEQUALVERIFY = b'\x9d'  # Same as OP_NUMEQUAL, but runs OP_VERIFY afterward.
OP_NUMNOTEQUAL = b'\x9e'  # Returns 1 if the numbers are not equal, 0 otherwise.
OP_LESSTHAN = b'\x9f'  # Returns 1 if a is less than b, 0 otherwise.
OP_GREATERTHAN = b'\xa0'  # Returns 1 if a is greater than b, 0 otherwise.
OP_LESSTHANOREQUAL = b'\xa1'  # Returns 1 if a is less than or equal to b, 0 otherwise.
OP_GREATERTHANOREQUAL = b'\xa2'  # Returns 1 if a is greater than or equal to b, 0 otherwise.
OP_MIN = b'\xa3'  # Returns the smaller of a and b.
OP_MAX = b'\xa4'  # Returns the larger of a and b.
OP_WITHIN = b'\xa5'  # Returns 1 if x is within the specified range (left-inclusive), 0 otherwise.

OP_RIPEMD160 = b'\xa6'  # The input is hashed using RIPEMD-160.
OP_SHA1 = b'\xa7'  # The input is hashed using SHA-1.
OP_SHA256 = b'\xa8'  # The input is hashed using SHA-256.
OP_HASH160 = b'\xa9'  # The input is hashed twice: first with SHA-256 and then with RIPEMD-160.
OP_HASH256 = b'\xaa'  # The input is hashed two times with SHA-256.

# All of the signature checking words will only match signatures to the data after the most
# recently-executed OP_CODESEPARATOR.
OP_CODESEPARATOR = b'\xab'

# The entire transaction's outputs, inputs, and script (from the most recently-executed
# OP_CODESEPARATOR to the end) are hashed. The signature used by OP_CHECKSIG must be a valid
# signature for this hash and public key. If it is, 1 is returned, 0 otherwise.
OP_CHECKSIG = b'\xac'

OP_CHECKSIGVERIFY = b'\xad'  # Same as OP_CHECKSIG, but OP_VERIFY is executed afterward.

# sig1 sig2 ... <number of signatures> pub1 pub2 <number of public keys>
# Compares the first signature against each public key until it finds an ECDSA match.
# Starting with the subsequent public key, it compares the second signature against each remaining
# public key until it finds an ECDSA match. The process is repeated until all signatures have been
# checked or not enough public keys remain to produce a successful result. All signatures need to
# match a public key. Because public keys are not checked again if they fail any signature
# comparison, signatures must be placed in the scriptSig using the same order as their corresponding
# public keys were placed in the scriptPubKey or redeemScript. If all signatures are valid, 1 is
# returned, 0 otherwise. Due to a bug, one extra unused value is removed from the stack.
OP_CHECKMULTISIG = b'\xae'

OP_CHECKMULTISIGVERIFY = b'\xaf'  # Same as OP_CHECKMULTISIG, but OP_VERIFY is executed afterward.

# Marks transaction as invalid if the top stack item is greater than the transaction's nLockTime
# field, otherwise script evaluation continues as though an OP_NOP was executed. Transaction is
# also invalid if 1. the stack is empty; or 2. the top stack item is negative; or 3. the top stack
# item is greater than or equal to 500000000 while the transaction's nLockTime field is less than
# 500000000, or vice versa; or 4. the input's nSequence field is equal to 0xffffffff. The precise
# semantics are described in BIP 0065.
OP_CHECKLOCKTIMEVERIFY = b'\xb1'

# scripting system to address reissuing transactions when the coins they spend have been
# conflicted/double-spent.
OP_CHECKBLOCKATHEIGHT = b'\xb4'

OP_DUP = b'\x76'  # Duplicates the top stack item.

OP_EQUAL = b'\x87'  # Returns 1 if the inputs are exactly equal, 0 otherwise.

OP_EQUALVERIFY = b'\x88'  # Same as OP_EQUAL, but runs OP_VERIFY afterward.

# The number in the word name (2-16) is pushed onto the stack. In this case 14, so 20 bytes.
OP_PUSH_20 = b'\x14'

# Marks transaction as invalid if top stack value is not true. The top stack value is removed.
OP_VERIFY = b'\x69'

# Marks transaction as invalid. A standard way of attaching extra data to transactions is to add a
# zero-value output with a scriptPubKey consisting of OP_RETURN followed by exactly one pushdata
# op. Such outputs are provably unspendable, reducing their cost to the network. Currently it is
# usually considered non-standard (though valid) for a transaction to have more than one OP_RETURN
# output or an OP_RETURN output with more than one pushdata op.
OP_RETURN = b'\x6a'
