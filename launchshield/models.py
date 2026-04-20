"""Pydantic models for LaunchShield Swarm runs, invocations and findings."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunMode(str, Enum):
    PRESET_STRESS = "preset-stress"
    CUSTOM_STANDARD = "custom-standard"


class ScanScope(str, Enum):
    SAMPLE = "sample"
    FULL = "full"


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InvocationStatus(str, Enum):
    PENDING = "pending"
    PAYMENT_SUBMITTED = "payment_submitted"
    PAYMENT_CONFIRMED = "payment_confirmed"
    COMPLETED = "completed"
    FAILED = "failed"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FindingSource(str, Enum):
    FILE_SCAN = "file_scan"
    DEP_LOOKUP = "dep_lookup"
    SITE_PROBE = "site_probe"
    DEEP_ANALYSIS = "deep_analysis"
    AISA_VERIFY = "aisa_verify"
    FIX_SUGGESTION = "fix_suggestion"


class ProviderMode(str, Enum):
    MOCK = "mock"
    REAL = "real"
    ERROR = "error"


class PaymentReceipt(BaseModel):
    provider: str
    amount_usdc: float
    tx_hash: Optional[str] = None
    network: str = "arc-sandbox"
    explorer_url: Optional[str] = None
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    console_reference: Optional[str] = None


class ToolInvocation(BaseModel):
    invocation_id: str
    stage: str
    tool_name: str
    target: str
    price_usd: float
    status: InvocationStatus = InvocationStatus.PENDING
    payment: Optional[PaymentReceipt] = None
    result_summary: Optional[str] = None
    finding_ids: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class Finding(BaseModel):
    finding_id: str
    source: FindingSource
    severity: FindingSeverity
    title: str
    summary: str
    evidence: str
    recommendation: str
    related_invocation_ids: List[str] = Field(default_factory=list)


class ProfitabilitySnapshot(BaseModel):
    tool_cost_usd: float = 0.0
    settled_usdc: float = 0.0
    traditional_gas_estimate_usd: float = 0.0
    micro_model_margin_signal: str = "profitable"
    traditional_model_signal: str = "bankrupt"
    conclusion_headline: str = (
        "Traditional gas destroys the margin of high-frequency AI security workflows. "
        "Arc + Circle micropayments keep the model profitable."
    )


class ProviderSource(BaseModel):
    requested_mode: ProviderMode = ProviderMode.MOCK
    effective_mode: ProviderMode = ProviderMode.MOCK
    provider: str
    detail: Optional[str] = None


class RunCounts(BaseModel):
    planned_invocations: int = 0
    completed_invocations: int = 0
    confirmed_payments: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0


class ScanRun(BaseModel):
    run_id: str
    mode: RunMode
    scan_scope: ScanScope = ScanScope.SAMPLE
    status: RunStatus = RunStatus.QUEUED
    repo_url: str
    target_url: str
    created_at: datetime = Field(default_factory=utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    planned_invocations: int = 0
    planned_breakdown: dict[str, int] = Field(default_factory=dict)
    completed_invocations: int = 0
    tool_invocations: List[ToolInvocation] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)
    profitability: ProfitabilitySnapshot = Field(default_factory=ProfitabilitySnapshot)
    provider_sources: dict[str, ProviderSource] = Field(default_factory=dict)
    error_message: Optional[str] = None

    def counts(self) -> RunCounts:
        confirmed = sum(
            1
            for inv in self.tool_invocations
            if inv.payment is not None and inv.payment.confirmed_at is not None
        )
        critical = sum(1 for f in self.findings if f.severity == FindingSeverity.CRITICAL)
        high = sum(1 for f in self.findings if f.severity == FindingSeverity.HIGH)
        medium = sum(1 for f in self.findings if f.severity == FindingSeverity.MEDIUM)
        low = sum(1 for f in self.findings if f.severity == FindingSeverity.LOW)
        return RunCounts(
            planned_invocations=self.planned_invocations,
            completed_invocations=self.completed_invocations,
            confirmed_payments=confirmed,
            critical_findings=critical,
            high_findings=high,
            medium_findings=medium,
            low_findings=low,
        )


class CreateRunRequest(BaseModel):
    mode: RunMode
    scan_scope: ScanScope = ScanScope.SAMPLE
    repo_url: Optional[str] = None
    target_url: Optional[str] = None


class CreateRunResponse(BaseModel):
    run_id: str
    status: RunStatus
    mode: RunMode
    scan_scope: ScanScope
    stream_url: str
    summary_url: str


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    mode: RunMode
    scan_scope: ScanScope
    repo_url: str
    target_url: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    counts: RunCounts
    planned_breakdown: dict[str, int]
    provider_sources: dict[str, ProviderSource]
    totals: ProfitabilitySnapshot
    profitability: ProfitabilitySnapshot
    findings: List[Finding]
    tool_invocations: List[ToolInvocation]
    error_message: Optional[str] = None

    @classmethod
    def from_run(cls, run: ScanRun) -> "RunSummary":
        return cls(
            run_id=run.run_id,
            status=run.status,
            mode=run.mode,
            scan_scope=run.scan_scope,
            repo_url=run.repo_url,
            target_url=run.target_url,
            started_at=run.started_at,
            completed_at=run.completed_at,
            counts=run.counts(),
            planned_breakdown=run.planned_breakdown,
            provider_sources=run.provider_sources,
            totals=run.profitability,
            profitability=run.profitability,
            findings=run.findings,
            tool_invocations=run.tool_invocations,
            error_message=run.error_message,
        )
