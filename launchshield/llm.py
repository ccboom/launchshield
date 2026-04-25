"""LLM adapter for deep analysis and fix suggestion."""
from __future__ import annotations

import asyncio
import importlib
import json
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol
from urllib.parse import urlsplit, urlunsplit

from .config import AppConfig, get_config
from .models import ProviderMode, ProviderSource


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
        self._base_url = _normalize_openai_base_url(config.openai_base_url)
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError("openai package not installed") from exc
        client_kwargs = {"api_key": config.openai_api_key}
        if self._base_url:
            client_kwargs["base_url"] = self._base_url
        self._client = AsyncOpenAI(**client_kwargs)

    async def _chat(self, system: str, user: str) -> Dict[str, Any]:
        request = dict(
            model=self._config.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        resp = await self._client.chat.completions.create(**request)
        try:
            text = _extract_chat_completion_text(resp)
        except RuntimeError as exc:
            if not _should_retry_stream(exc):
                raise
            text = await self._chat_via_stream(request)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    async def _chat_via_stream(self, request: Dict[str, Any]) -> str:
        stream = await self._client.chat.completions.create(**request, stream=True)
        chunks: List[str] = []
        async for chunk in stream:
            piece = _extract_chat_completion_chunk_text(chunk)
            if piece:
                chunks.append(piece)
        text = "".join(chunks).strip()
        if text:
            return text
        raise RuntimeError(
            "LLM gateway stream returned no delta content. "
            "Check model compatibility and upstream gateway response format."
        )

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
            risk_summary=_coerce_text_field(data.get("risk_summary", "")),
            exploit_path=_coerce_text_field(data.get("exploit_path", "")),
            impact_scope=_coerce_text_field(data.get("impact_scope", "")),
            remediation_direction=_coerce_text_field(data.get("remediation_direction", "")),
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
            why=_coerce_text_field(data.get("why", "")),
            patch_summary=_coerce_text_field(data.get("patch_summary", "")),
            suggested_code_change=_coerce_text_field(data.get("suggested_code_change", "")),
            validation_steps=_coerce_text_field(data.get("validation_steps", "")),
        )


def build_provider(config: Optional[AppConfig] = None) -> LLMProvider:
    cfg = config or get_config()
    if _real_provider_available(cfg):
        return OpenAIProvider(cfg)
    return MockLLMProvider(cfg)


def describe_provider(config: Optional[AppConfig] = None) -> ProviderSource:
    cfg = config or get_config()
    requested_mode = ProviderMode.REAL if cfg.use_real_llm else ProviderMode.MOCK
    available, fallback_reason = _real_provider_status(cfg)
    if available:
        detail = cfg.openai_model
        normalized_base_url = _normalize_openai_base_url(cfg.openai_base_url)
        if normalized_base_url:
            detail = f"{detail} @ {normalized_base_url}"
        return ProviderSource(
            requested_mode=requested_mode,
            effective_mode=ProviderMode.REAL,
            provider="openai-compatible",
            detail=detail,
        )
    if cfg.use_real_llm:
        return ProviderSource(
            requested_mode=requested_mode,
            effective_mode=ProviderMode.MOCK,
            provider="mock-llm",
            detail=fallback_reason or "Real LLM unavailable; using bundled mock analysis",
        )
    return ProviderSource(
        requested_mode=requested_mode,
        effective_mode=ProviderMode.MOCK,
        provider="mock-llm",
        detail="Bundled deterministic demo provider",
    )


def _real_provider_available(config: AppConfig) -> bool:
    available, _ = _real_provider_status(config)
    return available


def _real_provider_status(config: AppConfig) -> tuple[bool, Optional[str]]:
    if not config.use_real_llm:
        return False, None
    if not config.openai_api_key:
        return False, "OPENAI_API_KEY missing; using bundled mock analysis"
    try:
        importlib.import_module("openai")
    except ImportError:
        return False, "openai package not installed; using bundled mock analysis"
    return True, None


def _normalize_openai_base_url(base_url: Optional[str]) -> Optional[str]:
    if not base_url:
        return base_url
    parsed = urlsplit(base_url.strip())
    path = parsed.path.rstrip("/")
    if not path:
        path = "/v1"
    normalized = parsed._replace(path=path, query="", fragment="")
    return urlunsplit(normalized)


def _coerce_text_field(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        parts = [_coerce_text_field(item).strip() for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _extract_chat_completion_text(resp: Any) -> str:
    if isinstance(resp, str):
        preview = " ".join(resp.strip().split())[:160]
        raise RuntimeError(
            "LLM gateway returned HTML/text instead of OpenAI JSON payload. "
            f"Check OPENAI_BASE_URL; response preview: {preview}"
        )

    choices = getattr(resp, "choices", None)
    if not choices:
        raise RuntimeError("LLM gateway returned no choices in chat completion response")

    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None) if message is not None else None
    if isinstance(content, str) and content.strip():
        return content
    raise RuntimeError(
        "LLM gateway returned no message content. "
        "Check model compatibility and upstream gateway response format."
    )


def _extract_chat_completion_chunk_text(chunk: Any) -> str:
    choices = getattr(chunk, "choices", None)
    if not choices:
        return ""
    delta = getattr(choices[0], "delta", None)
    content = getattr(delta, "content", None) if delta is not None else None
    if isinstance(content, str):
        return content
    return ""


def _should_retry_stream(exc: RuntimeError) -> bool:
    return "no message content" in str(exc).lower()
