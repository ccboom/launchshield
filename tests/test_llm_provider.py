from __future__ import annotations

import asyncio
import sys
import types

from launchshield.config import AppConfig
from launchshield import llm as llm_mod
from launchshield.llm import OpenAIProvider


def test_app_config_reads_openai_base_url_from_env(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    cfg = AppConfig()
    assert cfg.openai_base_url == "https://example.test/v1"


def test_openai_provider_passes_base_url_to_sdk(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/")

    cfg = AppConfig()
    OpenAIProvider(cfg)

    assert captured["api_key"] == "test-key"
    assert captured["base_url"] == "https://example.test/v1"


def test_build_provider_falls_back_to_mock_when_openai_sdk_missing(monkeypatch) -> None:
    monkeypatch.setenv("USE_REAL_LLM", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_import_module(name: str):
        if name == "openai":
            raise ImportError("missing openai")
        return types.SimpleNamespace()

    monkeypatch.setattr(llm_mod.importlib, "import_module", fake_import_module)

    cfg = AppConfig()
    provider = llm_mod.build_provider(cfg)

    assert isinstance(provider, llm_mod.MockLLMProvider)


def test_describe_provider_marks_mock_when_openai_sdk_missing(monkeypatch) -> None:
    monkeypatch.setenv("USE_REAL_LLM", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_import_module(name: str):
        if name == "openai":
            raise ImportError("missing openai")
        return types.SimpleNamespace()

    monkeypatch.setattr(llm_mod.importlib, "import_module", fake_import_module)

    cfg = AppConfig()
    source = llm_mod.describe_provider(cfg)

    assert source.requested_mode == "real"
    assert source.effective_mode == "mock"
    assert source.provider == "mock-llm"
    assert "package not installed" in source.detail


def test_extract_chat_completion_text_raises_for_empty_content() -> None:
    response = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=None))]
    )

    try:
        llm_mod._extract_chat_completion_text(response)
    except RuntimeError as exc:
        assert "no message content" in str(exc)
    else:
        raise AssertionError("expected missing-content error")


def test_openai_provider_surfaces_html_gateway_misconfiguration(monkeypatch) -> None:
    class _FakeCompletions:
        async def create(self, **kwargs):
            return "<html>gateway</html>"

    class _FakeChat:
        completions = _FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/")

    provider = OpenAIProvider(AppConfig())

    async def _run():
        await provider.deep_analysis(
            llm_mod.DeepAnalysisInput(
                snippet="eval(user_input)",
                rule="dangerous_eval",
                language="python",
                evidence="demo",
            )
        )

    try:
        asyncio.run(_run())
    except RuntimeError as exc:
        assert "returned HTML/text" in str(exc)
        assert "Check OPENAI_BASE_URL" in str(exc)
    else:
        raise AssertionError("expected HTML gateway error")


def test_openai_provider_falls_back_to_stream_when_content_missing(monkeypatch) -> None:
    class _FakeStream:
        def __init__(self, chunks):
            self._chunks = iter(chunks)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._chunks)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class _FakeCompletions:
        async def create(self, **kwargs):
            if kwargs.get("stream"):
                return _FakeStream(
                    [
                        types.SimpleNamespace(
                            choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content='{"risk_summary":"Stream risk",'))]
                        ),
                        types.SimpleNamespace(
                            choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content='"exploit_path":"Stream exploit",'))]
                        ),
                        types.SimpleNamespace(
                            choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content='"impact_scope":"Stream impact",'))]
                        ),
                        types.SimpleNamespace(
                            choices=[types.SimpleNamespace(delta=types.SimpleNamespace(content='"remediation_direction":"Stream remediation"}'))]
                        ),
                    ]
                )
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=None))]
            )

    class _FakeChat:
        completions = _FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/")

    provider = OpenAIProvider(AppConfig())

    async def _run():
        return await provider.deep_analysis(
            llm_mod.DeepAnalysisInput(
                snippet="eval(user_input)",
                rule="dangerous_eval",
                language="python",
                evidence="demo",
            )
        )

    result = asyncio.run(_run())

    assert result.risk_summary == "Stream risk"
    assert result.exploit_path == "Stream exploit"
    assert result.impact_scope == "Stream impact"
    assert result.remediation_direction == "Stream remediation"


def test_openai_provider_coerces_list_validation_steps_to_string(monkeypatch) -> None:
    class _FakeCompletions:
        async def create(self, **kwargs):
            return types.SimpleNamespace(
                choices=[
                    types.SimpleNamespace(
                        message=types.SimpleNamespace(
                            content=(
                                '{"why":"because","patch_summary":"patch summary",'
                                '"suggested_code_change":"patch code",'
                                '"validation_steps":["step one","step two"]}'
                            )
                        )
                    )
                ]
            )

    class _FakeChat:
        completions = _FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/")

    provider = OpenAIProvider(AppConfig())

    async def _run():
        return await provider.fix_suggestion(
            llm_mod.FixSuggestionInput(
                snippet="eval(user_input)",
                rule="dangerous_eval",
                language="python",
                analysis=llm_mod.DeepAnalysisResult(
                    risk_summary="risk",
                    exploit_path="exploit",
                    impact_scope="impact",
                    remediation_direction="remediation",
                ),
            )
        )

    result = asyncio.run(_run())

    assert result.validation_steps == "step one\nstep two"
