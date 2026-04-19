"""LLM adapter for deep analysis and fix suggestion."""
from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from .config import AppConfig, get_config


@dataclass
class DeepAnalysisInput:
    snippet: str
    rule: str
    language: str
    evidence: str


@dataclass
class DeepAnalysisResult:
    risk_summary: str
    exploit_path: str
    impact_scope: str
    remediation_direction: str


@dataclass
class FixSuggestionInput:
    snippet: str
    rule: str
    language: str
    analysis: DeepAnalysisResult


@dataclass
class FixSuggestionResult:
    why: str
    patch_summary: str
    suggested_code_change: str
    validation_steps: str


class LLMProvider(Protocol):
    async def deep_analysis(self, req: DeepAnalysisInput) -> DeepAnalysisResult: ...
    async def fix_suggestion(self, req: FixSuggestionInput) -> FixSuggestionResult: ...


_RULE_RISKS: Dict[str, Dict[str, str]] = {
    "hardcoded_secret": {
        "risk": "Hard-coded credential shipped to production could be exfiltrated from "
        "source control history at any time.",
        "exploit": "Attacker clones the public mirror, grep for `SECRET`, pivots into "
        "the backing service using the leaked key.",
        "impact": "Full compromise of the downstream service account; secret rotation "
        "requires every dependent workflow to be restarted.",
        "remediation": "Move the value to a secret manager, rotate now, and add a pre-commit "
        "hook to block base64/api-key-like strings.",
    },
    "dangerous_eval": {
        "risk": "Unvalidated `eval` turns user input into remote code execution.",
        "exploit": "Craft a payload that escapes the string context to execute arbitrary code "
        "in the server process.",
        "impact": "Full RCE; likely privilege escalation if the server runs with broad OS access.",
        "remediation": "Replace with a whitelisted parser or structured deserialization.",
    },
    "unsafe_shell_call": {
        "risk": "Shell interpolation with user input enables command injection.",
        "exploit": "Inject shell metacharacters (`; rm -rf /`) that run alongside the intended "
        "command.",
        "impact": "Server takeover, data exfiltration, lateral movement into the build runner.",
        "remediation": "Switch to arg-array execution, escape inputs, or prefer a native API.",
    },
    "debug_mode_exposed": {
        "risk": "Debug mode leaks stack traces, settings and internal paths.",
        "exploit": "Trigger an error page and harvest configuration secrets or file paths.",
        "impact": "Information disclosure that accelerates every downstream attack.",
        "remediation": "Force `DEBUG=False` in production and wrap stack traces in a sanitizer.",
    },
    "weak_cors_config": {
        "risk": "Permissive CORS lets any origin read authenticated responses.",
        "exploit": "Malicious site calls the API with the victim's cookies and exfiltrates data.",
        "impact": "Account takeover for any authenticated user who visits a hostile page.",
        "remediation": "Pin `Access-Control-Allow-Origin` to a trusted allow-list; never mix "
        "`*` with credentials.",
    },
    "open_redirect_pattern": {
        "risk": "Open redirect is phishing fuel.",
        "exploit": "Attacker crafts a URL on your domain that forwards to a look-alike "
        "credential-stealing page.",
        "impact": "Brand abuse, credential phishing, SSO confusion.",
        "remediation": "Validate redirect targets against an allow-list; strip query params.",
    },
    "insecure_deserialization": {
        "risk": "Deserializing untrusted input risks object-injection RCE.",
        "exploit": "Send a payload that constructs a gadget chain during deserialization.",
        "impact": "Remote code execution in the deserializer process.",
        "remediation": "Use structured schema validation; never pickle untrusted data.",
    },
    "unsafe_innerhtml": {
        "risk": "Directly injecting into `innerHTML` is a classic DOM XSS sink.",
        "exploit": "Supply markup with a `<script>` or `onerror=` payload that executes in the "
        "user's browser.",
        "impact": "Session theft, token exfiltration, coerced transactions.",
        "remediation": "Use `textContent`, a templating engine with escaping, or DOMPurify.",
    },
    "suspicious_env_exposure": {
        "risk": "Environment data served to the client leaks secrets and infra hints.",
        "exploit": "Scrape the page for internal URLs and API keys exposed via `__NEXT_DATA__`.",
        "impact": "Accelerated recon that unlocks subsequent privileged attacks.",
        "remediation": "Gate env vars with a `NEXT_PUBLIC_` style allow-list and strip secrets "
        "server-side.",
    },
    "vulnerable_dependency": {
        "risk": "Known CVE present in a shipped dependency.",
        "exploit": "Attackers weaponize public PoCs as soon as the CVE is disclosed.",
        "impact": "Varies by package — commonly RCE, SSRF or DoS on the hosting service.",
        "remediation": "Bump to the patched release; add a `pip-audit` / `npm audit` gate in CI.",
    },
    "missing_security_header": {
        "risk": "Missing security headers leave the app open to clickjacking or downgrade.",
        "exploit": "Frame the page inside a hostile site and trick the user into UI redress.",
        "impact": "Interactive phishing, token theft, brand damage.",
        "remediation": "Ship CSP, HSTS, X-Frame-Options, and Referrer-Policy at the edge.",
    },
    "mixed_content": {
        "risk": "Mixed HTTP content on an HTTPS page can be tampered in transit.",
        "exploit": "MitM rewrites the insecure resource to inject malicious code.",
        "impact": "DOM takeover via attacker-controlled scripts.",
        "remediation": "Move every sub-resource to HTTPS; add `upgrade-insecure-requests` CSP.",
    },
    "exposed_admin_path": {
        "risk": "Discoverable admin entry point invites brute force and fingerprinting.",
        "exploit": "Attackers enumerate `/admin`, attempt default credentials or known bypasses.",
        "impact": "Full admin takeover; often game-over for the service.",
        "remediation": "Gate admin behind SSO + IP allow-list; rename path; add rate limiting.",
    },
}


