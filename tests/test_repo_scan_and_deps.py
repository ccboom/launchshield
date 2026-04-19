"""Unit tests for the static file scanner and dependency parsers."""
from __future__ import annotations

from launchshield.dep_check import (
    DependencyEntry,
    lookup_vuln,
    parse_manifests,
    parse_package_json,
    parse_pyproject_toml,
    parse_requirements_txt,
)
from launchshield.repo_scan import scan_file
from launchshield.repo_source import MOCK_MANIFESTS, RepoFile, is_allowed_path


def test_file_scanner_detects_common_issues() -> None:
    content = (
        "API_KEY = 'sk-live-ABCDEFGHIJKLMNOPQRST1234'\n"
        "def run_cmd(cmd):\n"
        "    return eval(cmd)\n"
        "import os\n"
        "os.system('ping ' + host)\n"
    )
    matches = scan_file("src/app.py", "python", content)
    rule_names = {m.rule for m in matches}
    assert "hardcoded_secret" in rule_names
    assert "dangerous_eval" in rule_names
    assert "unsafe_shell_call" in rule_names


def test_scanner_ignores_clean_code() -> None:
    content = "def add(a, b):\n    return a + b\n"
    assert scan_file("src/math.py", "python", content) == []


def test_requirements_txt_parser() -> None:
    entries = parse_requirements_txt(
        "requirements.txt",
        "# comment\nflask==1.1.4\nrequests==2.19.1  # pinned\n\n",
    )
    names = {(e.ecosystem, e.name, e.version) for e in entries}
    assert ("pypi", "flask", "1.1.4") in names
    assert ("pypi", "requests", "2.19.1") in names


def test_package_json_parser() -> None:
    content = (
        '{"dependencies": {"lodash": "^4.17.11", "express": "4.16.0"},'
        ' "devDependencies": {"jest": "26.0.0"}}'
    )
    entries = parse_package_json("package.json", content)
    pairs = {(e.ecosystem, e.name, e.version) for e in entries}
    assert ("npm", "lodash", "4.17.11") in pairs
    assert ("npm", "express", "4.16.0") in pairs
    assert ("npm", "jest", "26.0.0") in pairs


def test_lookup_vuln_returns_known_advisory() -> None:
    entry = DependencyEntry(ecosystem="npm", name="lodash", version="4.17.11", manifest_path="p")
    vuln = lookup_vuln(entry)
    assert vuln is not None
    assert vuln.advisory_id == "CVE-2019-10744"


def test_parse_manifests_against_fixtures() -> None:
    entries = parse_manifests(list(MOCK_MANIFESTS))
    assert len(entries) > 10
    names = {(e.ecosystem, e.name) for e in entries}
    assert ("pypi", "flask") in names
    assert ("npm", "lodash") in names


def test_allowed_extensions() -> None:
    assert is_allowed_path("src/app.py")
    assert is_allowed_path(".env.example")
    assert not is_allowed_path("README.md")
    assert not is_allowed_path("scripts/run.sh")
