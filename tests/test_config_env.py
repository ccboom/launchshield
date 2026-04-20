from __future__ import annotations

import importlib
import sys
from pathlib import Path


def _reload_config_module(workdir: Path, monkeypatch):
    monkeypatch.chdir(workdir)
    sys.modules.pop("launchshield.config", None)
    return importlib.import_module("launchshield.config")


def test_app_config_reads_arc_private_key_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text(
        "ARC_PRIVATE_KEY=0xfrom-dotenv\n"
        "ARC_WALLET_ADDRESS=0xwallet\n",
        encoding="utf-8",
    )

    config_mod = _reload_config_module(tmp_path, monkeypatch)
    cfg = config_mod.AppConfig()

    assert cfg.arc_private_key == "0xfrom-dotenv"
    assert cfg.arc_wallet_address == "0xwallet"


def test_os_environment_wins_over_dotenv(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("ARC_PRIVATE_KEY=0xfrom-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("ARC_PRIVATE_KEY", "0xfrom-env")

    config_mod = _reload_config_module(tmp_path, monkeypatch)
    cfg = config_mod.AppConfig()

    assert cfg.arc_private_key == "0xfrom-env"
