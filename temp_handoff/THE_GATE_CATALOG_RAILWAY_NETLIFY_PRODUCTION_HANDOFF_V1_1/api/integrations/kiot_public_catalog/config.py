from __future__ import annotations

import ipaddress
import math
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError


MODULE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = MODULE_DIR / "data"
DEFAULT_LOG_DIR = MODULE_DIR / "logs"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
LOCAL_DEPLOYMENT_MODE = "local"
RAILWAY_DEPLOYMENT_MODE = "railway"
MIN_RETAIN_GENERATIONS = 2
MAX_RETAIN_GENERATIONS = 10


@dataclass(frozen=True)
class SyncConfig:
    secrets_path: Path
    cache_path: Path
    status_path: Path
    lock_path: Path
    log_path: Path
    retain_generations: int
    request_timeout_seconds: float = 60.0
    request_attempts: int = 4
    request_min_interval_seconds: float = 0.12
    page_size: int = 100


@dataclass(frozen=True)
class ApiConfig:
    cache_path: Path
    status_path: Path
    website_api_key: str
    internal_api_key: str
    max_cache_age_seconds: float
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    max_page_size: int = 100
    rate_limit_per_minute: int = 120
    log_path: Path = DEFAULT_LOG_DIR / "catalog_api.log"
    deployment_mode: str = LOCAL_DEPLOYMENT_MODE
    website_catalog_path: Path = DEFAULT_DATA_DIR / "website_catalog.json"
    website_catalog_status_path: Path = DEFAULT_DATA_DIR / "website_catalog_status.json"
    website_catalog_max_age_seconds: float = 10800.0
    website_catalog_max_products: int = 1000
    website_catalog_max_response_bytes: int = 5_000_000
    website_rate_limit_per_minute: int = 600


def _path_from_env(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).expanduser().resolve()


def load_sync_config() -> SyncConfig:
    data_dir = _path_from_env("KIOT_CATALOG_DATA_DIR", DEFAULT_DATA_DIR)
    log_dir = _path_from_env("KIOT_CATALOG_LOG_DIR", DEFAULT_LOG_DIR)
    return SyncConfig(
        secrets_path=_path_from_env(
            "KIOT_CATALOG_SECRETS_PATH", Path("~/.thegate/secrets.env").expanduser()
        ),
        cache_path=data_dir / "catalog.sqlite3",
        status_path=data_dir / "sync_status.json",
        lock_path=data_dir / ".sync.lock",
        log_path=log_dir / "catalog_sync.log",
        retain_generations=load_retain_generations(),
        request_timeout_seconds=float(
            os.environ.get("KIOT_CATALOG_REQUEST_TIMEOUT_SECONDS", "60")
        ),
        request_attempts=int(os.environ.get("KIOT_CATALOG_REQUEST_ATTEMPTS", "4")),
        request_min_interval_seconds=float(
            os.environ.get("KIOT_CATALOG_REQUEST_MIN_INTERVAL_SECONDS", "0.12")
        ),
        page_size=min(100, max(1, int(os.environ.get("KIOT_CATALOG_PAGE_SIZE", "100")))),
    )


def _load_api_key(name: str) -> str:
    value = os.environ.get(name, "")
    placeholders = ("CHANGE_ME", "REPLACE_ME", "EXAMPLE", "PLACEHOLDER")
    if not value or len(value) < 24 or any(mark in value.upper() for mark in placeholders):
        raise ConfigurationError(f"INVALID_OR_MISSING_{name}")
    return value


def validate_loopback(host: str) -> None:
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise ConfigurationError("NON_LOOPBACK_BIND_REJECTED")
    except ValueError as exc:
        raise ConfigurationError("BIND_HOST_MUST_BE_LITERAL_LOOPBACK") from exc


def validate_bind(host: str, deployment_mode: str) -> None:
    if deployment_mode == LOCAL_DEPLOYMENT_MODE:
        validate_loopback(host)
        return
    if deployment_mode == RAILWAY_DEPLOYMENT_MODE and host == "0.0.0.0":
        return
    if deployment_mode not in {LOCAL_DEPLOYMENT_MODE, RAILWAY_DEPLOYMENT_MODE}:
        raise ConfigurationError("INVALID_DEPLOYMENT_MODE")
    raise ConfigurationError("NON_LOOPBACK_BIND_REQUIRES_RAILWAY_MODE")


def _bounded_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise ConfigurationError(f"INVALID_{name}") from exc
    if value < minimum or value > maximum:
        raise ConfigurationError(f"INVALID_{name}")
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"INVALID_{name}") from exc
    if not math.isfinite(value) or value <= 0:
        raise ConfigurationError(f"INVALID_{name}")
    return value


