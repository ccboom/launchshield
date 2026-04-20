"""Browser runtime with CDP-backed page snapshots and HTTP fallback."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
import websockets

from .config import AppConfig
from .models import ProviderMode, ProviderSource


_HTTP_USER_AGENT = "LaunchShieldSwarm/0.1 (+https://launchshield.dev)"
_SNAPSHOT_SCRIPT = r"""
(() => {
  const inlineScripts = Array.from(document.scripts || [])
    .filter((script) => !script.src)
    .slice(0, 10)
    .map((script) => (script.textContent || "").slice(0, 400));
  const links = Array.from(document.querySelectorAll("a[href]"))
    .map((node) => node.getAttribute("href") || "")
    .filter(Boolean);
  const resourceCandidates = [
    ...Array.from(document.querySelectorAll("[src]")).map((node) => node.getAttribute("src") || ""),
    ...Array.from(document.querySelectorAll("link[href]")).map((node) => node.getAttribute("href") || ""),
    ...links,
  ];
  const mixedContent = window.location.protocol === "https:" && resourceCandidates.some((value) => {
    const lower = value.toLowerCase();
    return lower.startsWith("http://") && !lower.startsWith("http://localhost");
  });
  const adminLikeLinks = links.filter((value) => /\/(admin|dashboard|internal|debug|management)/i.test(value)).slice(0, 10);
  return {
    url: window.location.href,
    title: document.title || "",
    html: (document.documentElement ? document.documentElement.outerHTML : "").slice(0, 200000),
    inlineScripts,
    hasPasswordField: !!document.querySelector('input[type="password"]'),
    nextDataPresent: !!document.getElementById("__NEXT_DATA__") || inlineScripts.some((body) => body.includes("__NEXT_DATA__")),
    mixedContent,
    adminLikeLinks,
  };
})()
""".strip()


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
    capture_source: str = "http-fallback"
    title: str = ""
    source_detail: Optional[str] = None


class _CDPSession:
    def __init__(self, websocket) -> None:
        self._websocket = websocket
        self._next_id = 0

    async def call(self, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        self._next_id += 1
        call_id = self._next_id
        await self._websocket.send(
            json.dumps(
                {
                    "id": call_id,
                    "method": method,
                    "params": params or {},
                }
            )
        )
        while True:
            raw = await self._websocket.recv()
            message = json.loads(raw)
            if message.get("id") != call_id:
                continue
            if "error" in message:
                error = message["error"]
                raise RuntimeError(f"CDP {method} failed: {error}")
            return message.get("result") or {}

    async def navigate_and_snapshot(self, url: str, *, timeout_seconds: float = 15.0) -> PageSnapshot:
        await self.call("Page.enable")
        await self.call("Runtime.enable")
        await self.call("Network.enable")
        navigate_result = await self.call("Page.navigate", {"url": url})
        resolved_url = str(navigate_result.get("url") or url)
        response_headers: dict[str, str] = {}
        status_code: Optional[int] = None
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                raw = await asyncio.wait_for(self._websocket.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break
            message = json.loads(raw)
            method = message.get("method")
            params = message.get("params") or {}
            if method == "Network.responseReceived" and params.get("type") == "Document":
                response = params.get("response") or {}
                if response.get("url"):
                    resolved_url = str(response["url"])
                if response.get("status") is not None:
                    status_code = int(response["status"])
                response_headers = {
                    str(key).lower(): str(value)
                    for key, value in (response.get("headers") or {}).items()
                }
            if method in {"Page.loadEventFired", "Page.domContentEventFired"}:
                break

        eval_result = await self.call(
            "Runtime.evaluate",
            {
                "expression": _SNAPSHOT_SCRIPT,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        value = (eval_result.get("result") or {}).get("value") or {}
        return PageSnapshot(
            url=str(value.get("url") or resolved_url),
            status_code=status_code,
            headers=response_headers,
            html=str(value.get("html") or ""),
            inline_scripts=[str(item) for item in value.get("inlineScripts") or []],
            has_password_field=bool(value.get("hasPasswordField")),
            next_data_present=bool(value.get("nextDataPresent")),
            mixed_content=bool(value.get("mixedContent")),
            admin_like_links=[str(item) for item in value.get("adminLikeLinks") or []],
            capture_source="cdp-browser",
            title=str(value.get("title") or ""),
        )


class BrowserRuntime:
    """Thin wrapper around CDP, with graceful HTTP fallback."""

    def __init__(self, config: AppConfig):
        self._config = config
        self._http = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": _HTTP_USER_AGENT},
        )
        self._provider_source: Optional[ProviderSource] = None

    async def aclose(self) -> None:
        await self._http.aclose()

    async def describe_provider(self) -> ProviderSource:
        if self._provider_source is not None:
            return self._provider_source
        if not self._config.use_real_browser:
            self._provider_source = ProviderSource(
                requested_mode=ProviderMode.MOCK,
                effective_mode=ProviderMode.MOCK,
                provider="http-fallback",
                detail="USE_REAL_BROWSER=false",
            )
            return self._provider_source
        try:
            version = await self._browser_version()
        except Exception as exc:
            self._provider_source = ProviderSource(
                requested_mode=ProviderMode.REAL,
                effective_mode=ProviderMode.MOCK,
                provider="http-fallback",
                detail=f"CDP unavailable at {self._config.chrome_debug_url}: {exc}",
            )
            return self._provider_source
        product = str(version.get("Browser") or version.get("User-Agent") or "cdp-browser")
        self._provider_source = ProviderSource(
            requested_mode=ProviderMode.REAL,
            effective_mode=ProviderMode.REAL,
            provider="cdp-browser",
            detail=product,
        )
        return self._provider_source

    async def fetch(self, url: str) -> PageSnapshot:
        if self._config.use_real_browser:
            try:
                snapshot = await self._fetch_via_cdp(url)
                self._provider_source = ProviderSource(
                    requested_mode=ProviderMode.REAL,
                    effective_mode=ProviderMode.REAL,
                    provider="cdp-browser",
                    detail=self._config.chrome_debug_url,
                )
                return snapshot
            except Exception as exc:
                self._provider_source = ProviderSource(
                    requested_mode=ProviderMode.REAL,
                    effective_mode=ProviderMode.MOCK,
                    provider="http-fallback",
                    detail=f"CDP failed, using HTTP fallback: {exc}",
                )
        else:
            self._provider_source = ProviderSource(
                requested_mode=ProviderMode.MOCK,
                effective_mode=ProviderMode.MOCK,
                provider="http-fallback",
                detail="USE_REAL_BROWSER=false",
            )
        return await self._fetch_via_http(url)

    async def probe_path(self, base_url: str, path: str) -> int:
        url = base_url.rstrip("/") + path
        snapshot = await self.fetch(url)
        return snapshot.status_code or 0

    async def _browser_version(self) -> dict[str, Any]:
        resp = await self._http.get(f"{self._config.chrome_debug_url.rstrip('/')}/json/version")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("unexpected /json/version payload")
        return data

    async def _fetch_via_cdp(self, url: str) -> PageSnapshot:
        target = await self._open_cdp_target(url)
        ws_url = target.get("webSocketDebuggerUrl")
        target_id = target.get("id")
        if not ws_url or not target_id:
            raise RuntimeError("CDP target missing websocket URL")
        try:
            async with websockets.connect(ws_url, open_timeout=5, close_timeout=1, max_size=4_000_000) as websocket:
                session = _CDPSession(websocket)
                return await session.navigate_and_snapshot(url)
        finally:
            await self._close_cdp_target(str(target_id))

    async def _open_cdp_target(self, url: str) -> dict[str, Any]:
        encoded = quote(url, safe="")
        endpoint = f"{self._config.chrome_debug_url.rstrip('/')}/json/new?{encoded}"
        last_error: Optional[Exception] = None
        for method in ("PUT", "GET"):
            try:
                resp = await self._http.request(method, endpoint)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict):
                    raise RuntimeError("unexpected /json/new payload")
                return data
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def _close_cdp_target(self, target_id: str) -> None:
        endpoint = f"{self._config.chrome_debug_url.rstrip('/')}/json/close/{target_id}"
        for method in ("GET", "PUT"):
            try:
                await self._http.request(method, endpoint)
                return
            except Exception:
                continue

    async def _fetch_via_http(self, url: str) -> PageSnapshot:
        try:
            resp = await self._http.get(url)
            headers = {k.lower(): v for k, v in resp.headers.items()}
            html = resp.text
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
            capture_source="http-fallback",
            source_detail="Fallback HTML fetch",
        )


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
