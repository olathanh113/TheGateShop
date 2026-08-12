from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

from .config import MODULE_DIR, load_api_config, load_sync_config
from .errors import CatalogError, ConfigurationError
from .secrets import load_kiotviet_credentials


REQUIRED_PATH_ENV = (
    "KIOT_CATALOG_DATA_DIR",
    "KIOT_CATALOG_LOG_DIR",
    "KIOT_CATALOG_SECRETS_PATH",
)


def _explicit_absolute_path(name: str) -> Path:
    raw = os.environ.get(name, "")
    if not raw.strip():
        raise ConfigurationError(f"MISSING_DEPLOYMENT_ENV_{name}")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ConfigurationError(f"DEPLOYMENT_PATH_NOT_ABSOLUTE_{name}")
    if candidate.is_symlink():
        raise ConfigurationError(f"DEPLOYMENT_PATH_SYMLINK_REJECTED_{name}")
    return candidate.resolve()


def _require_private_directory(path: Path, code: str) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ConfigurationError(f"{code}_MISSING_OR_UNSAFE")
    if stat.S_IMODE(path.stat().st_mode) != 0o700 or not os.access(path, os.W_OK):
        raise ConfigurationError(f"{code}_PERMISSIONS_UNSAFE")


def validate_deployment_configuration() -> dict[str, object]:
    """Validate deployment metadata and secret structure without network access."""
    raw_paths = {name: _explicit_absolute_path(name) for name in REQUIRED_PATH_ENV}
    data_dir = raw_paths["KIOT_CATALOG_DATA_DIR"]
    log_dir = raw_paths["KIOT_CATALOG_LOG_DIR"]
    secrets_path = raw_paths["KIOT_CATALOG_SECRETS_PATH"]

    if data_dir == log_dir:
        raise ConfigurationError("DEPLOYMENT_DATA_AND_LOG_DIR_MUST_DIFFER")
    for path in (data_dir, log_dir, secrets_path):
        if path == MODULE_DIR or path.is_relative_to(MODULE_DIR):
            raise ConfigurationError("DEPLOYMENT_RUNTIME_PATH_INSIDE_SOURCE")

    _require_private_directory(data_dir, "DEPLOYMENT_DATA_DIR")
    _require_private_directory(log_dir, "DEPLOYMENT_LOG_DIR")
    if secrets_path.is_symlink():
        raise ConfigurationError("DEPLOYMENT_SECRET_STORE_SYMLINK_REJECTED")

    sync_config = load_sync_config()
    api_config = load_api_config()
    if sync_config.cache_path.parent != data_dir or api_config.cache_path.parent != data_dir:
        raise ConfigurationError("DEPLOYMENT_DATA_DIR_RESOLUTION_MISMATCH")
    if sync_config.log_path.parent != log_dir or api_config.log_path.parent != log_dir:
        raise ConfigurationError("DEPLOYMENT_LOG_DIR_RESOLUTION_MISMATCH")
    if sync_config.secrets_path != secrets_path:
        raise ConfigurationError("DEPLOYMENT_SECRET_PATH_RESOLUTION_MISMATCH")

    credentials = load_kiotviet_credentials(secrets_path)
    credentials = None
    return {
        "status": "PASS",
        "network_call_performed": False,
        "data_directory": "validated_private_writable",
        "log_directory": "validated_private_writable",
        "secret_store": "validated_private_structure",
        "api_bind": (
            "railway_all_interfaces"
            if api_config.deployment_mode == "railway"
            else "loopback"
        ),
        "retention_generations": sync_config.retain_generations,
        "max_cache_age_seconds": api_config.max_cache_age_seconds,
    }


def main() -> int:
    try:
        print(json.dumps(validate_deployment_configuration(), sort_keys=True))
        return 0
    except CatalogError as exc:
        print(json.dumps({"status": "FAILED", "error_code": exc.code}, sort_keys=True))
        return 2
    except Exception as exc:
        code = "UNEXPECTED_" + type(exc).__name__.upper()
        print(json.dumps({"status": "FAILED", "error_code": code}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
