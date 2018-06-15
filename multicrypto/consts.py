# An empty array of bytes is pushed onto the stack.
# This is not a no-op: an item is added to the stack.
OP_0 = b'\x00'

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

# The entire transaction's outputs, inputs, and script (from the most recently-executed
# OP_CODESEPARATOR to the end) are hashed. The signature used by OP_CHECKSIG must be a valid
# signature for this hash and public key. If it is, 1 is returned, 0 otherwise.
OP_CHECKSIG = b'\xac'

OP_DUP = b'v'  # Duplicates the top stack item.

OP_EQUAL = b'\x87'  # Returns 1 if the inputs are exactly equal, 0 otherwise.

OP_EQUALVERIFY = b'\x88'  # Same as OP_EQUAL, but runs OP_VERIFY afterward.

OP_HASH160 = b'\xa9'  # The input is hashed twice: first with SHA-256 and then with RIPEMD-160.

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
