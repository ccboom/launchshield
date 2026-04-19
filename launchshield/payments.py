"""Payment adapter — x402/Gateway style, mock-first with real provider slot."""
from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Optional, Protocol

import httpx

from .config import AppConfig, get_config
from .models import PaymentReceipt


class PaymentError(RuntimeError):
    """Raised when a micro-payment fails to submit or confirm."""


class PaymentProvider(Protocol):
    async def pay(self, *, amount_usd: float, memo: str) -> PaymentReceipt: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _mock_tx_hash(memo: str) -> str:
    seed = f"{memo}|{time.time_ns()}|{secrets.token_hex(8)}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return "0x" + digest[:40]


class MockPaymentProvider:
    """Deterministic mock — emits realistic looking receipts without network calls."""

    def __init__(self, config: AppConfig):
        self._config = config

    async def pay(self, *, amount_usd: float, memo: str) -> PaymentReceipt:
        submitted_at = _utcnow()
        await asyncio.sleep(max(0.0, self._config.demo_pace_seconds * 0.3))
        tx_hash = _mock_tx_hash(memo)
        confirmed_at = _utcnow()
        explorer_url = f"{self._config.arc_explorer_base_url.rstrip('/')}/tx/{tx_hash}"
        console_ref = f"circle-sandbox://payments/{tx_hash[-12:]}"
        return PaymentReceipt(
            provider="mock-x402",
            amount_usdc=round(amount_usd, 6),
            tx_hash=tx_hash,
            network="arc-sandbox",
            explorer_url=explorer_url,
            submitted_at=submitted_at,
            confirmed_at=confirmed_at,
            console_reference=console_ref,
        )


class X402GatewayProvider:
    """Minimal x402/Gateway style adapter. Wire once sandbox creds exist."""

    def __init__(self, config: AppConfig):
        if not config.x402_gateway_base_url or not config.x402_gateway_api_key:
            raise PaymentError(
                "x402 gateway credentials missing — set X402_GATEWAY_BASE_URL and X402_GATEWAY_API_KEY"
            )
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.x402_gateway_base_url,
            headers={
                "Authorization": f"Bearer {config.x402_gateway_api_key}",
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )

    async def pay(self, *, amount_usd: float, memo: str) -> PaymentReceipt:
        payload = {
            "amount_usd": round(amount_usd, 6),
            "currency": "USDC",
            "network": "arc-sandbox",
            "memo": memo,
            "sender": self._config.arc_wallet_address,
        }
        submitted_at = _utcnow()
        try:
            resp = await self._client.post("/v1/payments", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise PaymentError(f"payment submit failed: {exc}") from exc

        tx_hash = data.get("tx_hash") or data.get("transaction_hash")
        if not tx_hash:
            raise PaymentError("payment response missing tx_hash")

        confirmed_at = _utcnow()
        explorer_url = data.get("explorer_url") or (
            f"{self._config.arc_explorer_base_url.rstrip('/')}/tx/{tx_hash}"
        )
        console_ref = data.get("console_reference")
        return PaymentReceipt(
            provider="x402-gateway",
            amount_usdc=round(amount_usd, 6),
            tx_hash=tx_hash,
            network=data.get("network", "arc-sandbox"),
            explorer_url=explorer_url,
            submitted_at=submitted_at,
            confirmed_at=confirmed_at,
            console_reference=console_ref,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def build_provider(config: Optional[AppConfig] = None) -> PaymentProvider:
    cfg = config or get_config()
    if not cfg.use_real_payments:
        return MockPaymentProvider(cfg)

    # Prefer the direct Arc testnet path when a private key is available — that
    # is the documented Circle/Arc developer flow and produces real on-chain
    # transactions with zero extra infrastructure. Fall back to a configured
    # x402 gateway for teams that prefer a hosted payment surface.
    if cfg.arc_private_key:
        from .arc_chain import ArcTestnetPaymentProvider  # local import to keep web3 optional

        return ArcTestnetPaymentProvider(cfg)
    if cfg.x402_gateway_base_url and cfg.x402_gateway_api_key:
        return X402GatewayProvider(cfg)
    raise PaymentError(
        "USE_REAL_PAYMENTS is true but no provider is configured. "
        "Set ARC_PRIVATE_KEY for direct Arc testnet, "
        "or X402_GATEWAY_BASE_URL + X402_GATEWAY_API_KEY for a gateway."
    )
