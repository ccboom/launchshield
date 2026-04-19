"""Fixed pricing matrix for every tool. All prices MUST be < $0.01."""
from __future__ import annotations

from typing import Dict

TOOL_PRICES_USD: Dict[str, float] = {
    "file_scan": 0.001,
    "dep_lookup": 0.002,
    "site_probe": 0.003,
    "deep_analysis": 0.005,
    "aisa_verify": 0.005,
    "fix_suggestion": 0.008,
}

MAX_TOOL_PRICE_USD = 0.01

TRADITIONAL_GAS_PER_TX_USD = 0.05


def price_for(tool_name: str) -> float:
    if tool_name not in TOOL_PRICES_USD:
        raise KeyError(f"unknown tool: {tool_name}")
    return TOOL_PRICES_USD[tool_name]


def traditional_gas_estimate(confirmed_payments: int) -> float:
    return round(confirmed_payments * TRADITIONAL_GAS_PER_TX_USD, 4)


def assert_prices_valid() -> None:
    for name, price in TOOL_PRICES_USD.items():
        if price >= MAX_TOOL_PRICE_USD:
            raise AssertionError(f"price {price} for {name} is not below {MAX_TOOL_PRICE_USD}")


assert_prices_valid()
