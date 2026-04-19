"""Real Circle/Arc testnet payment provider using web3.py.

Each call submits a real ERC-20 `transfer()` against the USDC system contract on
the Arc testnet (chain id 5042002, USDC at `0x3600000000000000000000000000000000000000`,
RPC `https://rpc.testnet.arc.network`).

USDC is the native gas token on Arc, so the wallet's USDC balance pays both the
transfer value AND the gas. Sub-second finality means we can wait for receipts
inline without slowing the demo to a crawl.

If the operator does not configure `ARC_MERCHANT_ADDRESS`, the provider sends a
self-transfer (wallet -> wallet) — the transaction still lands on-chain and is
visible on the Arc Explorer, which is all the demo needs to prove "real" rails.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional

from .config import AppConfig
from .models import PaymentReceipt


# Minimal ERC-20 ABI — only the surface we touch.
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function",
    },
]


class ArcChainError(RuntimeError):
    """Raised when an Arc testnet operation fails."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _signed_raw(signed: Any) -> bytes:
    """web3.py 7.x exposes `raw_transaction`; older versions used `rawTransaction`."""
    return getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction")


class ArcTestnetPaymentProvider:
    """Submits one real USDC transfer on Arc testnet per `pay()` call."""

    def __init__(self, config: AppConfig):
        if not config.arc_private_key:
            raise ArcChainError("ARC_PRIVATE_KEY is required for real Arc payments")
        if not config.arc_rpc_url:
            raise ArcChainError("ARC_RPC_URL is required for real Arc payments")

        try:
            from web3 import Web3
            from eth_account import Account
        except ImportError as exc:  # pragma: no cover - dependency declared in requirements
            raise ArcChainError(
                "web3 is not installed; add `web3>=7.6.0,<8.0.0` to requirements"
            ) from exc

        self._cfg = config
        self._w3 = Web3(Web3.HTTPProvider(config.arc_rpc_url, request_kwargs={"timeout": 20}))
        if not self._w3.is_connected():
            raise ArcChainError(f"could not reach Arc RPC at {config.arc_rpc_url}")

        self._account = Account.from_key(config.arc_private_key)
        if (
            config.arc_wallet_address
            and config.arc_wallet_address.lower() != self._account.address.lower()
        ):
            raise ArcChainError(
                "ARC_WALLET_ADDRESS does not match the address derived from ARC_PRIVATE_KEY"
            )

        self._sender = Web3.to_checksum_address(self._account.address)
        self._merchant = Web3.to_checksum_address(
            config.arc_merchant_address or self._account.address
        )
        self._usdc = self._w3.eth.contract(
            address=Web3.to_checksum_address(config.arc_usdc_address),
            abi=ERC20_ABI,
        )

        # Cache decimals once — USDC is 6 on Arc per official docs.
        try:
            self._decimals = int(self._usdc.functions.decimals().call())
        except Exception as exc:
            raise ArcChainError(f"failed to read USDC.decimals(): {exc!r}") from exc

        self._chain_id = int(config.arc_chain_id)
        self._explorer = config.arc_explorer_base_url.rstrip("/")
        self._timeout = config.arc_tx_timeout_seconds
        self._override_amount = config.arc_payment_amount_override_usdc

        # Serialize transactions so nonces stay monotonic.
        self._lock = asyncio.Lock()

    @property
    def sender_address(self) -> str:
        return self._sender

    def usdc_balance(self) -> float:
        """Return the wallet's USDC balance in human units (e.g. 9.875)."""
        raw = self._usdc.functions.balanceOf(self._sender).call()
        return raw / (10 ** self._decimals)

    async def pay(self, *, amount_usd: float, memo: str) -> PaymentReceipt:
        amount_to_send = self._override_amount if self._override_amount is not None else amount_usd
        amount_units = max(1, int(round(amount_to_send * (10 ** self._decimals))))

        submitted_at = _utcnow()
        async with self._lock:
            try:
                tx_hash_hex, receipt = await asyncio.to_thread(
                    self._submit_and_wait, amount_units
                )
            except ArcChainError:
                raise
            except Exception as exc:  # web3 raises a wide variety of exception types
                raise ArcChainError(f"Arc tx failed: {exc!r}") from exc

        confirmed_at = _utcnow()
        block_number = getattr(receipt, "blockNumber", None)
        gas_used = getattr(receipt, "gasUsed", None)
        explorer_url = f"{self._explorer}/tx/{tx_hash_hex}"

        return PaymentReceipt(
            provider="arc-testnet",
            amount_usdc=round(amount_to_send, 6),
            tx_hash=tx_hash_hex,
            network=f"arc-testnet:{self._chain_id}",
            explorer_url=explorer_url,
            submitted_at=submitted_at,
            confirmed_at=confirmed_at,
            console_reference=(
                f"arcscan://{self._chain_id}/tx/{tx_hash_hex}"
                if block_number is not None
                else None
            ),
        )

    # ---------- internal helpers (run in a thread because web3.py is sync) ----------

    def _submit_and_wait(self, amount_units: int):
        nonce = self._w3.eth.get_transaction_count(self._sender, "pending")
        gas_price = self._w3.eth.gas_price

        try:
            gas_estimate = self._usdc.functions.transfer(
                self._merchant, amount_units
            ).estimate_gas({"from": self._sender})
        except Exception:
            gas_estimate = 80_000  # ERC-20 transfer headroom

        tx = self._usdc.functions.transfer(self._merchant, amount_units).build_transaction(
            {
                "from": self._sender,
                "nonce": nonce,
                "chainId": self._chain_id,
                "gas": int(gas_estimate * 1.2),
                "gasPrice": gas_price,
            }
        )
        signed = self._account.sign_transaction(tx)
        raw = _signed_raw(signed)
        tx_hash = self._w3.eth.send_raw_transaction(raw)
        receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=self._timeout)
        tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else str(tx_hash)
        if not tx_hash_hex.startswith("0x"):
            tx_hash_hex = "0x" + tx_hash_hex
        if getattr(receipt, "status", 0) != 1:
            raise ArcChainError(f"transaction reverted: {tx_hash_hex}")
        return tx_hash_hex, receipt

    async def aclose(self) -> None:
        # web3.HTTPProvider holds a requests.Session; closing it is best-effort.
        provider = getattr(self._w3, "provider", None)
        session = getattr(provider, "_request_session", None) if provider else None
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


def build_arc_provider(config: AppConfig) -> Optional[ArcTestnetPaymentProvider]:
    """Build the Arc provider iff credentials are present. Returns None otherwise."""
    if not config.arc_private_key:
        return None
    return ArcTestnetPaymentProvider(config)
