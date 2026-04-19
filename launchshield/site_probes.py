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


def _header_missing(snapshot: PageSnapshot, header: str) -> bool:
    return header.lower() not in {k.lower() for k in snapshot.headers}


def http_header_probe(snapshot: PageSnapshot) -> List[ProbeFinding]:
    out: List[ProbeFinding] = []
    checks = [
        ("Content-Security-Policy", FindingSeverity.HIGH, "Missing CSP header"),
        ("X-Frame-Options", FindingSeverity.MEDIUM, "Missing X-Frame-Options"),
        (
            "Strict-Transport-Security",
            FindingSeverity.MEDIUM,
            "Missing HSTS header",
        ),
    ]
    for header, severity, title in checks:
        if _header_missing(snapshot, header):
            out.append(
                ProbeFinding(
                    probe="missing_security_header",
                    severity=severity,
                    target=snapshot.url,
                    title=title,
                    summary=f"{header} is not returned by {snapshot.url}.",
                    evidence=f"HTTP response headers: {list(snapshot.headers.keys())[:8]}",
                )
            )

    server_header = snapshot.headers.get("server")
    if server_header:
        out.append(
            ProbeFinding(
                probe="server_header_exposed",
                severity=FindingSeverity.LOW,
                target=snapshot.url,
                title="Server banner exposed",
                summary=f"Server identifies itself as `{server_header}`.",
                evidence=f"Server: {server_header}",
            )
        )

    cors = snapshot.headers.get("access-control-allow-origin")
    if cors == "*":
        out.append(
            ProbeFinding(
                probe="weak_cors_config",
                severity=FindingSeverity.HIGH,
                target=snapshot.url,
                title="Permissive CORS on response",
                summary="`Access-Control-Allow-Origin: *` returned on a page that may serve credentials.",
                evidence="Access-Control-Allow-Origin: *",
            )
        )
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
        if "eval(" in body or "innerHTML" in body:
            findings.append(
                ProbeFinding(
                    probe="unsafe_innerhtml",
                    severity=FindingSeverity.HIGH,
                    target=snapshot.url,
                    title="Inline script uses an unsafe DOM sink",
                    summary="An inline <script> block on the page uses `eval()` or `innerHTML` on data of unknown origin.",
                    evidence=f"inline_script[{idx}]: {body[:160]}",
                )
            )
    return findings


def next_data_probe(snapshot: PageSnapshot) -> Optional[ProbeFinding]:
    if not snapshot.next_data_present:
        return None
    return ProbeFinding(
        probe="suspicious_env_exposure",
        severity=FindingSeverity.MEDIUM,
        target=snapshot.url,
        title="__NEXT_DATA__ payload present",
        summary="Inline __NEXT_DATA__ blob ships server-side state to the browser.",
        evidence="Detected `__NEXT_DATA__` in HTML payload.",
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
        evidence="Found `http://` references inside an HTTPS page.",
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
