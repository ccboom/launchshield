"""Pre-flight check for the Arc testnet payment path.

Run this before flipping ``USE_REAL_PAYMENTS=true`` to confirm:

* the configured RPC is reachable,
* the wallet derived from ``ARC_PRIVATE_KEY`` matches ``ARC_WALLET_ADDRESS``,
* the wallet has enough USDC to fund a `preset-stress` run,
* (optionally) submit a single 0.001 USDC self-transfer end-to-end.

Usage::

    python scripts/check_arc_testnet.py            # read-only checks
    python scripts/check_arc_testnet.py --send     # additionally submit one tx

The script reads configuration from environment variables (and ``.env`` if
present). It exits non-zero on any failure so you can wire it into CI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/check_arc_testnet.py` from the repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from launchshield.config import AppConfig  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Arc testnet pre-flight check")
    parser.add_argument(
        "--send",
        action="store_true",
        help="Also submit a single 0.001 USDC self-transfer (consumes faucet funds).",
    )
    parser.add_argument(
        "--required-usdc",
        type=float,
        default=1.0,
        help="Minimum USDC balance to require (default: 1.0, enough for ~63 settlements).",
    )
    args = parser.parse_args()

    try:
        from launchshield.arc_chain import ArcTestnetPaymentProvider
    except Exception as exc:
        print(f"[FAIL] cannot import ArcTestnetPaymentProvider: {exc!r}")
        return 2

    cfg = AppConfig()
    print(f"RPC URL    : {cfg.arc_rpc_url}")
    print(f"Chain ID   : {cfg.arc_chain_id}")
    print(f"USDC       : {cfg.arc_usdc_address}")
    print(f"Explorer   : {cfg.arc_explorer_base_url}")
    if not cfg.arc_private_key:
        print("[FAIL] ARC_PRIVATE_KEY is not set.")
        return 1

    try:
        provider = ArcTestnetPaymentProvider(cfg)
    except Exception as exc:
        print(f"[FAIL] could not initialise provider: {exc}")
        return 1

    print(f"Wallet     : {provider.sender_address}")
    print(f"Decimals   : {provider._decimals}")  # noqa: SLF001 - intentional for diagnostics

    try:
        balance = provider.usdc_balance()
    except Exception as exc:
        print(f"[FAIL] balanceOf() failed: {exc}")
        return 1
    print(f"Balance    : {balance:.6f} USDC")

    if balance < args.required_usdc:
        print(
            f"[WARN] balance below required {args.required_usdc} USDC — "
            f"top up at https://faucet.circle.com (Network: Arc Testnet)."
        )
        return 1

    if not args.send:
        print("[OK] read-only checks passed.")
        return 0

    import asyncio

    async def _one_tx() -> int:
        receipt = await provider.pay(amount_usd=0.001, memo="launchshield:check_arc_testnet")
        print(f"[OK] tx submitted: {receipt.tx_hash}")
        print(f"     explorer    : {receipt.explorer_url}")
        await provider.aclose()
        return 0

    try:
        return asyncio.run(_one_tx())
    except Exception as exc:
        print(f"[FAIL] tx failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
