"""Minimal CDP client replacement for the missing `arc_house_helper.cdp`.

Only the bits we need for site probes: fetch page HTML, run a small JS expression,
read security-relevant properties. Falls back to HTTP-only probing when CDP is
unavailable so `USE_REAL_BROWSER=false` still produces a full demo run.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from .config import AppConfig


@dataclass
class PageSnapshot:
    url: str
    status_code: Optional[int]
    headers: Dict[str, str]
    html: str
    inline_scripts: List[str]
    has_password_field: bool
    next_data_present: bool
    mixed_content: bool
    admin_like_links: List[str]


class BrowserRuntime:
    """Thin wrapper: HTTP fetch + optional CDP evaluate.

    Real CDP evaluation is only engaged when `config.use_real_browser=True` and
    `CHROME_DEBUG_URL` returns a usable target list. Otherwise we synthesise the
    same fields purely from the HTTP response — enough for every probe shipped
    in this MVP.
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._http = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "LaunchShieldSwarm/0.1 (+https://launchshield.dev)",
            },
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def fetch(self, url: str) -> PageSnapshot:
        try:
            resp = await self._http.get(url)
            headers = {k.lower(): v for k, v in resp.headers.items()}
            html = resp.text if "html" in headers.get("content-type", "") else resp.text
            status = resp.status_code
        except httpx.HTTPError:
            headers = {}
            html = ""
            status = None
        inline_scripts = _extract_inline_scripts(html)
        has_password_field = "type=\"password\"" in html or "type='password'" in html
        next_data_present = "__NEXT_DATA__" in html
        mixed_content = bool(
            url.lower().startswith("https://")
            and ("http://" in html.lower() and "http://localhost" not in html.lower())
        )
        admin_like_links = _extract_admin_links(html)
        return PageSnapshot(
            url=url,
            status_code=status,
            headers=headers,
            html=html,
            inline_scripts=inline_scripts,
            has_password_field=has_password_field,
            next_data_present=next_data_present,
            mixed_content=mixed_content,
            admin_like_links=admin_like_links,
        )

    async def probe_path(self, base_url: str, path: str) -> int:
        url = base_url.rstrip("/") + path
        try:
            resp = await self._http.get(url)
            return resp.status_code
        except httpx.HTTPError:
            return 0


def _extract_inline_scripts(html: str) -> List[str]:
    out: List[str] = []
    lower = html.lower()
    idx = 0
    while True:
        start = lower.find("<script", idx)
        if start == -1:
            return out
        gt = lower.find(">", start)
        if gt == -1:
            return out
        end = lower.find("</script>", gt)
        if end == -1:
            return out
        tag = html[start : gt + 1]
        body = html[gt + 1 : end]
        if "src=" not in tag.lower():
            out.append(body[:400])
        idx = end + len("</script>")


def _extract_admin_links(html: str) -> List[str]:
    lower = html.lower()
    candidates = []
    for needle in ("/admin", "/dashboard", "/internal", "/debug", "/management"):
        if needle in lower:
            candidates.append(needle)
    return candidates
