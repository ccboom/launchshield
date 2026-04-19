# Arc Testnet Wiring — LaunchShield Swarm

This note covers everything you need to flip LaunchShield Swarm from the mock
payment provider to **real USDC transfers on the Circle Arc testnet** (chain id
`5042002`). The rails are the ones documented at
[docs.arc.network](https://docs.arc.network).

## Why Arc?

On Arc, USDC is the native gas token. A single balance pays both the transfer
value and the gas. Block finality is sub-second, so a 63-invocation preset run
finishes in under a minute even while awaiting each receipt inline.

| Parameter | Value |
| --- | --- |
| RPC URL | `https://rpc.testnet.arc.network` |
| Chain ID | `5042002` |
| USDC contract | `0x3600000000000000000000000000000000000000` (system contract) |
| Explorer | `https://testnet.arcscan.app` |
| Faucet | `https://faucet.circle.com` (network: *Arc Testnet*) |
| Reference gas | ~`$0.009` per ERC-20 transfer |

## One-time setup

```powershell
# 1) Install Foundry to get `cast`.
iwr https://foundry.paradigm.xyz | iex
foundryup

# 2) Generate a wallet (never reuse a mainnet key!).
cast wallet new
# => Address: 0x...
#    Private key: 0x...

# 3) Fund it at https://faucet.circle.com (network: Arc Testnet).
#    The faucet pays 10 USDC per request; one request is enough for ~1,100 demo
#    invocations with the default per-call prices.

# 4) Write the credentials into .env (never commit this file):
Copy-Item .env.example .env
# edit .env and set ARC_PRIVATE_KEY=0x...
```

## Pre-flight check (read-only)

```powershell
.\.venv\Scripts\python.exe scripts\check_arc_testnet.py
```

Expected output:

```
RPC URL    : https://rpc.testnet.arc.network
Chain ID   : 5042002
USDC       : 0x3600000000000000000000000000000000000000
Explorer   : https://testnet.arcscan.app
Wallet     : 0x...
Decimals   : 6
Balance    : 10.000000 USDC
[OK] read-only checks passed.
```

## One live transfer (burns ~$0.009 of faucet funds)

```powershell
.\.venv\Scripts\python.exe scripts\check_arc_testnet.py --send
```

The script submits a single 0.001 USDC self-transfer and prints the resulting
explorer URL. Open it in a browser — you should see the transaction in an Arc
testnet block within ~1 second.

## Flip the app to real payments

```powershell
# .env
USE_REAL_PAYMENTS=true
ARC_PRIVATE_KEY=0x...

# Optional: stretch faucet funds by fixing every transfer at 0.001 USDC
# (the UI still displays the tool's list price for accuracy).
ARC_PAYMENT_AMOUNT_OVERRIDE_USDC=0.001
```

Restart uvicorn. Click **Execute & Stress Test** — every row in the Streaming
Billing panel will now be a real Arc transaction. Each `0x…` link goes to
`https://testnet.arcscan.app/tx/<hash>`.

## Budget math for one preset run

* 63 invocations × listed prices ≈ `$0.152` of value transferred.
* 63 transactions × ~`$0.009` gas ≈ `$0.57` of USDC burned as gas.
* Total burn per full preset run: **~$0.72 USDC**.
* One faucet request (10 USDC) covers **~13 preset runs**.

If you plan to do many back-to-back recordings, either request the faucet
multiple times or set `ARC_PAYMENT_AMOUNT_OVERRIDE_USDC=0.0001` to drop the
per-call value to near zero (gas still costs ~$0.009).

## Troubleshooting

* **`could not reach Arc RPC`** — check VPN/firewall; confirm
  `https://rpc.testnet.arc.network` responds with a JSON-RPC body.
* **`insufficient funds`** — the wallet ran out of USDC. Re-fund at
  `https://faucet.circle.com`.
* **`transaction reverted`** — happens if a previous tx with the same nonce
  landed first. The provider serialises requests via an `asyncio.Lock`, so this
  should be rare. Simply restart the run.
* **Slow receipts** — Arc commits in ~1 s, but the RPC can throttle during
  bursts. Increase `ARC_TX_TIMEOUT_SECONDS` if needed.
