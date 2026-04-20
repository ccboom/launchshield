"""File-level static scanning rules.

Each rule produces candidate matches. The orchestrator later wraps each rule hit
into a `Finding` with `source=file_scan`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .models import FindingSeverity


@dataclass
class FileMatch:
    rule: str
    severity: FindingSeverity
    path: str
    line: int
    snippet: str
    evidence: str
    language: str


@dataclass
class Rule:
    name: str
    severity: FindingSeverity
    pattern: re.Pattern[str]
    languages: Optional[Tuple[str, ...]] = None
    reason: str = ""


_BASE_RULES: List[Rule] = [
    Rule(
        name="hardcoded_secret",
        severity=FindingSeverity.CRITICAL,
        pattern=re.compile(
            r"(sk[_-](?:live|test)[_-][A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|JWT_SECRET\s*=\s*['\"]|"
            r"SECRET_KEY\s*=\s*['\"][A-Za-z0-9_-]{8,})",
        ),
        reason="Hard-coded credential detected.",
    ),
    Rule(
        name="dangerous_eval",
        severity=FindingSeverity.CRITICAL,
        pattern=re.compile(r"\beval\s*\("),
        reason="Use of `eval()` on potentially untrusted input.",
    ),
    Rule(
        name="unsafe_shell_call",
        severity=FindingSeverity.HIGH,
        pattern=re.compile(r"(os\.system\s*\(|subprocess\.(?:Popen|call|run)\s*\([^)]*shell\s*=\s*True)"),
        reason="Shell interpolation with potentially tainted input.",
    ),
    Rule(
        name="debug_mode_exposed",
        severity=FindingSeverity.MEDIUM,
        pattern=re.compile(
            r"\bdebug\b\s*[:=]\s*(?:true|1|\"on\"|'on')",
            re.IGNORECASE,
        ),
        reason="Debug mode left enabled.",
    ),
    Rule(
        name="weak_cors_config",
        severity=FindingSeverity.HIGH,
        pattern=re.compile(
            r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*['\"]|"
            r"allow_origins\s*[:=]\s*\[?\s*['\"]\*['\"]"
        ),
        reason="Permissive CORS configuration detected.",
    ),
    Rule(
        name="open_redirect_pattern",
        severity=FindingSeverity.HIGH,
        pattern=re.compile(r"redirect\s*\(\s*(?:req\.(?:query|args|body|params)|request\.args\.get)"),
        reason="Redirect target derived from untrusted input.",
    ),
    Rule(
        name="insecure_deserialization",
        severity=FindingSeverity.CRITICAL,
        pattern=re.compile(
            r"pickle\.loads\s*\(|yaml\.load\s*\((?!.*Loader\s*=\s*yaml\.Safe)|"
            r"xml\.etree\.ElementTree\.fromstring\s*\("
        ),
        reason="Unsafe deserialization primitive.",
    ),
    Rule(
        name="unsafe_innerhtml",
        severity=FindingSeverity.HIGH,
        pattern=re.compile(r"\.innerHTML\s*="),
        reason="Direct assignment to innerHTML bypasses escaping.",
    ),
    Rule(
        name="suspicious_env_exposure",
        severity=FindingSeverity.MEDIUM,
        pattern=re.compile(r"JSON\.stringify\s*\(\s*process\.env|window\.__NEXT_DATA__\s*="),
        reason="Environment data exposed to the client bundle.",
    ),
]


def _iter_lines(content: str) -> Iterable[Tuple[int, str]]:
    for idx, line in enumerate(content.splitlines(), start=1):
        yield idx, line


def scan_file(path: str, language: str, content: str) -> List[FileMatch]:
    matches: List[FileMatch] = []
    for rule in _BASE_RULES:
        if rule.languages and language not in rule.languages:
            continue
        for line_no, line in _iter_lines(content):
            if rule.pattern.search(line):
                matches.append(
                    FileMatch(
                        rule=rule.name,
                        severity=rule.severity,
                        path=path,
                        line=line_no,
                        snippet=line.strip()[:240],
                        evidence=f"{path}:{line_no} — {rule.reason}",
                        language=language,
                    )
                )
    return matches