def _rule_block(rule: str) -> Dict[str, str]:
    return _RULE_RISKS.get(
        rule,
        {
            "risk": "Heuristic flagged this area as requiring human review.",
            "exploit": "Depends on surrounding context — usually data flow from untrusted input.",
            "impact": "Potentially material; validate before shipping.",
            "remediation": "Refactor to eliminate the pattern and add regression tests.",
        },
    )


class MockLLMProvider:
    def __init__(self, config: AppConfig):
        self._config = config
        self._rng = random.Random(17)

    async def deep_analysis(self, req: DeepAnalysisInput) -> DeepAnalysisResult:
        await asyncio.sleep(self._config.demo_pace_seconds * 0.4)
        block = _rule_block(req.rule)
        return DeepAnalysisResult(
            risk_summary=block["risk"],
            exploit_path=block["exploit"],
            impact_scope=block["impact"],
            remediation_direction=block["remediation"],
        )

    async def fix_suggestion(self, req: FixSuggestionInput) -> FixSuggestionResult:
        await asyncio.sleep(self._config.demo_pace_seconds * 0.4)
        return FixSuggestionResult(
            why=req.analysis.risk_summary,
            patch_summary=f"Refactor `{req.rule}` occurrence in {req.language} to remove the unsafe sink.",
            suggested_code_change=_mock_patch(req.rule, req.language, req.snippet),
            validation_steps=(
                "1) Add a unit test exercising the previously unsafe input. "
                "2) Run the security regression suite. "
                "3) Re-run the LaunchShield scan to confirm the finding disappears."
            ),
        )


def _mock_patch(rule: str, language: str, snippet: str) -> str:
    header = f"# Suggested replacement for {rule} ({language})"
    body_py = (
        "from os import environ\n"
        "SECRET = environ['APP_SECRET']  # loaded from a secret manager\n"
    )
    body_js = (
        "const SECRET = process.env.APP_SECRET; // loaded from a secret manager\n"
    )
    if language in {"py", "python"}:
        return f"{header}\n{body_py}"
    return f"{header}\n{body_js}"


class OpenAIProvider:
    """Minimal skeleton — fill in once OPENAI_API_KEY is available.

    Kept intentionally small: calls out to the OpenAI Responses / Chat Completions
    endpoint and parses JSON. Swap in richer prompts later.
    """

    def __init__(self, config: AppConfig):
        if not config.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY missing — cannot use real LLM provider")
        self._config = config
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openai package not installed") from exc
        self._client = AsyncOpenAI(api_key=config.openai_api_key)

    async def _chat(self, system: str, user: str) -> Dict[str, Any]:
        resp = await self._client.chat.completions.create(
            model=self._config.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        text = resp.choices[0].message.content or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    async def deep_analysis(self, req: DeepAnalysisInput) -> DeepAnalysisResult:
        system = (
            "You are a senior application security engineer. Return strict JSON with keys "
            "risk_summary, exploit_path, impact_scope, remediation_direction. Keep each "
            "under 240 characters."
        )
        user = json.dumps(
            {"snippet": req.snippet, "rule": req.rule, "language": req.language, "evidence": req.evidence}
        )
        data = await self._chat(system, user)
        return DeepAnalysisResult(
            risk_summary=data.get("risk_summary", ""),
            exploit_path=data.get("exploit_path", ""),
            impact_scope=data.get("impact_scope", ""),
            remediation_direction=data.get("remediation_direction", ""),
        )

    async def fix_suggestion(self, req: FixSuggestionInput) -> FixSuggestionResult:
        system = (
            "You are a secure code remediation assistant. Return strict JSON with keys "
            "why, patch_summary, suggested_code_change, validation_steps."
        )
        user = json.dumps(
            {
                "snippet": req.snippet,
                "rule": req.rule,
                "language": req.language,
                "analysis": req.analysis.__dict__,
            }
        )
        data = await self._chat(system, user)
        return FixSuggestionResult(
            why=data.get("why", ""),
            patch_summary=data.get("patch_summary", ""),
            suggested_code_change=data.get("suggested_code_change", ""),
            validation_steps=data.get("validation_steps", ""),
        )


def build_provider(config: Optional[AppConfig] = None) -> LLMProvider:
    cfg = config or get_config()
    if cfg.use_real_llm and cfg.openai_api_key:
        return OpenAIProvider(cfg)
    return MockLLMProvider(cfg)
