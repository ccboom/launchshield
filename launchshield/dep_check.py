"""Dependency manifest parsing and vulnerability lookup (mock-friendly)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .models import FindingSeverity
from .repo_source import RepoFile


@dataclass
class DependencyEntry:
    ecosystem: str
    name: str
    version: str
    manifest_path: str
    specifier: str = ""
    pinned: bool = True


@dataclass
class DependencyVuln:
    name: str
    version: str
    ecosystem: str
    severity: FindingSeverity
    advisory_id: str
    summary: str
    fixed_in: str


_TOML_DEP_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*=\s*\"([^\"]+)\"")
_REQ_RE = re.compile(
    r"^\s*([A-Za-z0-9_.\-]+)(?:\[[A-Za-z0-9_,.\-]+\])?\s*(==|~=|>=|<=|>|<)\s*([A-Za-z0-9_.\-]+)"
)


def parse_requirements_txt(path: str, content: str) -> List[DependencyEntry]:
    out: List[DependencyEntry] = []
    for line in content.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        match = _REQ_RE.match(line)
        if match:
            out.append(
                DependencyEntry(
                    ecosystem="pypi",
                    name=match.group(1),
                    version=match.group(3),
                    manifest_path=path,
                    specifier=f"{match.group(2)}{match.group(3)}",
                    pinned=match.group(2) == "==",
                )
            )
    return out


def parse_package_json(path: str, content: str) -> List[DependencyEntry]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    out: List[DependencyEntry] = []
    for key in ("dependencies", "devDependencies"):
        for name, version in (data.get(key) or {}).items():
            version_raw = str(version).strip()
            version_s = version_raw.lstrip("^~>=<! ")
            out.append(
                DependencyEntry(
                    ecosystem="npm",
                    name=name,
                    version=version_s,
                    manifest_path=path,
                    specifier=version_raw,
                    pinned=version_raw == version_s,
                )
            )
    return out


def parse_pyproject_toml(path: str, content: str) -> List[DependencyEntry]:
    out: List[DependencyEntry] = []
    try:
        import tomllib  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - python <3.11 fallback
        try:
            import tomli as tomllib  # type: ignore
        except ModuleNotFoundError:
            return out
    try:
        data = tomllib.loads(content)
    except Exception:
        return out
    project = data.get("project") or {}
    for dep in project.get("dependencies", []) or []:
        match = re.match(r"([A-Za-z0-9_.\-]+)\s*(==|~=|>=|<=|>|<)\s*([A-Za-z0-9_.\-]+)", dep)
        if match:
            out.append(
                DependencyEntry(
                    ecosystem="pypi",
                    name=match.group(1),
                    version=match.group(3),
                    manifest_path=path,
                    specifier=f"{match.group(2)}{match.group(3)}",
                    pinned=match.group(2) == "==",
                )
            )
    return out


def parse_manifests(manifests: List[RepoFile]) -> List[DependencyEntry]:
    entries: List[DependencyEntry] = []
    for manifest in manifests:
        name = manifest.path.split("/")[-1]
        if name == "requirements.txt":
            entries.extend(parse_requirements_txt(manifest.path, manifest.content))
        elif name == "package.json":
            entries.extend(parse_package_json(manifest.path, manifest.content))
        elif name == "pyproject.toml":
            entries.extend(parse_pyproject_toml(manifest.path, manifest.content))
    return entries


_STATIC_ADVISORIES: Dict[Tuple[str, str], DependencyVuln] = {
    ("pypi", "flask"): DependencyVuln(
        name="flask",
        version="1.1.4",
        ecosystem="pypi",
        severity=FindingSeverity.HIGH,
        advisory_id="GHSA-m2qf-hxjv-5gpq",
        summary="Flask <2.2.5 leaks session data under cache-inconsistent proxies.",
        fixed_in=">=2.2.5",
    ),
    ("pypi", "requests"): DependencyVuln(
        name="requests",
        version="2.19.1",
        ecosystem="pypi",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2018-18074",
        summary="requests leaked Authorization headers across redirects.",
        fixed_in=">=2.20.0",
    ),
    ("pypi", "pyyaml"): DependencyVuln(
        name="pyyaml",
        version="5.3",
        ecosystem="pypi",
        severity=FindingSeverity.CRITICAL,
        advisory_id="CVE-2020-14343",
        summary="pyyaml full_load allowed arbitrary code execution via crafted YAML.",
        fixed_in=">=5.4",
    ),
    ("pypi", "jinja2"): DependencyVuln(
        name="jinja2",
        version="2.10",
        ecosystem="pypi",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2019-10906",
        summary="jinja2 <2.10.1 sandbox escape via str.format_map.",
        fixed_in=">=2.10.1",
    ),
    ("pypi", "pillow"): DependencyVuln(
        name="pillow",
        version="8.1.1",
        ecosystem="pypi",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2021-25287",
        summary="Pillow <8.2 out-of-bounds read in BLP decoder.",
        fixed_in=">=8.2.0",
    ),
    ("pypi", "cryptography"): DependencyVuln(
        name="cryptography",
        version="3.2",
        ecosystem="pypi",
        severity=FindingSeverity.MEDIUM,
        advisory_id="GHSA-rhm9-p9w5-fwm7",
        summary="cryptography <3.3 includes a vulnerable bundled OpenSSL.",
        fixed_in=">=3.3",
    ),
    ("pypi", "urllib3"): DependencyVuln(
        name="urllib3",
        version="1.24.1",
        ecosystem="pypi",
        severity=FindingSeverity.MEDIUM,
        advisory_id="CVE-2019-11324",
        summary="urllib3 <1.24.2 improperly handled CRLF in URL parsing.",
        fixed_in=">=1.24.2",
    ),
    ("pypi", "django"): DependencyVuln(
        name="django",
        version="2.2.3",
        ecosystem="pypi",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2019-14234",
        summary="Django <2.2.4 SQL injection via JSONField key lookups.",
        fixed_in=">=2.2.4",
    ),
    ("pypi", "numpy"): DependencyVuln(
        name="numpy",
        version="1.19.5",
        ecosystem="pypi",
        severity=FindingSeverity.MEDIUM,
        advisory_id="CVE-2021-33430",
        summary="numpy <1.22 buffer overflow in PyArray_NewFromDescr_int.",
        fixed_in=">=1.22",
    ),
    ("pypi", "pandas"): DependencyVuln(
        name="pandas",
        version="1.1.0",
        ecosystem="pypi",
        severity=FindingSeverity.LOW,
        advisory_id="GHSA-v8wq-m3q8-w3rr",
        summary="pandas <1.1.5 ReDoS in string accessor.",
        fixed_in=">=1.1.5",
    ),
    ("npm", "lodash"): DependencyVuln(
        name="lodash",
        version="4.17.11",
        ecosystem="npm",
        severity=FindingSeverity.CRITICAL,
        advisory_id="CVE-2019-10744",
        summary="lodash <4.17.12 prototype pollution via defaultsDeep.",
        fixed_in=">=4.17.12",
    ),
    ("npm", "express"): DependencyVuln(
        name="express",
        version="4.16.0",
        ecosystem="npm",
        severity=FindingSeverity.MEDIUM,
        advisory_id="GHSA-rv95-896h-c2vc",
        summary="express <4.17.3 permits open redirect when trust proxy is set.",
        fixed_in=">=4.17.3",
    ),
    ("npm", "minimist"): DependencyVuln(
        name="minimist",
        version="1.2.0",
        ecosystem="npm",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2020-7598",
        summary="minimist <1.2.2 prototype pollution.",
        fixed_in=">=1.2.2",
    ),
    ("npm", "axios"): DependencyVuln(
        name="axios",
        version="0.21.0",
        ecosystem="npm",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2020-28168",
        summary="axios <0.21.1 SSRF via baseURL bypass.",
        fixed_in=">=0.21.1",
    ),
    ("npm", "moment"): DependencyVuln(
        name="moment",
        version="2.24.0",
        ecosystem="npm",
        severity=FindingSeverity.MEDIUM,
        advisory_id="CVE-2022-24785",
        summary="moment <2.29.4 path traversal in locale loading.",
        fixed_in=">=2.29.4",
    ),
    ("npm", "jquery"): DependencyVuln(
        name="jquery",
        version="3.3.1",
        ecosystem="npm",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2019-11358",
        summary="jQuery <3.4.0 prototype pollution via $.extend.",
        fixed_in=">=3.4.0",
    ),
    ("npm", "handlebars"): DependencyVuln(
        name="handlebars",
        version="4.0.11",
        ecosystem="npm",
        severity=FindingSeverity.CRITICAL,
        advisory_id="CVE-2019-19919",
        summary="handlebars <4.3.0 template injection leading to RCE.",
        fixed_in=">=4.3.0",
    ),
    ("npm", "serialize-javascript"): DependencyVuln(
        name="serialize-javascript",
        version="2.1.1",
        ecosystem="npm",
        severity=FindingSeverity.HIGH,
        advisory_id="CVE-2020-7660",
        summary="serialize-javascript <3.1.0 XSS via untrusted regex.",
        fixed_in=">=3.1.0",
    ),
}


def lookup_vuln(entry: DependencyEntry) -> Optional[DependencyVuln]:
    if not entry.pinned:
        return None
    vuln = _STATIC_ADVISORIES.get((entry.ecosystem, entry.name.lower()))
    if vuln is None:
        return None
    if entry.version != vuln.version:
        return None
    return vuln
