"""Configuration loading (env + CLI overrides).

No secrets are required: the MyPaisaa API is protected by IP whitelisting,
not credentials. All settings are configurable through environment variables
(see ``.env.example`` at the repository root) or CLI flags.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_API_BASE_URL = "https://vg1ypu45sc.execute-api.ap-south-1.amazonaws.com"
DEFAULT_API_STATEMENTS_PATH = "/fetchaccount/customerbankdetails/{userid}"


def _find_repo_root(start: Path) -> Path:
    """Walk up until a repo marker (.git / backend dir) is found."""
    current = start
    for _ in range(6):
        if (current / ".git").exists() or (current / "backend").is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return start


_REPO_ROOT = _find_repo_root(Path(__file__).resolve().parents[3])
load_dotenv(_REPO_ROOT / ".env")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "") or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class PipelineConfig:
    api_base_url: str = DEFAULT_API_BASE_URL
    api_statements_path: str = DEFAULT_API_STATEMENTS_PATH
    input_file: Path = _REPO_ROOT / "New Dataset" / "users.csv"
    output_dir: Path = _REPO_ROOT / "New Dataset" / "bank_statements"
    max_concurrent_users: int = 5
    max_retries: int = 3
    backoff_base_seconds: float = 2.0
    backoff_max_seconds: float = 60.0
    request_timeout_seconds: float = 60.0
    connect_timeout_seconds: float = 15.0
    requests_per_second: float = 0.0  # 0 = unlimited (concurrency still applies)
    user_agent: str = "airco-insights-statement-fetcher/1.0"


def load_config(**overrides) -> PipelineConfig:
    """Build config from env vars, then apply explicit overrides."""
    input_file = os.getenv("MYPAAISA_INPUT_FILE") or None
    output_dir = os.getenv("MYPAAISA_OUTPUT_DIR") or None
    cfg = PipelineConfig(
        api_base_url=os.getenv("MYPAAISA_API_BASE_URL", DEFAULT_API_BASE_URL),
        api_statements_path=os.getenv(
            "MYPAAISA_API_STATEMENTS_PATH", DEFAULT_API_STATEMENTS_PATH
        ),
        input_file=Path(input_file) if input_file else PipelineConfig.input_file,
        output_dir=Path(output_dir) if output_dir else PipelineConfig.output_dir,
        max_concurrent_users=_env_int("MAX_CONCURRENT_USERS", 5),
        max_retries=_env_int("MAX_RETRIES", 3),
        backoff_base_seconds=_env_float("BACKOFF_BASE_SECONDS", 2.0),
        backoff_max_seconds=_env_float("BACKOFF_MAX_SECONDS", 60.0),
        request_timeout_seconds=_env_float("REQUEST_TIMEOUT_SECONDS", 60.0),
        connect_timeout_seconds=_env_float("CONNECT_TIMEOUT_SECONDS", 15.0),
        requests_per_second=_env_float("REQUESTS_PER_SECOND", 0.0),
    )
    if overrides:
        changes = {}
        for key, value in overrides.items():
            if value is None:
                continue
            changes[key] = Path(value) if key in {"input_file", "output_dir"} else value
        if changes:
            cfg = PipelineConfig(**{**cfg.__dict__, **changes})
    return cfg
