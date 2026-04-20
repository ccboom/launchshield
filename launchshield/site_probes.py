"""Site-level probes backed by the browser runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .browser_runtime import BrowserRuntime, PageSnapshot
from .models import FindingSeverity


SENSITIVE_PATHS = (
    "/.env",
    "/admin",
    "/login",
    "/dashboard",
    "/.git/config",
    "/debug",
    "/swagger",
)


@dataclass
class ProbeFinding:
    probe: str
    severity: FindingSeverity
    target: str
    title: str
    summary: str
    evidence: str


@dataclass(frozen=True)
class ProbePlan:
    probe: str
    target: str
    detail: Optional[str] = None


HEADER_CHECKS = (
    ("Content-Security-Policy", FindingSeverity.HIGH, "Missing CSP header"),
    ("X-Frame-Options", FindingSeverity.MEDIUM, "Missing X-Frame-Options"),
    ("Strict-Transport-Security", FindingSeverity.MEDIUM, "Missing HSTS header"),
)


def _header_missing(snapshot: PageSnapshot, header: str) -> bool:
    return header.lower() not in {k.lower() for k in snapshot.headers}


def _header_probe(
    snapshot: PageSnapshot,
    header: str,
    severity: FindingSeverity,
    title: str,
) -> Optional[ProbeFinding]:
    if not _header_missing(snapshot, header):
        return None
    return ProbeFinding(
        probe="missing_security_header",
        severity=severity,
        target=snapshot.url,
        title=title,
        summary=f"{header} is not returned by {snapshot.url}.",
        evidence=(
            f"source={snapshot.capture_source}; "
            f"headers={list(snapshot.headers.keys())[:8]}"
        ),
    )


def _server_header_probe(snapshot: PageSnapshot) -> Optional[ProbeFinding]:
    server_header = snapshot.headers.get("server")
    if not server_header:
        return None
    return ProbeFinding(
        probe="server_header_exposed",
        severity=FindingSeverity.LOW,
        target=snapshot.url,
        title="Server banner exposed",
        summary=f"Server identifies itself as `{server_header}`.",
        evidence=f"source={snapshot.capture_source}; Server: {server_header}",
    )


def _weak_cors_probe(snapshot: PageSnapshot) -> Optional[ProbeFinding]:
    cors = snapshot.headers.get("access-control-allow-origin")
    if cors != "*":
        return None
    return ProbeFinding(
        probe="weak_cors_config",
        severity=FindingSeverity.HIGH,
        target=snapshot.url,
        title="Permissive CORS on response",
        summary="`Access-Control-Allow-Origin: *` returned on a page that may serve credentials.",
        evidence=f"source={snapshot.capture_source}; Access-Control-Allow-Origin: *",
    )


def http_header_probe(snapshot: PageSnapshot) -> List[ProbeFinding]:
    out: List[ProbeFinding] = []
    for header, severity, title in HEADER_CHECKS:
        finding = _header_probe(snapshot, header, severity, title)
        if finding:
            out.append(finding)
    server_finding = _server_header_probe(snapshot)
    if server_finding:
        out.append(server_finding)
    cors_finding = _weak_cors_probe(snapshot)
    if cors_finding:
        out.append(cors_finding)
    return out


def sensitive_path_probe(path: str, status_code: int, base_url: str) -> Optional[ProbeFinding]:
    if status_code == 0:
        return None
    if 200 <= status_code < 400 and path != "/login":
        return ProbeFinding(
            probe="exposed_admin_path",
            severity=FindingSeverity.HIGH,
            target=base_url + path,
            title=f"Sensitive path {path} is reachable",
            summary=f"{base_url+path} returned {status_code} — expected 404/401.",
            evidence=f"GET {path} -> {status_code}",
        )
    if path == "/login" and 200 <= status_code < 400:
        return ProbeFinding(
            probe="login_page_exposed",
            severity=FindingSeverity.MEDIUM,
            target=base_url + path,
            title="Login surface publicly discoverable",
            summary="A /login page responds without authentication or rate limit evidence.",
            evidence=f"GET /login -> {status_code}",
        )
    return None


def inline_script_probe(snapshot: PageSnapshot) -> List[ProbeFinding]:
    findings: List[ProbeFinding] = []
    for idx, body in enumerate(snapshot.inline_scripts[:3]):
        finding = inline_script_probe_at(snapshot, idx)
        if finding:
            findings.append(finding)
    return findings


def inline_script_probe_at(snapshot: PageSnapshot, idx: int) -> Optional[ProbeFinding]:
    if idx >= len(snapshot.inline_scripts[:3]):
        return None
    body = snapshot.inline_scripts[idx]
    if "eval(" not in body and "innerHTML" not in body:
        return None
    return ProbeFinding(
        probe="unsafe_innerhtml",
        severity=FindingSeverity.HIGH,
        target=snapshot.url,
        title="Inline script uses an unsafe DOM sink",
        summary="An inline <script> block on the page uses `eval()` or `innerHTML` on data of unknown origin.",
        evidence=f"source={snapshot.capture_source}; inline_script[{idx}]: {body[:160]}",
    )


def next_data_probe(snapshot: PageSnapshot) -> Optional[ProbeFinding]:
    if not snapshot.next_data_present:
        return None
    return ProbeFinding(
        probe="suspicious_env_exposure",
        severity=FindingSeverity.MEDIUM,
        target=snapshot.url,
        title="__NEXT_DATA__ payload present",
        summary="Inline __NEXT_DATA__ blob ships server-side state to the browser.",
        evidence=f"source={snapshot.capture_source}; detected __NEXT_DATA__ in page payload",
    )


def mixed_content_probe(snapshot: PageSnapshot) -> Optional[ProbeFinding]:
    if not snapshot.mixed_content:
        return None
    return ProbeFinding(
        probe="mixed_content",
        severity=FindingSeverity.MEDIUM,
        target=snapshot.url,
        title="Mixed content detected",
        summary="HTTPS page embeds at least one HTTP sub-resource.",
        evidence=f"source={snapshot.capture_source}; found http:// references inside an HTTPS page",
    )


async def collect_site_findings(
    runtime: BrowserRuntime,
    base_url: str,
    limit: int,
) -> List[ProbeFinding]:
    """Collect up to `limit` findings. Probes are ordered for a balanced demo."""
    snapshot = await runtime.fetch(base_url)
    findings: List[ProbeFinding] = []
    findings.extend(http_header_probe(snapshot))
    next_f = next_data_probe(snapshot)
    if next_f:
        findings.append(next_f)
    mixed_f = mixed_content_probe(snapshot)
    if mixed_f:
        findings.append(mixed_f)
    findings.extend(inline_script_probe(snapshot))

    for path in SENSITIVE_PATHS:
        status = await runtime.probe_path(base_url, path)
        probe_f = sensitive_path_probe(path, status, base_url)
        if probe_f:
            findings.append(probe_f)
        if len(findings) >= limit:
            break

    return findings[:limit]


def build_probe_plan(base_url: str, limit: int) -> List[ProbePlan]:
    plans = [
        ProbePlan(probe="header", target=base_url, detail="Content-Security-Policy"),
        ProbePlan(probe="header", target=base_url, detail="X-Frame-Options"),
        ProbePlan(probe="header", target=base_url, detail="Strict-Transport-Security"),
        ProbePlan(probe="server_header", target=base_url),
        ProbePlan(probe="weak_cors", target=base_url),
    ]
    plans.extend(ProbePlan(probe="path", target=base_url + path, detail=path) for path in SENSITIVE_PATHS[:4])
    plans.extend(
        [
            ProbePlan(probe="next_data", target=base_url),
            ProbePlan(probe="mixed_content", target=base_url),
            ProbePlan(probe="inline_script", target=base_url, detail="0"),
        ]
    )
    plans.extend(ProbePlan(probe="path", target=base_url + path, detail=path) for path in SENSITIVE_PATHS[4:])
    return plans[:limit]


async def execute_probe(
    runtime: BrowserRuntime,
    plan: ProbePlan,
    base_url: str,
    *,
    base_snapshot: Optional[PageSnapshot] = None,
) -> Optional[ProbeFinding]:
    if plan.probe == "path":
        status = await runtime.probe_path(base_url, plan.detail or "")
        return sensitive_path_probe(plan.detail or "", status, base_url)

    snapshot = base_snapshot or await runtime.fetch(base_url)
    if plan.probe == "header":
        for header, severity, title in HEADER_CHECKS:
            if header == plan.detail:
                return _header_probe(snapshot, header, severity, title)
        raise ValueError(f"unknown header probe: {plan.detail}")
    if plan.probe == "server_header":
        return _server_header_probe(snapshot)
    if plan.probe == "weak_cors":
        return _weak_cors_probe(snapshot)
    if plan.probe == "next_data":
        return next_data_probe(snapshot)
    if plan.probe == "mixed_content":
        return mixed_content_probe(snapshot)
    if plan.probe == "inline_script":
        return inline_script_probe_at(snapshot, int(plan.detail or "0"))
    raise ValueError(f"unknown probe type: {plan.probe}")
