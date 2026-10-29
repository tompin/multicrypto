# Ethereum - stage 1 (library and CLI)

## Goal

Support Ethereum (ETH) and its Sepolia testnet (TETH): addresses, signed transactions sending
ether, and communication with nodes and a block explorer, without new dependencies. The GUI is
stage 2.

## Research (2026-10-29)

Keccak-256 is not `hashlib.sha3_256` (different padding byte), pycryptodome was removed with the
broken `ethaddress` module, so Keccak-256 is implemented in pure Python and checked against
`hashlib.sha3_256` using the SHA-3 padding. RLP is small enough to implement too. ECDSA with
RFC6979 and BIP-32 are already in the package.

Public JSON-RPC endpoints without an API key, checked with `eth_chainId`, `eth_getBalance`,
`eth_getTransactionCount`, `eth_feeHistory`, `eth_estimateGas` and `eth_sendRawTransaction`:

| Endpoint | Chain | Result |
| --- | --- | --- |
| ethereum-rpc.publicnode.com | mainnet | works |
| eth.drpc.org | mainnet | works |
| mainnet.gateway.tenderly.co | mainnet | works |
| rpc.mevblocker.io, rpc.flashbots.net | mainnet | work, but send transactions privately |
| 1rpc.io/eth | mainnet | unstable: worked, then HTTP 410 and rate limits (-32029) |
| eth.llamarpc.com | mainnet | Cloudflare error 525 |
| cloudflare-eth.com | mainnet | most methods fail |
| rpc.ankr.com/eth | mainnet | requires API key |
| ethereum-sepolia-rpc.publicnode.com | Sepolia | works |
| sepolia.gateway.tenderly.co | Sepolia | works, rate limited quickly (HTTP 429) |
| rpc.sepolia.ethpandaops.io | Sepolia | works |
| 1rpc.io/sepolia | Sepolia | rate limited (-32005) |
| sepolia.drpc.org | Sepolia | not on the free plan |
| rpc.sepolia.org | Sepolia | does not respond |

Block explorers:

- Blockscout (`eth.blockscout.com`, `eth-sepolia.blockscout.com`) - API v2 and Etherscan
  compatible API without a key. `/api/v2/addresses/{address}/counters` gives
  `transactions_count` (sent and received), also `"0"` for unused addresses.
- Etherscan API V2 - requires a key.
- Ethplorer - `freekey` works, but it is focused on tokens.

Nodes don't know the number of received transactions (the nonce counts only sent ones), so the
explorer is needed for the discovery of used HD addresses in stage 2.

Direct peer-to-peer connection (devp2p: RLPx with ECIES, AES-CTR, snappy and ForkID updated with
every hard fork) is not implemented, JSON-RPC to public or own node is used like in other wallets.

## Design

- `multicrypto/keccak.py`, `multicrypto/rlp.py` - primitives.
- `multicrypto/ecdsa.py` - `sign_digest` (RFC6979 with HMAC-SHA256 of the digest like
  libsecp256k1, low s from EIP-2, recovery id) and `recover_public_key` from a digest.
- `multicrypto/ethereum.py` - addresses with EIP-55 checksum, hex private keys, ether/gwei
  conversion, EIP-1559 `Transaction` with signing and `decode_transaction` (recovers the sender).
- `multicrypto/ethereum_api.py` - `EthereumRPC` trying nodes in order (connection errors, HTTP
  errors, rate limits and errors -32005, -32029, -32603 go to the next node, other errors of
  the node are raised), `BlockscoutAPI`, `suggest_fees` (next base fee from `eth_feeHistory`,
  median tip of 10 blocks, at least 0.01 gwei, max fee = 2 * base fee + tip), `prepare_transfer`
  (checks the chain id of the node and the balance) and `broadcast_transaction` ("already known"
  is not an error).
- `ethereum_coins` in `multicrypto/coins.py` is separate from `coins`, so commands and GUI tabs
  for coins with unspent outputs don't get Ethereum.
- CLI: `checkaddress` and `genaddress` (vanity, about 4000 addresses per second per core) accept
  ETH and TETH, new `sendeth` command sends ether (`--dry_run`, `--node`, fee, gas and nonce
  options). `sendcrypto` options are specific to unspent outputs, so it is not extended.

## Verification

- Keccak-256: known digests and SHA3-256 of hashlib for lengths around the block size.
- Signature: EIP-155 example (r, s and recovery id), addresses from EIP-55, address of
  `m/44'/60'/0'/0/0` of the `abandon ... about` mnemonic is the one of MetaMask.
- Live: transactions with nonce 0 signed with the private key 1 (address with sent transactions)
  were rejected with `nonce too low: next nonce 4979` (mainnet) and `998` (Sepolia) by all nodes
  of the coin definitions, so the nodes decode the transaction and recover the right sender.

## Stage 2 (GUI)

- Wallet: account group with one account `m/44'/60'/0'/0/i` (MetaMask compatible, no change
  chain), imported hex private keys.
- Balance and Send tabs for Ethereum (nonce, fees in gwei), discovery using Blockscout counters.
- Possibly EIP-191 message signing (`personal_sign`) in the Sign tab and ERC-20 tokens.
