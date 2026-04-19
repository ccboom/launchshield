"""JSON persistence and in-process run registry."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .config import get_config
from .models import ScanRun


class RunRegistry:
    """Thread-safe in-process registry that also persists to disk."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runs: Dict[str, ScanRun] = {}
        self._load_existing()

    @property
    def runs_dir(self) -> Path:
        return get_config().runs_dir()

    def _run_path(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def artifacts_dir(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}-artifacts"

    def _load_existing(self) -> None:
        runs_dir = self.runs_dir
        if not runs_dir.exists():
            return
        for path in runs_dir.glob("*.json"):
            try:
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
                run = ScanRun.model_validate(data)
                self._runs[run.run_id] = run
            except Exception:
                continue

    def save(self, run: ScanRun) -> None:
        with self._lock:
            self._runs[run.run_id] = run
            path = self._run_path(run.run_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(run.model_dump_json(indent=2), encoding="utf-8")
            tmp.replace(path)

    def get(self, run_id: str) -> Optional[ScanRun]:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> List[ScanRun]:
        with self._lock:
            return list(self._runs.values())

    def write_artifacts(self, run: ScanRun) -> None:
        adir = self.artifacts_dir(run.run_id)
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "summary.json").write_text(
            run.model_dump_json(indent=2), encoding="utf-8"
        )
        (adir / "invocations.json").write_text(
            json.dumps(
                [inv.model_dump(mode="json") for inv in run.tool_invocations], indent=2
            ),
            encoding="utf-8",
        )
        (adir / "findings.json").write_text(
            json.dumps([f.model_dump(mode="json") for f in run.findings], indent=2),
            encoding="utf-8",
        )
        (adir / "profitability.json").write_text(
            run.profitability.model_dump_json(indent=2), encoding="utf-8"
        )


_registry_singleton: Optional[RunRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> RunRegistry:
    global _registry_singleton
    with _registry_lock:
        if _registry_singleton is None:
            _registry_singleton = RunRegistry()
        return _registry_singleton


def reset_registry_for_tests() -> None:
    global _registry_singleton
    with _registry_lock:
        _registry_singleton = None
