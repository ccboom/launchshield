"""Shared test fixtures for LaunchShield Swarm."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from launchshield import config as config_mod
from launchshield import orchestrator as orchestrator_mod
from launchshield import storage as storage_mod


@pytest.fixture(autouse=True)
def _isolated_runtime(monkeypatch: pytest.MonkeyPatch):
    data_dir = Path.cwd() / "data" / "pytest-runtime" / uuid4().hex
    data_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("LAUNCHSHIELD_DATA_DIR", str(data_dir))
    monkeypatch.setenv("LAUNCHSHIELD_DEMO_PACE_SECONDS", "0.0")
    monkeypatch.setenv("USE_REAL_PAYMENTS", "false")
    monkeypatch.setenv("USE_REAL_LLM", "false")
    monkeypatch.setenv("USE_REAL_AISA", "false")
    monkeypatch.setenv("USE_REAL_GITHUB", "false")
    monkeypatch.setenv("USE_REAL_BROWSER", "false")
    monkeypatch.setenv("PRESET_REPO_URL", "https://github.com/launchshield-demo/fixture")
    monkeypatch.setenv("PRESET_TARGET_URL", "http://127.0.0.1:9")

    config_mod.reset_config_for_tests()
    storage_mod.reset_registry_for_tests()
    orchestrator_mod.reset_orchestrator_for_tests()

    yield

    config_mod.reset_config_for_tests()
    storage_mod.reset_registry_for_tests()
    orchestrator_mod.reset_orchestrator_for_tests()
    shutil.rmtree(data_dir, ignore_errors=True)
