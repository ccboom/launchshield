"""Unit tests for pricing invariants and tier quotas."""
from __future__ import annotations

import pytest

from launchshield.models import RunMode
from launchshield.presets import CUSTOM_STANDARD, PRESET_STRESS, tier_for
from launchshield.pricing import (
    MAX_TOOL_PRICE_USD,
    TOOL_PRICES_USD,
    TRADITIONAL_GAS_PER_TX_USD,
    traditional_gas_estimate,
)


def test_every_tool_price_below_one_cent() -> None:
    assert TOOL_PRICES_USD, "pricing table must not be empty"
    for tool, price in TOOL_PRICES_USD.items():
        assert price < MAX_TOOL_PRICE_USD, f"{tool} priced at {price} must be < ${MAX_TOOL_PRICE_USD}"


def test_preset_stress_totals_sixty_three() -> None:
    assert PRESET_STRESS.total() == 63
    assert tier_for(RunMode.PRESET_STRESS).total() == 63


def test_custom_standard_totals_thirty_four() -> None:
    assert CUSTOM_STANDARD.total() == 34
    assert tier_for(RunMode.CUSTOM_STANDARD).total() == 34


@pytest.mark.parametrize("confirmed", [0, 1, 15, 63])
def test_traditional_gas_formula(confirmed: int) -> None:
    expected = round(confirmed * TRADITIONAL_GAS_PER_TX_USD, 4)
    assert traditional_gas_estimate(confirmed) == expected
