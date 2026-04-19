"""Unit tests for the Arc testnet payment provider.

These tests do NOT hit the real RPC. They patch web3.py so the wiring
(amount conversion, nonce management, receipt construction, ABI usage,
checksum derivation) can be verified offline.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import types
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from launchshield import arc_chain as arc_chain_mod
from launchshield import payments as payments_mod
from launchshield.config import AppConfig


# Deterministic test key (Hardhat default account #0). NEVER use in production.
_TEST_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
_TEST_ADDRESS = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
_TEST_USDC = "0x3600000000000000000000000000000000000000"


class _FakeContractFunction:
    def __init__(self, return_value: Any):
        self._return_value = return_value

    def call(self) -> Any:
        return self._return_value

    def estimate_gas(self, _params: Dict[str, Any]) -> int:
        return 65_000

    def build_transaction(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"to": _TEST_USDC, **params, "data": "0xa9059cbb"}


class _FakeContractFunctions:
    def __init__(self, *, decimals: int = 6, balance: int = 10_000_000):
        self._decimals = decimals
        self._balance = balance

    def decimals(self) -> _FakeContractFunction:
        return _FakeContractFunction(self._decimals)

    def balanceOf(self, _addr: str) -> _FakeContractFunction:
        return _FakeContractFunction(self._balance)

    def transfer(self, _to: str, _amount: int) -> _FakeContractFunction:
        return _FakeContractFunction(True)


class _FakeContract:
    def __init__(self):
        self.functions = _FakeContractFunctions()


class _FakeReceipt:
    status = 1
    blockNumber = 12345
    gasUsed = 51_000


class _FakeEth:
    def __init__(self, contract: _FakeContract):
        self._contract = contract
        self.gas_price = 1_000_000_000
        self.sent_raw_txs: list[bytes] = []
        self._next_nonce = 7

    def contract(self, address: str, abi: Any):  # noqa: D401, ANN001
        assert address == _TEST_USDC
        return self._contract

    def get_transaction_count(self, _addr: str, _state: str = "latest") -> int:
        return self._next_nonce

    def send_raw_transaction(self, raw: bytes) -> bytes:
        self.sent_raw_txs.append(raw)
        # Return a 32-byte fake hash that web3 will expose with .hex()
        return b"\xab" * 32

    def wait_for_transaction_receipt(self, _tx_hash: bytes, timeout: int = 60) -> _FakeReceipt:
        return _FakeReceipt()


class _FakeWeb3:
    HTTPProvider = staticmethod(lambda url, request_kwargs=None: ("http", url))

    @staticmethod
    def to_checksum_address(addr: str) -> str:
        # Trust the test inputs; real web3 does proper EIP-55 casing.
        return addr

    def __init__(self, _provider):
        self._contract = _FakeContract()
        self.eth = _FakeEth(self._contract)
        self.provider = types.SimpleNamespace(_request_session=None)

    def is_connected(self) -> bool:
        return True


class _FakeAccount:
    def __init__(self, address: str):
        self.address = address

    def sign_transaction(self, tx: Dict[str, Any]):
        # Return an object with raw_transaction (web3.py 7.x style)
        return types.SimpleNamespace(raw_transaction=b"\x01raw" + str(tx["nonce"]).encode())


@pytest.fixture
def arc_modules(monkeypatch: pytest.MonkeyPatch):
    """Patch web3 + eth_account inside arc_chain for offline tests."""
    fake_web3_module = types.SimpleNamespace(Web3=_FakeWeb3)
    fake_eth_account_module = types.SimpleNamespace(
        Account=types.SimpleNamespace(from_key=lambda _key: _FakeAccount(_TEST_ADDRESS))
    )

    monkeypatch.setitem(sys.modules, "web3", fake_web3_module)
    monkeypatch.setitem(sys.modules, "eth_account", fake_eth_account_module)

    # arc_chain imports web3/eth_account lazily inside __init__, so no reload needed.
    yield arc_chain_mod


def _make_config(monkeypatch: pytest.MonkeyPatch) -> AppConfig:
    monkeypatch.setenv("USE_REAL_PAYMENTS", "true")
    monkeypatch.setenv("ARC_PRIVATE_KEY", _TEST_PRIVATE_KEY)
    monkeypatch.setenv("ARC_WALLET_ADDRESS", _TEST_ADDRESS)
    monkeypatch.setenv("ARC_USDC_ADDRESS", _TEST_USDC)
    monkeypatch.setenv("ARC_CHAIN_ID", "5042002")
    monkeypatch.setenv("ARC_RPC_URL", "https://rpc.testnet.arc.network")
    monkeypatch.setenv("ARC_EXPLORER_BASE_URL", "https://testnet.arcscan.app")
    monkeypatch.setenv("ARC_TX_TIMEOUT_SECONDS", "10")
    return AppConfig()


def test_provider_constructs_with_only_private_key(monkeypatch, arc_modules) -> None:
    cfg = _make_config(monkeypatch)
    provider = arc_chain_mod.ArcTestnetPaymentProvider(cfg)
    assert provider.sender_address == _TEST_ADDRESS
    assert provider._decimals == 6
    assert provider.usdc_balance() == 10.0


def test_pay_returns_real_looking_receipt(monkeypatch, arc_modules) -> None:
    cfg = _make_config(monkeypatch)
    provider = arc_chain_mod.ArcTestnetPaymentProvider(cfg)
    receipt = asyncio.run(provider.pay(amount_usd=0.005, memo="unit-test"))

    assert receipt.provider == "arc-testnet"
    assert receipt.amount_usdc == 0.005
    assert receipt.tx_hash.startswith("0x")
    assert len(receipt.tx_hash) == 66  # 0x + 64 hex chars
    assert receipt.network == "arc-testnet:5042002"
    assert receipt.explorer_url == f"https://testnet.arcscan.app/tx/{receipt.tx_hash}"
    assert receipt.confirmed_at is not None


def test_amount_override_takes_precedence(monkeypatch, arc_modules) -> None:
    monkeypatch.setenv("ARC_PAYMENT_AMOUNT_OVERRIDE_USDC", "0.0005")
    cfg = _make_config(monkeypatch)
    provider = arc_chain_mod.ArcTestnetPaymentProvider(cfg)
    receipt = asyncio.run(provider.pay(amount_usd=0.999, memo="override"))
    assert receipt.amount_usdc == 0.0005


def test_build_provider_picks_arc_when_real_payments_enabled(monkeypatch, arc_modules) -> None:
    cfg = _make_config(monkeypatch)
    provider = payments_mod.build_provider(cfg)
    assert isinstance(provider, arc_chain_mod.ArcTestnetPaymentProvider)


def test_build_provider_raises_without_creds_when_real_enabled(monkeypatch) -> None:
    monkeypatch.setenv("USE_REAL_PAYMENTS", "true")
    monkeypatch.delenv("ARC_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("X402_GATEWAY_BASE_URL", raising=False)
    monkeypatch.delenv("X402_GATEWAY_API_KEY", raising=False)
    cfg = AppConfig()
    with pytest.raises(payments_mod.PaymentError):
        payments_mod.build_provider(cfg)


def test_build_provider_returns_mock_when_real_disabled(monkeypatch) -> None:
    monkeypatch.setenv("USE_REAL_PAYMENTS", "false")
    cfg = AppConfig()
    provider = payments_mod.build_provider(cfg)
    assert isinstance(provider, payments_mod.MockPaymentProvider)


def test_wallet_address_mismatch_is_rejected(monkeypatch, arc_modules) -> None:
    cfg = _make_config(monkeypatch)
    monkeypatch.setenv("ARC_WALLET_ADDRESS", "0x0000000000000000000000000000000000000001")
    cfg2 = AppConfig()
    with pytest.raises(arc_chain_mod.ArcChainError):
        arc_chain_mod.ArcTestnetPaymentProvider(cfg2)
