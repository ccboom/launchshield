"""Profitability matrix calculation."""
from __future__ import annotations

from typing import Iterable

from .models import ProfitabilitySnapshot, ToolInvocation
from .pricing import traditional_gas_estimate


def compute(invocations: Iterable[ToolInvocation]) -> ProfitabilitySnapshot:
    invocations = list(invocations)
    tool_cost = sum(inv.price_usd for inv in invocations)
    settled = sum(
        inv.payment.amount_usdc
        for inv in invocations
        if inv.payment is not None and inv.payment.confirmed_at is not None
    )
    confirmed = sum(
        1
        for inv in invocations
        if inv.payment is not None and inv.payment.confirmed_at is not None
    )
    trad_gas = traditional_gas_estimate(confirmed)
    micro_signal = "profitable" if settled < trad_gas else "neutral"
    trad_signal = "bankrupt" if trad_gas >= settled else "viable"
    return ProfitabilitySnapshot(
        tool_cost_usd=round(tool_cost, 4),
        settled_usdc=round(settled, 4),
        traditional_gas_estimate_usd=round(trad_gas, 4),
        micro_model_margin_signal=micro_signal,
        traditional_model_signal=trad_signal,
    )
