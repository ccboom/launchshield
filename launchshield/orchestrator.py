"""Orchestrate a scan run: emit SSE events, submit payments, call scanners."""
from __future__ import annotations

import asyncio
import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, List, Optional

from . import aisa as aisa_mod
from . import llm as llm_mod
from . import payments as payments_mod
from . import profitability as profitability_mod
from . import repo_source as repo_source_mod
from .browser_runtime import BrowserRuntime
from .config import AppConfig, get_config
from .dep_check import lookup_vuln, parse_manifests
from .events import StreamEvent, make_event
from .models import (
    CreateRunRequest,
    Finding,
    FindingSeverity,
    FindingSource,
    InvocationStatus,
    PaymentReceipt,
    ProfitabilitySnapshot,
    RunMode,
    RunStatus,
    ScanRun,
    ToolInvocation,
)
from .presets import tier_for
from .pricing import price_for
from .repo_scan import FileMatch, scan_file
from .repo_source import RepoFile, RepoSource, priority_sort
from .site_probes import ProbeFinding, collect_site_findings
from .storage import RunRegistry, get_registry

STAGES = [
    "repo.fetch",
    "repo.file_scan",
    "repo.dep_lookup",
    "site.browser_probes",
    "analysis.deep_review",
    "analysis.aisa_verify",
    "analysis.fix_suggestions",
    "summary.profitability",
    "summary.finalize",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_run_id() -> str:
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    stamp = _utcnow().strftime("%Y%m%d")
    return f"run_{stamp}_{suffix}"


def _new_finding_id() -> str:
    return "fnd_" + uuid.uuid4().hex[:10]


def _new_invocation_id() -> str:
    return "inv_" + uuid.uuid4().hex[:10]


class EventBus:
    """Fan-out event broker scoped per run."""

    def __init__(self) -> None:
        self._subs: Dict[str, List[asyncio.Queue[StreamEvent]]] = {}
        self._done: Dict[str, asyncio.Event] = {}
        self._buffer: Dict[str, List[StreamEvent]] = {}
        self._lock = asyncio.Lock()

    async def ensure_channel(self, run_id: str) -> None:
        async with self._lock:
            self._subs.setdefault(run_id, [])
            self._done.setdefault(run_id, asyncio.Event())
            self._buffer.setdefault(run_id, [])

    async def publish(self, event: StreamEvent) -> None:
        run_id = event.run_id
        await self.ensure_channel(run_id)
        async with self._lock:
            self._buffer[run_id].append(event)
            listeners = list(self._subs[run_id])
        for queue in listeners:
            await queue.put(event)

    async def close(self, run_id: str) -> None:
        await self.ensure_channel(run_id)
        async with self._lock:
            self._done[run_id].set()
            listeners = list(self._subs[run_id])
        for queue in listeners:
            await queue.put(None)  # sentinel

    async def subscribe(self, run_id: str) -> AsyncIterator[StreamEvent]:
        await self.ensure_channel(run_id)
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            backlog = list(self._buffer[run_id])
            self._subs[run_id].append(queue)
            done = self._done[run_id]
        try:
            for event in backlog:
                yield event
            while True:
                if done.is_set() and queue.empty():
                    return
                item = await queue.get()
                if item is None:
                    return
                yield item
        finally:
            async with self._lock:
                if queue in self._subs.get(run_id, []):
                    self._subs[run_id].remove(queue)


@dataclass
class _InvocationContext:
    stage: str
    tool_name: str
    target: str


class Orchestrator:
    """Run manager that owns the event bus and background tasks."""

    def __init__(
        self,
        *,
        config: Optional[AppConfig] = None,
        registry: Optional[RunRegistry] = None,
    ) -> None:
        self._config = config or get_config()
        self._registry = registry or get_registry()
        self._bus = EventBus()
        self._tasks: Dict[str, asyncio.Task] = {}

    @property
    def bus(self) -> EventBus:
        return self._bus

    def build_run(self, request: CreateRunRequest) -> ScanRun:
        if request.mode == RunMode.PRESET_STRESS:
            repo_url = self._config.preset_repo_url
            target_url = self._config.preset_target_url
        else:
            if not request.repo_url or not request.target_url:
                raise ValueError("custom-standard requires repo_url and target_url")
            repo_url = request.repo_url
            target_url = request.target_url

        tier = tier_for(request.mode)
        run = ScanRun(
            run_id=_new_run_id(),
            mode=request.mode,
            status=RunStatus.QUEUED,
            repo_url=repo_url,
            target_url=target_url,
            planned_invocations=tier.total(),
        )
        self._registry.save(run)
        return run

    async def start(self, run: ScanRun) -> None:
        await self._bus.ensure_channel(run.run_id)
        task = asyncio.create_task(self._run_entry(run.run_id), name=f"orchestrate:{run.run_id}")
        self._tasks[run.run_id] = task

    async def _run_entry(self, run_id: str) -> None:
        try:
            await self._execute(run_id)
        except Exception as exc:  # pragma: no cover - defensive
            run = self._registry.get(run_id)
            if run:
                run.status = RunStatus.FAILED
                run.error_message = f"orchestrator crashed: {exc!r}"
                run.completed_at = _utcnow()
                self._registry.save(run)
            await self._bus.publish(make_event("run.failed", run_id, reason=repr(exc)))
        finally:
            await self._bus.close(run_id)

    async def _execute(self, run_id: str) -> None:
        run = self._registry.get(run_id)
        if run is None:
            raise RuntimeError(f"run missing: {run_id}")

        run.status = RunStatus.RUNNING
        run.started_at = _utcnow()
        self._registry.save(run)
        await self._bus.publish(
            make_event(
                "run.started",
                run_id,
                mode=run.mode.value,
                repo_url=run.repo_url,
                target_url=run.target_url,
                planned_invocations=run.planned_invocations,
                stages=STAGES,
            )
        )

        tier = tier_for(run.mode)
        payment_provider = payments_mod.build_provider(self._config)
        llm_provider = llm_mod.build_provider(self._config)
        aisa_provider = aisa_mod.build_provider(self._config)
        repo_provider = repo_source_mod.build_provider(self._config)
        browser = BrowserRuntime(self._config)

        try:
            # Stage 0: repo.fetch (preparation only, no billable invocations)
            await self._stage_started(run_id, "repo.fetch")
            try:
                files = await repo_provider.list_files(run.repo_url)
                manifests = await repo_provider.list_manifests(run.repo_url)
            except Exception as exc:
                await self._fail_run(run, f"repo fetch failed: {exc!r}")
                return
            await self._stage_completed(run_id, "repo.fetch", files=len(files), manifests=len(manifests))

            await self._stage_file_scan(run, tier.file_scan, files, repo_provider, payment_provider)
            await self._stage_dep_lookup(run, tier.dep_lookup, manifests, payment_provider)
            await self._stage_site_probes(run, tier.site_probe, browser, payment_provider)
            await self._stage_deep_analysis(run, tier.deep_analysis, llm_provider, payment_provider)
            await self._stage_aisa_verify(run, tier.aisa_verify, aisa_provider, payment_provider)
            await self._stage_fix_suggestions(run, tier.fix_suggestion, llm_provider, payment_provider)
            await self._stage_profitability(run)
            await self._stage_finalize(run)

        finally:
            try:
                await browser.aclose()
            except Exception:
                pass
            closer = getattr(payment_provider, "aclose", None)
            if callable(closer):
                try:
                    await closer()
                except Exception:
                    pass
            closer_aisa = getattr(aisa_provider, "aclose", None)
            if callable(closer_aisa):
                try:
                    await closer_aisa()
                except Exception:
                    pass

    # ---------- stage implementations ----------

    async def _stage_file_scan(
        self,
        run: ScanRun,
        quota: int,
        files: List[str],
        repo_provider: RepoSource,
        payment_provider,
    ) -> None:
        stage = "repo.file_scan"
        await self._stage_started(run.run_id, stage, quota=quota)

        chosen = priority_sort(files)[:quota]
        while len(chosen) < quota and files:
            chosen.append(files[(len(chosen)) % len(files)])

        for target_path in chosen[:quota]:
            invocation = await self._begin_invocation(
                run, stage=stage, tool_name="file_scan", target=target_path
            )
            await self._submit_payment(run, invocation, payment_provider, memo=f"file_scan:{target_path}")
            if invocation.status == InvocationStatus.FAILED:
                continue

            try:
                repo_file = await repo_provider.read_file(run.repo_url, target_path)
                matches = scan_file(repo_file.path, repo_file.language, repo_file.content)
            except Exception as exc:
                await self._fail_invocation(run, invocation, f"read/scan error: {exc!r}")
                continue

            if matches:
                summary = f"{len(matches)} rule match(es) in {target_path}"
            else:
                summary = f"clean — no rule hits in {target_path}"

            created: List[Finding] = []
            for match in matches[:2]:  # cap noise per file
                finding = Finding(
                    finding_id=_new_finding_id(),
                    source=FindingSource.FILE_SCAN,
                    severity=match.severity,
                    title=f"{match.rule} in {match.path}",
                    summary=f"Rule `{match.rule}` triggered at {match.path}:{match.line}.",
                    evidence=f"{match.path}:{match.line} — {match.snippet}",
                    recommendation="Review and remediate per rule guidance.",
                    related_invocation_ids=[invocation.invocation_id],
                )
                created.append(finding)
            await self._complete_invocation(run, invocation, summary=summary, findings=created)

        await self._stage_completed(run.run_id, stage, completed=quota)

    async def _stage_dep_lookup(
        self,
        run: ScanRun,
        quota: int,
        manifests: List[RepoFile],
        payment_provider,
    ) -> None:
        stage = "repo.dep_lookup"
        await self._stage_started(run.run_id, stage, quota=quota)

        deps = parse_manifests(manifests)
        if not deps:
            deps = [None] * quota  # type: ignore[list-item]

        for i in range(quota):
            dep = deps[i % max(1, len(deps))] if deps else None
            target = f"{dep.ecosystem}:{dep.name}@{dep.version}" if dep else "empty-manifest"
            invocation = await self._begin_invocation(
                run, stage=stage, tool_name="dep_lookup", target=target
            )
            await self._submit_payment(run, invocation, payment_provider, memo=f"dep_lookup:{target}")
            if invocation.status == InvocationStatus.FAILED:
                continue

            created: List[Finding] = []
            summary = f"no advisory match for {target}"
            if dep is not None:
                vuln = lookup_vuln(dep)
                if vuln is not None:
                    summary = f"{vuln.advisory_id} matches {dep.name}@{dep.version}"
                    finding = Finding(
                        finding_id=_new_finding_id(),
                        source=FindingSource.DEP_LOOKUP,
                        severity=vuln.severity,
                        title=f"Vulnerable dependency: {vuln.name}",
                        summary=vuln.summary,
                        evidence=f"{dep.manifest_path} pins {dep.name}=={dep.version} — {vuln.advisory_id}",
                        recommendation=f"Upgrade {vuln.name} to {vuln.fixed_in}.",
                        related_invocation_ids=[invocation.invocation_id],
                    )
                    created.append(finding)
            await self._complete_invocation(run, invocation, summary=summary, findings=created)

        await self._stage_completed(run.run_id, stage, completed=quota)

    async def _stage_site_probes(
        self,
        run: ScanRun,
        quota: int,
        browser: BrowserRuntime,
        payment_provider,
    ) -> None:
        stage = "site.browser_probes"
        await self._stage_started(run.run_id, stage, quota=quota)

        try:
            probe_findings = await collect_site_findings(browser, run.target_url, limit=quota)
        except Exception as exc:
            probe_findings = []
            # don't fail the whole run — surface as transient
            run.error_message = (run.error_message or "") + f" site probe error: {exc!r};"

        for i in range(quota):
            probe: Optional[ProbeFinding] = probe_findings[i] if i < len(probe_findings) else None
            target = probe.target if probe else f"{run.target_url}#probe-{i+1}"
            invocation = await self._begin_invocation(
                run, stage=stage, tool_name="site_probe", target=target
            )
            await self._submit_payment(run, invocation, payment_provider, memo=f"site_probe:{target}")
            if invocation.status == InvocationStatus.FAILED:
                continue

            created: List[Finding] = []
            if probe:
                summary = f"{probe.probe} flagged {target}"
                finding = Finding(
                    finding_id=_new_finding_id(),
                    source=FindingSource.SITE_PROBE,
                    severity=probe.severity,
                    title=probe.title,
                    summary=probe.summary,
                    evidence=probe.evidence,
                    recommendation="Review site probe evidence and apply standard hardening.",
                    related_invocation_ids=[invocation.invocation_id],
                )
                created.append(finding)
            else:
                summary = f"probe passed on {target}"
            await self._complete_invocation(run, invocation, summary=summary, findings=created)

        await self._stage_completed(run.run_id, stage, completed=quota)

    async def _stage_deep_analysis(
        self,
        run: ScanRun,
        quota: int,
        llm_provider,
        payment_provider,
    ) -> None:
        stage = "analysis.deep_review"
        await self._stage_started(run.run_id, stage, quota=quota)

        high_candidates = [
            f for f in run.findings
            if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        ][:quota]

        for i in range(quota):
            target_finding = high_candidates[i] if i < len(high_candidates) else None
            target = target_finding.finding_id if target_finding else f"synthetic-high-{i+1}"
            invocation = await self._begin_invocation(
                run, stage=stage, tool_name="deep_analysis", target=target
            )
            await self._submit_payment(run, invocation, payment_provider, memo=f"deep_analysis:{target}")
            if invocation.status == InvocationStatus.FAILED:
                continue

            created: List[Finding] = []
            try:
                rule = _rule_from_finding(target_finding)
                language = "python"
                snippet = target_finding.evidence if target_finding else "synthetic snippet"
                analysis = await llm_provider.deep_analysis(
                    llm_mod.DeepAnalysisInput(
                        snippet=snippet,
                        rule=rule,
                        language=language,
                        evidence=target_finding.evidence if target_finding else "synthetic",
                    )
                )
                summary = analysis.risk_summary
                finding = Finding(
                    finding_id=_new_finding_id(),
                    source=FindingSource.DEEP_ANALYSIS,
                    severity=FindingSeverity.HIGH,
                    title=f"Deep analysis: {rule}",
                    summary=analysis.risk_summary,
                    evidence=f"exploit path → {analysis.exploit_path}",
                    recommendation=analysis.remediation_direction,
                    related_invocation_ids=[invocation.invocation_id]
                    + ([target_finding.finding_id] if target_finding else []),
                )
                created.append(finding)
            except Exception as exc:
                await self._fail_invocation(run, invocation, f"llm error: {exc!r}")
                continue

            await self._complete_invocation(run, invocation, summary=summary, findings=created)

        await self._stage_completed(run.run_id, stage, completed=quota)

    async def _stage_aisa_verify(
        self,
        run: ScanRun,
        quota: int,
        aisa_provider,
        payment_provider,
    ) -> None:
        stage = "analysis.aisa_verify"
        await self._stage_started(run.run_id, stage, quota=quota)

        candidates = [
            f for f in run.findings
            if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        ][:quota]

        for i in range(quota):
            target_finding = candidates[i] if i < len(candidates) else None
            target = target_finding.finding_id if target_finding else f"synthetic-aisa-{i+1}"
            invocation = await self._begin_invocation(
                run, stage=stage, tool_name="aisa_verify", target=target
            )
            await self._submit_payment(run, invocation, payment_provider, memo=f"aisa_verify:{target}")
            if invocation.status == InvocationStatus.FAILED:
                continue

            try:
                subject = target_finding.title if target_finding else "generic"
                category = target_finding.source.value if target_finding else "file_scan"
                verification = await aisa_provider.verify(subject, category)
            except Exception as exc:
                await self._fail_invocation(run, invocation, f"aisa error: {exc!r}")
                continue

            finding = Finding(
                finding_id=_new_finding_id(),
                source=FindingSource.AISA_VERIFY,
                severity=(
                    FindingSeverity.HIGH
                    if verification.match_level == "strong"
                    else FindingSeverity.MEDIUM
                ),
                title=f"AIsa intel — {verification.match_level} match",
                summary=verification.intel_summary,
                evidence=f"priority={verification.recommended_priority}",
                recommendation="Weight triage by AIsa priority signal.",
                related_invocation_ids=[invocation.invocation_id]
                + ([target_finding.finding_id] if target_finding else []),
            )
            await self._complete_invocation(
                run, invocation, summary=verification.intel_summary, findings=[finding]
            )

        await self._stage_completed(run.run_id, stage, completed=quota)

    async def _stage_fix_suggestions(
        self,
        run: ScanRun,
        quota: int,
        llm_provider,
        payment_provider,
    ) -> None:
        stage = "analysis.fix_suggestions"
        await self._stage_started(run.run_id, stage, quota=quota)

        candidates = [
            f for f in run.findings
            if f.severity in (FindingSeverity.CRITICAL, FindingSeverity.HIGH)
        ][:quota]

        for i in range(quota):
            target_finding = candidates[i] if i < len(candidates) else None
            target = target_finding.finding_id if target_finding else f"synthetic-fix-{i+1}"
            invocation = await self._begin_invocation(
                run, stage=stage, tool_name="fix_suggestion", target=target
            )
            await self._submit_payment(run, invocation, payment_provider, memo=f"fix_suggestion:{target}")
            if invocation.status == InvocationStatus.FAILED:
                continue

            try:
                rule = _rule_from_finding(target_finding)
                language = "python"
                analysis = await llm_provider.deep_analysis(
                    llm_mod.DeepAnalysisInput(
                        snippet=target_finding.evidence if target_finding else "",
                        rule=rule,
                        language=language,
                        evidence=target_finding.evidence if target_finding else "",
                    )
                )
                suggestion = await llm_provider.fix_suggestion(
                    llm_mod.FixSuggestionInput(
                        snippet=target_finding.evidence if target_finding else "",
                        rule=rule,
                        language=language,
                        analysis=analysis,
                    )
                )
            except Exception as exc:
                await self._fail_invocation(run, invocation, f"llm error: {exc!r}")
                continue

            finding = Finding(
                finding_id=_new_finding_id(),
                source=FindingSource.FIX_SUGGESTION,
                severity=FindingSeverity.MEDIUM,
                title=f"Fix suggestion: {rule}",
                summary=suggestion.patch_summary,
                evidence=suggestion.suggested_code_change,
                recommendation=suggestion.validation_steps,
                related_invocation_ids=[invocation.invocation_id]
                + ([target_finding.finding_id] if target_finding else []),
            )
            await self._complete_invocation(
                run, invocation, summary=suggestion.patch_summary, findings=[finding]
            )

        await self._stage_completed(run.run_id, stage, completed=quota)

    async def _stage_profitability(self, run: ScanRun) -> None:
        stage = "summary.profitability"
        await self._stage_started(run.run_id, stage)
        snapshot = profitability_mod.compute(run.tool_invocations)
        run.profitability = snapshot
        self._registry.save(run)
        await self._stage_completed(
            run.run_id,
            stage,
            tool_cost_usd=snapshot.tool_cost_usd,
            settled_usdc=snapshot.settled_usdc,
            traditional_gas_estimate_usd=snapshot.traditional_gas_estimate_usd,
        )

    async def _stage_finalize(self, run: ScanRun) -> None:
        stage = "summary.finalize"
        await self._stage_started(run.run_id, stage)
        run.status = RunStatus.COMPLETED
        run.completed_at = _utcnow()
        self._registry.save(run)
        self._registry.write_artifacts(run)
        counts = run.counts()
        await self._stage_completed(run.run_id, stage)
        await self._bus.publish(
            make_event(
                "run.completed",
                run.run_id,
                counts=counts.model_dump(),
                profitability=run.profitability.model_dump(),
            )
        )

    # ---------- helpers ----------

    async def _stage_started(self, run_id: str, stage: str, **payload) -> None:
        await self._bus.publish(make_event("stage.started", run_id, stage=stage, **payload))

    async def _stage_completed(self, run_id: str, stage: str, **payload) -> None:
        await self._bus.publish(make_event("stage.completed", run_id, stage=stage, **payload))

    async def _begin_invocation(
        self, run: ScanRun, *, stage: str, tool_name: str, target: str
    ) -> ToolInvocation:
        invocation = ToolInvocation(
            invocation_id=_new_invocation_id(),
            stage=stage,
            tool_name=tool_name,
            target=target,
            price_usd=price_for(tool_name),
            status=InvocationStatus.PENDING,
            started_at=_utcnow(),
        )
        run.tool_invocations.append(invocation)
        self._registry.save(run)
        await self._bus.publish(
            make_event(
                "tool.invoked",
                run.run_id,
                invocation_id=invocation.invocation_id,
                stage=stage,
                tool_name=tool_name,
                target=target,
                price_usd=invocation.price_usd,
            )
        )
        return invocation

    async def _submit_payment(
        self,
        run: ScanRun,
        invocation: ToolInvocation,
        payment_provider,
        *,
        memo: str,
    ) -> None:
        invocation.status = InvocationStatus.PAYMENT_SUBMITTED
        self._registry.save(run)
        await self._bus.publish(
            make_event(
                "payment.submitted",
                run.run_id,
                invocation_id=invocation.invocation_id,
                amount_usd=invocation.price_usd,
                memo=memo,
            )
        )
        try:
            receipt: PaymentReceipt = await payment_provider.pay(
                amount_usd=invocation.price_usd, memo=memo
            )
        except Exception as exc:
            await self._fail_run(run, f"payment failed for {invocation.invocation_id}: {exc!r}")
            invocation.status = InvocationStatus.FAILED
            invocation.error_message = f"payment failed: {exc!r}"
            invocation.completed_at = _utcnow()
            self._registry.save(run)
            return

        invocation.payment = receipt
        invocation.status = InvocationStatus.PAYMENT_CONFIRMED
        self._registry.save(run)
        await self._bus.publish(
            make_event(
                "payment.confirmed",
                run.run_id,
                invocation_id=invocation.invocation_id,
                tx_hash=receipt.tx_hash,
                explorer_url=receipt.explorer_url,
                amount_usdc=receipt.amount_usdc,
                console_reference=receipt.console_reference,
            )
        )

    async def _complete_invocation(
        self,
        run: ScanRun,
        invocation: ToolInvocation,
        *,
        summary: str,
        findings: List[Finding],
    ) -> None:
        invocation.result_summary = summary
        invocation.status = InvocationStatus.COMPLETED
        invocation.completed_at = _utcnow()
        for f in findings:
            run.findings.append(f)
            invocation.finding_ids.append(f.finding_id)
        run.completed_invocations += 1
        self._registry.save(run)

        for f in findings:
            await self._bus.publish(
                make_event(
                    "finding.created",
                    run.run_id,
                    finding_id=f.finding_id,
                    source=f.source.value,
                    severity=f.severity.value,
                    title=f.title,
                    summary=f.summary,
                    related_invocation_ids=f.related_invocation_ids,
                )
            )
        await self._bus.publish(
            make_event(
                "tool.completed",
                run.run_id,
                invocation_id=invocation.invocation_id,
                stage=invocation.stage,
                tool_name=invocation.tool_name,
                target=invocation.target,
                summary=summary,
                finding_ids=invocation.finding_ids,
            )
        )

    async def _fail_invocation(
        self,
        run: ScanRun,
        invocation: ToolInvocation,
        reason: str,
    ) -> None:
        invocation.status = InvocationStatus.FAILED
        invocation.error_message = reason
        invocation.completed_at = _utcnow()
        self._registry.save(run)
        await self._bus.publish(
            make_event(
                "tool.failed",
                run.run_id,
                invocation_id=invocation.invocation_id,
                stage=invocation.stage,
                tool_name=invocation.tool_name,
                reason=reason,
            )
        )

    async def _fail_run(self, run: ScanRun, reason: str) -> None:
        run.status = RunStatus.FAILED
        run.error_message = reason
        run.completed_at = _utcnow()
        self._registry.save(run)
        await self._bus.publish(make_event("run.failed", run.run_id, reason=reason))


def _rule_from_finding(finding: Optional[Finding]) -> str:
    if finding is None:
        return "hardcoded_secret"
    title = (finding.title or "").lower()
    for rule in (
        "hardcoded_secret",
        "dangerous_eval",
        "unsafe_shell_call",
        "debug_mode_exposed",
        "weak_cors_config",
        "open_redirect_pattern",
        "insecure_deserialization",
        "unsafe_innerhtml",
        "suspicious_env_exposure",
        "vulnerable_dependency",
        "missing_security_header",
        "mixed_content",
        "exposed_admin_path",
    ):
        if rule in title or rule in finding.summary.lower():
            return rule
    return "hardcoded_secret"


_orchestrator_singleton: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator_singleton
    if _orchestrator_singleton is None:
        _orchestrator_singleton = Orchestrator()
    return _orchestrator_singleton


def reset_orchestrator_for_tests() -> None:
    global _orchestrator_singleton
    _orchestrator_singleton = None
