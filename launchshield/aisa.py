"""AIsa threat intel verification adapter."""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Optional, Protocol

import httpx

from .config import AppConfig, get_config


@dataclass
class AisaVerification:
    match_level: str
    intel_summary: str
    recommended_priority: str


class AisaProvider(Protocol):
    async def verify(self, subject: str, category: str) -> AisaVerification: ...


class MockAisaProvider:
    def __init__(self, config: AppConfig):
        self._config = config
        self._rng = random.Random(37)

    async def verify(self, subject: str, category: str) -> AisaVerification:
        await asyncio.sleep(self._config.demo_pace_seconds * 0.3)
        level = self._rng.choice(["strong", "partial", "weak"])
        priority = {
            "strong": "immediate",
            "partial": "high",
            "weak": "monitor",
        }[level]
        return AisaVerification(
            match_level=level,
            intel_summary=(
                f"AIsa corpus reports {level} correlation for {category} — "
                f"subject `{subject[:80]}` matches recent exploit chatter."
            ),
            recommended_priority=priority,
        )


class RealAisaProvider:
    def __init__(self, config: AppConfig):
        if not config.aisa_api_key or not config.aisa_base_url:
            raise RuntimeError("AIsa credentials missing")
        self._config = config
        self._client = httpx.AsyncClient(
            base_url=config.aisa_base_url,
            headers={"Authorization": f"Bearer {config.aisa_api_key}"},
            timeout=15.0,
        )

    async def verify(self, subject: str, category: str) -> AisaVerification:
        resp = await self._client.post(
            "/v1/verify",
            json={"subject": subject, "category": category},
        )
        resp.raise_for_status()
        data = resp.json()
        return AisaVerification(
            match_level=data.get("match_level", "weak"),
            intel_summary=data.get("intel_summary", ""),
            recommended_priority=data.get("recommended_priority", "monitor"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def build_provider(config: Optional[AppConfig] = None) -> AisaProvider:
    cfg = config or get_config()
    if cfg.use_real_aisa and cfg.aisa_api_key and cfg.aisa_base_url:
        return RealAisaProvider(cfg)
    return MockAisaProvider(cfg)
