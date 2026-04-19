"""Integration test — preset-stress run completes under mock providers."""
from __future__ import annotations

import asyncio
import json

import pytest

from launchshield.models import CreateRunRequest, RunMode, RunStatus
from launchshield.orchestrator import STAGES, Orchestrator


EXPECTED_STAGE_ORDER = STAGES


def _collect_events(events: list) -> list[str]:
    return [ev.type for ev in events]


@pytest.mark.asyncio
async def test_preset_stress_end_to_end() -> None:
    orchestrator = Orchestrator()
    run = orchestrator.build_run(CreateRunRequest(mode=RunMode.PRESET_STRESS))
    assert run.planned_invocations == 63

    await orchestrator.start(run)

    collected = []
    async for event in orchestrator.bus.subscribe(run.run_id):
        collected.append(event)

    types = _collect_events(collected)
    assert types[0] == "run.started"
    assert types[-1] in {"run.completed", "run.failed"}, types[-5:]
    assert types[-1] == "run.completed", types[-5:]

    assert types.count("tool.invoked") == 63
    assert types.count("payment.submitted") == 63
    assert types.count("payment.confirmed") == 63
    assert types.count("tool.completed") + types.count("tool.failed") == 63

    stage_started_order = [
        ev.payload["stage"] for ev in collected if ev.type == "stage.started"
    ]
    assert stage_started_order == EXPECTED_STAGE_ORDER

    stored = orchestrator._registry.get(run.run_id)
    assert stored is not None
    assert stored.status == RunStatus.COMPLETED
    assert stored.completed_invocations == 63
    assert stored.profitability.tool_cost_usd > 0
    assert stored.profitability.settled_usdc > 0
    assert stored.profitability.traditional_gas_estimate_usd > stored.profitability.settled_usdc

    artifacts_dir = orchestrator._registry.artifacts_dir(run.run_id)
    assert artifacts_dir.exists()
    assert (artifacts_dir / "summary.json").exists()
    assert (artifacts_dir / "invocations.json").exists()
    assert (artifacts_dir / "findings.json").exists()
    assert (artifacts_dir / "profitability.json").exists()

    invocations = json.loads((artifacts_dir / "invocations.json").read_text("utf-8"))
    assert len(invocations) == 63
    for inv in invocations:
        receipt = inv.get("payment")
        assert receipt is not None
        assert receipt.get("tx_hash", "").startswith("0x")
        assert receipt.get("explorer_url", "").startswith("http")


@pytest.mark.asyncio
async def test_custom_standard_completes_with_thirty_four() -> None:
    orchestrator = Orchestrator()
    run = orchestrator.build_run(
        CreateRunRequest(
            mode=RunMode.CUSTOM_STANDARD,
            repo_url="https://github.com/launchshield-demo/fixture",
            target_url="http://127.0.0.1:9",
        )
    )
    assert run.planned_invocations == 34

    await orchestrator.start(run)
    collected = []
    async for event in orchestrator.bus.subscribe(run.run_id):
        collected.append(event)

    assert collected[0].type == "run.started"
    assert collected[-1].type == "run.completed"

    tool_invoked = [e for e in collected if e.type == "tool.invoked"]
    assert len(tool_invoked) == 34
