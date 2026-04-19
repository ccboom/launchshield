"""FastAPI entrypoint for LaunchShield Swarm."""
from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import get_config
from .models import (
    CreateRunRequest,
    CreateRunResponse,
    RunMode,
    RunSummary,
)
from .orchestrator import get_orchestrator
from .pricing import TOOL_PRICES_USD
from .presets import tier_for
from .repo_source import parse_github_url
from .storage import get_registry


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="LaunchShield Swarm", version="0.1.0")

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        cfg = get_config()
        preset_tier = tier_for(RunMode.PRESET_STRESS)
        custom_tier = tier_for(RunMode.CUSTOM_STANDARD)
        context = {
            "preset_total": preset_tier.total(),
            "custom_total": custom_tier.total(),
            "preset_repo_url": cfg.preset_repo_url,
            "preset_target_url": cfg.preset_target_url,
            "tool_prices": TOOL_PRICES_USD,
        }
        return templates.TemplateResponse(request, "index.html", context)

    @app.get("/api/health")
    async def health() -> dict:
        cfg = get_config()
        return {
            "status": "ok",
            "app_env": cfg.app_env,
            "use_real_payments": cfg.use_real_payments,
            "use_real_llm": cfg.use_real_llm,
            "use_real_aisa": cfg.use_real_aisa,
            "use_real_github": cfg.use_real_github,
            "use_real_browser": cfg.use_real_browser,
        }

    @app.post("/api/runs", response_model=CreateRunResponse)
    async def create_run(payload: CreateRunRequest) -> CreateRunResponse:
        if payload.mode == RunMode.CUSTOM_STANDARD:
            if not payload.repo_url or not payload.target_url:
                raise HTTPException(status_code=400, detail="repo_url and target_url are required")
            try:
                parse_github_url(payload.repo_url)
            except ValueError:
                raise HTTPException(status_code=400, detail="repo_url must be a public GitHub URL")
            if not (payload.target_url.startswith("http://") or payload.target_url.startswith("https://")):
                raise HTTPException(status_code=400, detail="target_url must be http:// or https://")

        orchestrator = get_orchestrator()
        run = orchestrator.build_run(payload)
        await orchestrator.start(run)

        return CreateRunResponse(
            run_id=run.run_id,
            status=run.status,
            mode=run.mode,
            stream_url=f"/api/runs/{run.run_id}/events",
            summary_url=f"/api/runs/{run.run_id}",
        )

    @app.get("/api/runs/{run_id}", response_model=RunSummary)
    async def get_run(run_id: str) -> RunSummary:
        run = get_registry().get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        return RunSummary.from_run(run)

    @app.get("/api/runs/{run_id}/events")
    async def stream_run(run_id: str) -> StreamingResponse:
        run = get_registry().get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        orchestrator = get_orchestrator()

        async def _iter() -> AsyncIterator[bytes]:
            async for event in orchestrator.bus.subscribe(run_id):
                yield event.to_sse().encode("utf-8")

        return StreamingResponse(
            _iter(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return app


app = create_app()
