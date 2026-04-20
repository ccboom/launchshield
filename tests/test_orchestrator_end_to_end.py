"""Integration coverage for orchestration under mock providers."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from launchshield import aisa as aisa_mod
from launchshield import llm as llm_mod
from launchshield.browser_runtime import PageSnapshot
from launchshield.models import (
    CreateRunRequest,
    Finding,
    FindingSeverity,
    FindingSource,
    InvocationStatus,
    PaymentReceipt,
    RunMode,
    RunStatus,
    ScanScope,
)
from launchshield.orchestrator import STAGES, Orchestrator
from launchshield.site_probes import build_probe_plan


EXPECTED_STAGE_ORDER = STAGES


def _run(coro):
    return asyncio.run(coro)


def _collect_events(events: list) -> list[str]:
    return [ev.type for ev in events]


def test_preset_stress_end_to_end() -> None:
    async def scenario() -> None:
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

    _run(scenario())


def test_custom_standard_completes_with_thirty_four() -> None:
    async def scenario() -> None:
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

    _run(scenario())


def test_custom_full_scan_updates_plan_after_repo_fetch() -> None:
    async def scenario() -> None:
        orchestrator = Orchestrator()
        run = orchestrator.build_run(
            CreateRunRequest(
                mode=RunMode.CUSTOM_STANDARD,
                scan_scope=ScanScope.FULL,
                repo_url="https://github.com/launchshield-demo/fixture",
                target_url="https://example.com",
            )
        )
        assert run.planned_invocations == 0

        await orchestrator.start(run)
        collected = []
        async for event in orchestrator.bus.subscribe(run.run_id):
            collected.append(event)

        stored = orchestrator._registry.get(run.run_id)
        assert stored is not None
        assert stored.scan_scope == ScanScope.FULL
        assert stored.planned_invocations == 59
        assert stored.planned_breakdown["file_scan"] == 25
        assert stored.planned_breakdown["dep_lookup"] == 18
        assert any(event.type == "run.plan_updated" for event in collected)
        assert len([event for event in collected if event.type == "tool.invoked"]) == 59

    _run(scenario())


class _StubPaymentProvider:
    async def pay(self, *, amount_usd: float, memo: str) -> PaymentReceipt:
        now = datetime.now(timezone.utc)
        return PaymentReceipt(
            provider="stub",
            amount_usdc=amount_usd,
            tx_hash="0x1234567890abcdef1234567890abcdef12345678",
            network="arc-sandbox",
            explorer_url="https://example.com/tx/0x123",
            submitted_at=now,
            confirmed_at=now,
            console_reference=f"stub://{memo}",
        )


class _RecordingPaymentProvider(_StubPaymentProvider):
    def __init__(self, events: list[str]):
        self._events = events

    async def pay(self, *, amount_usd: float, memo: str) -> PaymentReceipt:
        self._events.append(f"pay:{memo}")
        return await super().pay(amount_usd=amount_usd, memo=memo)


class _ExplodingBrowser:
    async def fetch(self, url: str):
        raise RuntimeError("browser unavailable")

    async def probe_path(self, base_url: str, path: str) -> int:
        raise AssertionError("probe_path should not run after fetch failure")


class _RecordingBrowser:
    def __init__(self, events: list[str]):
        self._events = events

    async def fetch(self, url: str) -> PageSnapshot:
        self._events.append(f"browser:fetch:{url}")
        return PageSnapshot(
            url=url,
            status_code=200,
            headers={},
            html="<html></html>",
            inline_scripts=[],
            has_password_field=False,
            next_data_present=False,
            mixed_content=False,
            admin_like_links=[],
        )

    async def probe_path(self, base_url: str, path: str) -> int:
        self._events.append(f"browser:probe:{path}")
        return 404


class _RetryingLLMProvider:
    def __init__(self, *, fail_deep_once: bool = False, fail_fix_once: bool = False):
        self.fail_deep_once = fail_deep_once
        self.fail_fix_once = fail_fix_once
        self.deep_calls = 0
        self.fix_calls = 0

    async def deep_analysis(self, req: llm_mod.DeepAnalysisInput) -> llm_mod.DeepAnalysisResult:
        self.deep_calls += 1
        if self.fail_deep_once and self.deep_calls == 1:
            raise RuntimeError("transient deep analysis failure")
        return llm_mod.DeepAnalysisResult(
            risk_summary="deep risk summary",
            exploit_path="deep exploit path",
            impact_scope="deep impact scope",
            remediation_direction="deep remediation direction",
        )

    async def fix_suggestion(self, req: llm_mod.FixSuggestionInput) -> llm_mod.FixSuggestionResult:
        self.fix_calls += 1
        if self.fail_fix_once and self.fix_calls == 1:
            raise RuntimeError("transient fix suggestion failure")
        return llm_mod.FixSuggestionResult(
            why="because",
            patch_summary="patch summary",
            suggested_code_change="patch code",
            validation_steps="validation",
        )


class _RetryingAisaProvider:
    def __init__(self):
        self.calls = 0

    async def verify(self, subject: str, category: str) -> aisa_mod.AisaVerification:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient aisa failure")
        return aisa_mod.AisaVerification(
            match_level="strong",
            intel_summary="aisa summary",
            recommended_priority="immediate",
        )


def _seed_high_finding() -> Finding:
    return Finding(
        finding_id="fnd_seed",
        source=FindingSource.FILE_SCAN,
        severity=FindingSeverity.CRITICAL,
        title="dangerous_eval in src/app.py",
        summary="seed finding",
        evidence="src/app.py:10 - eval(user_input)",
        recommendation="replace eval",
        related_invocation_ids=["inv_seed"],
    )


def test_failed_invocation_increments_completed_count() -> None:
    async def scenario() -> None:
        orchestrator = Orchestrator()
        run = orchestrator.build_run(
            CreateRunRequest(
                mode=RunMode.CUSTOM_STANDARD,
                repo_url="https://github.com/launchshield-demo/fixture",
                target_url="http://127.0.0.1:9",
            )
        )

        invocation = await orchestrator._begin_invocation(
            run,
            stage="repo.file_scan",
            tool_name="file_scan",
            target="src/app.py",
        )
        await orchestrator._fail_invocation(run, invocation, "boom")

        assert run.completed_invocations == 1
        assert invocation.status == InvocationStatus.FAILED

    _run(scenario())


def test_site_probe_stage_marks_probe_failures_visible() -> None:
    async def scenario() -> None:
        orchestrator = Orchestrator()
        run = orchestrator.build_run(
            CreateRunRequest(
                mode=RunMode.CUSTOM_STANDARD,
                repo_url="https://github.com/launchshield-demo/fixture",
                target_url="http://127.0.0.1:9",
            )
        )

        await orchestrator._stage_site_probes(
            run,
            plans=build_probe_plan(run.target_url, 2),
            browser=_ExplodingBrowser(),
            payment_provider=_StubPaymentProvider(),
        )

        assert run.completed_invocations == 2
        assert len(run.tool_invocations) == 2
        assert all(inv.status == InvocationStatus.FAILED for inv in run.tool_invocations)
        assert "site probe error" in (run.error_message or "")

    _run(scenario())


def test_site_probe_stage_pays_before_browser_actions() -> None:
    async def scenario() -> None:
        events: list[str] = []
        orchestrator = Orchestrator()
        run = orchestrator.build_run(
            CreateRunRequest(
                mode=RunMode.CUSTOM_STANDARD,
                repo_url="https://github.com/launchshield-demo/fixture",
                target_url="https://example.com",
            )
        )

        await orchestrator._stage_site_probes(
            run,
            plans=build_probe_plan(run.target_url, 2),
            browser=_RecordingBrowser(events),
            payment_provider=_RecordingPaymentProvider(events),
        )

        assert events[0].startswith("pay:")
        assert len([event for event in events if event.startswith("pay:")]) == 2
        assert len(run.tool_invocations) == 2

    _run(scenario())


def test_deep_analysis_retries_once_then_succeeds() -> None:
    async def scenario() -> None:
        orchestrator = Orchestrator()
        run = orchestrator.build_run(
            CreateRunRequest(
                mode=RunMode.CUSTOM_STANDARD,
                repo_url="https://github.com/launchshield-demo/fixture",
                target_url="http://127.0.0.1:9",
            )
        )
        run.findings.append(_seed_high_finding())

        provider = _RetryingLLMProvider(fail_deep_once=True)
        await orchestrator._stage_deep_analysis(
            run,
            quota=1,
            llm_provider=provider,
            payment_provider=_StubPaymentProvider(),
        )

        assert provider.deep_calls == 2
        assert run.tool_invocations[-1].status == InvocationStatus.COMPLETED
        assert run.findings[-1].source == FindingSource.DEEP_ANALYSIS

    _run(scenario())


def test_fix_suggestion_retries_once_then_succeeds() -> None:
    async def scenario() -> None:
        orchestrator = Orchestrator()
        run = orchestrator.build_run(
            CreateRunRequest(
                mode=RunMode.CUSTOM_STANDARD,
                repo_url="https://github.com/launchshield-demo/fixture",
                target_url="http://127.0.0.1:9",
            )
        )
        run.findings.append(_seed_high_finding())

        provider = _RetryingLLMProvider(fail_fix_once=True)
        await orchestrator._stage_fix_suggestions(
            run,
            quota=1,
            llm_provider=provider,
            payment_provider=_StubPaymentProvider(),
        )

        assert provider.deep_calls == 1
        assert provider.fix_calls == 2
        assert run.tool_invocations[-1].status == InvocationStatus.COMPLETED
        assert run.findings[-1].source == FindingSource.FIX_SUGGESTION

    _run(scenario())


def test_aisa_verify_retries_once_then_succeeds() -> None:
    async def scenario() -> None:
        orchestrator = Orchestrator()
        run = orchestrator.build_run(
            CreateRunRequest(
                mode=RunMode.CUSTOM_STANDARD,
                repo_url="https://github.com/launchshield-demo/fixture",
                target_url="http://127.0.0.1:9",
            )
        )
        run.findings.append(_seed_high_finding())

        provider = _RetryingAisaProvider()
        await orchestrator._stage_aisa_verify(
            run,
            quota=1,
            aisa_provider=provider,
            payment_provider=_StubPaymentProvider(),
        )

        assert provider.calls == 2
        assert run.tool_invocations[-1].status == InvocationStatus.COMPLETED
        assert run.findings[-1].source == FindingSource.AISA_VERIFY

    _run(scenario())
