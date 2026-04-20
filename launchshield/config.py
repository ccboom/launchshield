"""Central configuration loader for LaunchShield Swarm."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _candidate_dotenv_paths() -> list[Path]:
    repo_root = Path(__file__).resolve().parent.parent
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(path)
    return ordered


def _parse_dotenv_line(raw: str) -> tuple[str, str] | None:
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    if line.startswith("export "):
        line = line[len("export ") :].lstrip()
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_dotenv_into_environ() -> None:
    for path in _candidate_dotenv_paths():
        if not path.exists():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                parsed = _parse_dotenv_line(raw)
                if parsed is None:
                    continue
                key, value = parsed
                os.environ.setdefault(key, value)
        except OSError:
            continue


_load_dotenv_into_environ()


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None and value != "" else default


@dataclass
class AppConfig:
    """Runtime configuration. All fields read from env with sensible defaults."""

    app_env: str = field(default_factory=lambda: _get("APP_ENV", "development"))
    host: str = field(default_factory=lambda: _get("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(_get("PORT", "8000")))

    data_dir: Path = field(
        default_factory=lambda: Path(_get("LAUNCHSHIELD_DATA_DIR", "data")).resolve()
    )

    chrome_debug_url: str = field(
        default_factory=lambda: _get("CHROME_DEBUG_URL", "http://127.0.0.1:9222")
    )

    github_token: Optional[str] = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    openai_base_url: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_BASE_URL"))
    openai_model: str = field(default_factory=lambda: _get("OPENAI_MODEL", "gpt-4.1-mini"))

    circle_api_key: Optional[str] = field(default_factory=lambda: os.getenv("CIRCLE_API_KEY"))
    arc_rpc_url: str = field(
        default_factory=lambda: _get("ARC_RPC_URL", "https://rpc.testnet.arc.network")
    )
    arc_chain_id: int = field(default_factory=lambda: int(_get("ARC_CHAIN_ID", "5042002")))
    arc_wallet_address: Optional[str] = field(
        default_factory=lambda: os.getenv("ARC_WALLET_ADDRESS")
    )
    arc_private_key: Optional[str] = field(default_factory=lambda: os.getenv("ARC_PRIVATE_KEY"))
    arc_usdc_address: str = field(
        default_factory=lambda: _get(
            "ARC_USDC_ADDRESS", "0x3600000000000000000000000000000000000000"
        )
    )
    arc_merchant_address: Optional[str] = field(
        default_factory=lambda: os.getenv("ARC_MERCHANT_ADDRESS")
    )
    arc_explorer_base_url: str = field(
        default_factory=lambda: _get(
            "ARC_EXPLORER_BASE_URL", "https://testnet.arcscan.app"
        )
    )
    arc_payment_amount_override_usdc: Optional[float] = field(
        default_factory=lambda: (
            float(os.getenv("ARC_PAYMENT_AMOUNT_OVERRIDE_USDC"))
            if os.getenv("ARC_PAYMENT_AMOUNT_OVERRIDE_USDC")
            else None
        )
    )
    arc_tx_timeout_seconds: int = field(
        default_factory=lambda: int(_get("ARC_TX_TIMEOUT_SECONDS", "45"))
    )

    x402_gateway_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("X402_GATEWAY_BASE_URL")
    )
    x402_gateway_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("X402_GATEWAY_API_KEY")
    )

    aisa_api_key: Optional[str] = field(default_factory=lambda: os.getenv("AISA_API_KEY"))
    aisa_base_url: Optional[str] = field(default_factory=lambda: os.getenv("AISA_BASE_URL"))

    preset_repo_url: str = field(
        default_factory=lambda: _get(
            "PRESET_REPO_URL", "https://github.com/launchshield-demo/vulnerable-playground"
        )
    )
    preset_target_url: str = field(
        default_factory=lambda: _get(
            "PRESET_TARGET_URL", "https://vulnerable-playground.launchshield.dev"
        )
    )

    use_real_payments: bool = field(default_factory=lambda: _get_bool("USE_REAL_PAYMENTS", False))
    use_real_llm: bool = field(default_factory=lambda: _get_bool("USE_REAL_LLM", False))
    use_real_aisa: bool = field(default_factory=lambda: _get_bool("USE_REAL_AISA", False))
    use_real_github: bool = field(default_factory=lambda: _get_bool("USE_REAL_GITHUB", False))
    use_real_browser: bool = field(default_factory=lambda: _get_bool("USE_REAL_BROWSER", False))

    demo_pace_seconds: float = field(
        default_factory=lambda: float(_get("LAUNCHSHIELD_DEMO_PACE_SECONDS", "0.35"))
    )

    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    def ensure_dirs(self) -> None:
        self.runs_dir().mkdir(parents=True, exist_ok=True)


_config_singleton: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _config_singleton
    if _config_singleton is None:
        _config_singleton = AppConfig()
        _config_singleton.ensure_dirs()
    return _config_singleton


def reset_config_for_tests() -> None:
    global _config_singleton
    _config_singleton = None