def load_api_config() -> ApiConfig:
    data_dir = _path_from_env("KIOT_CATALOG_DATA_DIR", DEFAULT_DATA_DIR)
    log_dir = _path_from_env("KIOT_CATALOG_LOG_DIR", DEFAULT_LOG_DIR)
    website_key = _load_api_key("KIOT_CATALOG_WEBSITE_API_KEY")
    internal_key = _load_api_key("KIOT_CATALOG_INTERNAL_API_KEY")
    if website_key == internal_key:
        raise ConfigurationError("API_KEYS_MUST_DIFFER")
    max_cache_age_seconds = load_max_cache_age_seconds()
    deployment_mode = os.environ.get(
        "KIOT_CATALOG_DEPLOYMENT_MODE", LOCAL_DEPLOYMENT_MODE
    ).strip().lower()
    host = os.environ.get("KIOT_CATALOG_HOST", DEFAULT_HOST)
    validate_bind(host, deployment_mode)
    port_name = "PORT" if deployment_mode == RAILWAY_DEPLOYMENT_MODE else "KIOT_CATALOG_PORT"
    port = _bounded_int(port_name, DEFAULT_PORT, minimum=1, maximum=65535)
    max_page_size = min(
        100, max(1, int(os.environ.get("KIOT_CATALOG_MAX_PAGE_SIZE", "100")))
    )
    rate = _bounded_int(
        "KIOT_CATALOG_RATE_LIMIT_PER_MINUTE", 120, minimum=10, maximum=600
    )
    website_max_age = _positive_float(
        "KIOT_CATALOG_WEBSITE_MAX_AGE_SECONDS", max_cache_age_seconds
    )
    website_max_products = _bounded_int(
        "KIOT_CATALOG_WEBSITE_MAX_PRODUCTS", 1000, minimum=1, maximum=5000
    )
    website_max_response_bytes = _bounded_int(
        "KIOT_CATALOG_WEBSITE_MAX_RESPONSE_BYTES",
        5_000_000,
        minimum=10_000,
        maximum=10_000_000,
    )
    website_rate = _bounded_int(
        "KIOT_CATALOG_WEBSITE_RATE_LIMIT_PER_MINUTE",
        600,
        minimum=10,
        maximum=6000,
    )
    return ApiConfig(
        cache_path=data_dir / "catalog.sqlite3",
        status_path=data_dir / "sync_status.json",
        website_api_key=website_key,
        internal_api_key=internal_key,
        max_cache_age_seconds=max_cache_age_seconds,
        host=host,
        port=port,
        max_page_size=max_page_size,
        rate_limit_per_minute=rate,
        log_path=log_dir / "catalog_api.log",
        deployment_mode=deployment_mode,
        website_catalog_path=data_dir / "website_catalog.json",
        website_catalog_status_path=data_dir / "website_catalog_status.json",
        website_catalog_max_age_seconds=website_max_age,
        website_catalog_max_products=website_max_products,
        website_catalog_max_response_bytes=website_max_response_bytes,
        website_rate_limit_per_minute=website_rate,
    )


def load_max_cache_age_seconds() -> float:
    raw = os.environ.get("KIOT_CATALOG_MAX_CACHE_AGE_SECONDS")
    if raw is None or not raw.strip():
        raise ConfigurationError("MISSING_KIOT_CATALOG_MAX_CACHE_AGE_SECONDS")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError("INVALID_KIOT_CATALOG_MAX_CACHE_AGE_SECONDS") from exc
    if not math.isfinite(value) or value <= 0:
        raise ConfigurationError("INVALID_KIOT_CATALOG_MAX_CACHE_AGE_SECONDS")
    return value


def validate_retain_generations(value: object) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < MIN_RETAIN_GENERATIONS
        or value > MAX_RETAIN_GENERATIONS
    ):
        raise ConfigurationError("INVALID_KIOT_CATALOG_RETAIN_GENERATIONS")
    return value


def load_retain_generations() -> int:
    raw = os.environ.get("KIOT_CATALOG_RETAIN_GENERATIONS")
    if raw is None or not raw.strip():
        raise ConfigurationError("MISSING_KIOT_CATALOG_RETAIN_GENERATIONS")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            "INVALID_KIOT_CATALOG_RETAIN_GENERATIONS"
        ) from exc
    return validate_retain_generations(value)


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def verify_secret_file(path: Path) -> None:
    if not path.is_file():
        raise ConfigurationError("SECRET_STORE_MISSING")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ConfigurationError("SECRET_STORE_PERMISSIONS_UNSAFE")
