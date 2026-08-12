from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import math
import os
import random
import signal
import stat
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .api import create_server
from .cache import CacheReader
from .cli import build_logger
from .config import (
    RAILWAY_DEPLOYMENT_MODE,
    ApiConfig,
    SyncConfig,
    ensure_private_directory,
    load_api_config,
    load_sync_config,
)
from .deployment_check import validate_deployment_configuration
from .errors import CacheUnavailable, CatalogError, ConfigurationError
from .sync import CatalogSynchronizer
from .website_catalog import (
    GoogleSheetsReadonlyAdapter,
    TARGET_SPREADSHEET_ID,
    WebsiteCatalogBuilder,
    WebsiteCatalogStore,
    decode_service_account_b64,
)


RUNTIME_ROOT = Path("/runtime")
SYNC_DISABLED_FILENAME = "SYNC_DISABLED"


@dataclass(frozen=True)
class RailwayRuntimeSettings:
    sync_config: SyncConfig
    api_config: ApiConfig
    cadence_seconds: int
    retry_base_seconds: float
    retry_max_seconds: float
    google_timeout_seconds: float
    google_attempts: int
    sync_enabled: bool
    service_account_b64: str
    sync_disabled_path: Path


def _strict_bool(name: str, *, default: str | None = None) -> bool:
    raw = os.environ.get(name, default)
    if raw == "true":
        return True
    if raw == "false":
        return False
    raise ConfigurationError(f"INVALID_{name}")


def _bounded_int(name: str, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "")
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"INVALID_{name}") from exc
    if value < minimum or value > maximum:
        raise ConfigurationError(f"INVALID_{name}")
    return value


def _bounded_float(name: str, *, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, "")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"INVALID_{name}") from exc
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ConfigurationError(f"INVALID_{name}")
    return value


def ensure_runtime_directories(root: Path = RUNTIME_ROOT) -> dict[str, Path]:
    if not root.is_absolute() or root.is_symlink():
        raise ConfigurationError("RUNTIME_ROOT_UNSAFE")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    paths = {name: root / name for name in ("data", "logs", "secrets")}
    for path in paths.values():
        if path.is_symlink():
            raise ConfigurationError("RUNTIME_DIRECTORY_SYMLINK_REJECTED")
        ensure_private_directory(path)
        if stat.S_IMODE(path.stat().st_mode) != 0o700 or not os.access(path, os.W_OK):
            raise ConfigurationError("RUNTIME_DIRECTORY_PERMISSIONS_UNSAFE")
    return paths


def materialize_kiot_secret(path: Path, values: dict[str, str]) -> None:
    expected = ("KV_RETAILER", "KV_CLIENT_ID", "KV_CLIENT_SECRET")
    placeholders = ("REPLACE", "CHANGE_ME", "PLACEHOLDER", "EXAMPLE")
    if set(values) != set(expected) or any(
        not isinstance(values[name], str)
        or not values[name]
        or "\n" in values[name]
        or values[name] != values[name].strip()
        or any(mark in values[name].upper() for mark in placeholders)
        for name in expected
    ):
        raise ConfigurationError("KIOT_RUNTIME_SECRET_INVALID")
    if path.is_symlink():
        raise ConfigurationError("KIOT_RUNTIME_SECRET_SYMLINK_REJECTED")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for name in expected:
                handle.write(f"{name}={values[name]}\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        path.chmod(0o600)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if temp.exists() and not temp.is_symlink():
            temp.unlink()


def prepare_railway_environment(root: Path = RUNTIME_ROOT) -> dict[str, Path]:
    paths = ensure_runtime_directories(root)
    secret_path = paths["secrets"] / "kiot.env"
    materialize_kiot_secret(
        secret_path,
        {
            "KV_RETAILER": os.environ.get("KV_RETAILER", ""),
            "KV_CLIENT_ID": os.environ.get("KV_CLIENT_ID", ""),
            "KV_CLIENT_SECRET": os.environ.get("KV_CLIENT_SECRET", ""),
        },
    )
    os.environ["KIOT_CATALOG_DATA_DIR"] = str(paths["data"])
    os.environ["KIOT_CATALOG_LOG_DIR"] = str(paths["logs"])
    os.environ["KIOT_CATALOG_SECRETS_PATH"] = str(secret_path)
    return paths


def load_railway_runtime_settings() -> RailwayRuntimeSettings:
    if os.environ.get("KIOT_CATALOG_DEPLOYMENT_MODE") != RAILWAY_DEPLOYMENT_MODE:
        raise ConfigurationError("RAILWAY_DEPLOYMENT_MODE_REQUIRED")
    if os.environ.get("KIOT_CATALOG_HOST") != "0.0.0.0":
        raise ConfigurationError("RAILWAY_BIND_HOST_INVALID")
    if os.environ.get("RAILWAY_VOLUME_MOUNT_PATH") != str(RUNTIME_ROOT):
        raise ConfigurationError("RAILWAY_VOLUME_MOUNT_PATH_INVALID")
    if os.environ.get("GOOGLE_SHEET_ID") != TARGET_SPREADSHEET_ID:
        raise ConfigurationError("GOOGLE_SHEET_ID_MISMATCH")
    cadence = _bounded_int(
        "KIOT_CATALOG_SYNC_CADENCE_SECONDS", minimum=3600, maximum=3600
    )
    retry_base = _bounded_float(
        "KIOT_CATALOG_WORKER_RETRY_BASE_SECONDS", minimum=5.0, maximum=300.0
    )
    retry_max = _bounded_float(
        "KIOT_CATALOG_WORKER_RETRY_MAX_SECONDS", minimum=retry_base, maximum=1800.0
    )
    google_timeout = _bounded_float(
        "GOOGLE_SHEETS_TIMEOUT_SECONDS", minimum=1.0, maximum=60.0
    )
    google_attempts = _bounded_int("GOOGLE_SHEETS_ATTEMPTS", minimum=1, maximum=5)
    service_account_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "")
    decode_service_account_b64(service_account_b64)
    sync_config = load_sync_config()
    api_config = load_api_config()
    if sync_config.cache_path.parent != RUNTIME_ROOT / "data":
        raise ConfigurationError("RAILWAY_DATA_PATH_INVALID")
    if sync_config.log_path.parent != RUNTIME_ROOT / "logs":
        raise ConfigurationError("RAILWAY_LOG_PATH_INVALID")
    if sync_config.secrets_path != RUNTIME_ROOT / "secrets" / "kiot.env":
        raise ConfigurationError("RAILWAY_SECRET_PATH_INVALID")
    if api_config.website_catalog_max_products < 1000:
        raise ConfigurationError("WEBSITE_PRODUCT_LIMIT_BELOW_SUPPORTED_MINIMUM")
    return RailwayRuntimeSettings(
        sync_config=sync_config,
        api_config=api_config,
        cadence_seconds=cadence,
        retry_base_seconds=retry_base,
        retry_max_seconds=retry_max,
        google_timeout_seconds=google_timeout,
        google_attempts=google_attempts,
        sync_enabled=_strict_bool("KIOT_CATALOG_SYNC_ENABLED", default="false"),
        service_account_b64=service_account_b64,
        sync_disabled_path=RUNTIME_ROOT / "data" / SYNC_DISABLED_FILENAME,
    )


def validate_railway_preflight(settings: RailwayRuntimeSettings) -> dict[str, Any]:
    deployment = validate_deployment_configuration()
    if settings.api_config.deployment_mode != RAILWAY_DEPLOYMENT_MODE:
        raise ConfigurationError("RAILWAY_API_MODE_INVALID")
    if settings.api_config.host != "0.0.0.0":
        raise ConfigurationError("RAILWAY_API_BIND_INVALID")
    return {
        "status": "PASS",
        "network_call_performed": False,
        "deployment_mode": RAILWAY_DEPLOYMENT_MODE,
        "api_bind": "railway_all_interfaces",
        "volume_mount": "validated_runtime_volume",
        "google_secret": "validated_structure_only",
        "google_scope": "spreadsheets.readonly",
        "sync_cadence_seconds": settings.cadence_seconds,
        "max_cache_age_seconds": settings.api_config.max_cache_age_seconds,
        "retention_generations": settings.sync_config.retain_generations,
        "website_max_products": settings.api_config.website_catalog_max_products,
        "base_deployment_check": deployment["status"],
    }


def make_website_builder(
    settings: RailwayRuntimeSettings,
    logger: logging.Logger,
    *,
    store: WebsiteCatalogStore | None = None,
) -> WebsiteCatalogBuilder:
    catalog_store = store or WebsiteCatalogStore(
        settings.api_config.website_catalog_path,
        settings.api_config.website_catalog_status_path,
        max_age_seconds=settings.api_config.website_catalog_max_age_seconds,
        source_max_age_seconds=settings.api_config.max_cache_age_seconds,
        max_products=settings.api_config.website_catalog_max_products,
        max_response_bytes=settings.api_config.website_catalog_max_response_bytes,
    )
    sheet = GoogleSheetsReadonlyAdapter(
        spreadsheet_id=TARGET_SPREADSHEET_ID,
        service_account_b64=settings.service_account_b64,
        timeout_seconds=settings.google_timeout_seconds,
        attempts=settings.google_attempts,
    )

    def reader_factory() -> CacheReader:
        reader = CacheReader(
            settings.sync_config.cache_path,
            settings.sync_config.status_path,
            max_cache_age_seconds=settings.api_config.max_cache_age_seconds,
        )
        if reader.status["stale"]:
            raise CacheUnavailable("SOURCE_CACHE_MARKED_STALE")
        return reader

    return WebsiteCatalogBuilder(
        reader_factory=reader_factory,
        sheet_adapter=sheet,
        store=catalog_store,
        logger=logger,
        max_products=settings.api_config.website_catalog_max_products,
    )


class RailwaySupervisor:
    def __init__(
        self,
        settings: RailwayRuntimeSettings,
        *,
        logger: logging.Logger,
        sync_factory: Callable[[], Any] | None = None,
        builder: WebsiteCatalogBuilder | None = None,
        server: Any | None = None,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.stop_event = threading.Event()
        self.jitter = jitter
        self.store = WebsiteCatalogStore(
            settings.api_config.website_catalog_path,
            settings.api_config.website_catalog_status_path,
            max_age_seconds=settings.api_config.website_catalog_max_age_seconds,
            source_max_age_seconds=settings.api_config.max_cache_age_seconds,
            max_products=settings.api_config.website_catalog_max_products,
            max_response_bytes=settings.api_config.website_catalog_max_response_bytes,
        )
        if builder is None:
            builder = make_website_builder(settings, logger, store=self.store)
        self.builder = builder
        self.sync_factory = sync_factory or (
            lambda: CatalogSynchronizer(settings.sync_config, logger=logger)
        )
        self.server = server or create_server(
            settings.api_config, logger, website_store=self.store
        )
        self.api_thread: threading.Thread | None = None
        self.worker_thread: threading.Thread | None = None

    def _sync_disabled(self) -> bool:
        return (not self.settings.sync_enabled) or self.settings.sync_disabled_path.exists()

    def _safe_build(self) -> bool:
        try:
            self.builder.build()
            return True
        except CatalogError as exc:
            self.logger.warning("worker_build_skipped code=%s", exc.code)
            return False
        except Exception:
            self.logger.warning("worker_build_skipped code=WEBSITE_CATALOG_BUILD_UNEXPECTED")
            return False

    def _worker_loop(self) -> None:
        # Activation guard: disabled startup serves an existing LKG only. It
        # performs neither a Kiot sync nor a Google-backed build/read.
        if not self._sync_disabled():
            self._safe_build()
        failures = 0
        while not self.stop_event.is_set():
            if self._sync_disabled():
                self.logger.info("sync_worker_disabled code=SYNC_DISABLED")
                self.stop_event.wait(min(60.0, float(self.settings.cadence_seconds)))
                continue
            try:
                summary = self.sync_factory().run()
                synced_at = summary.get("data_as_of")
                try:
                    self.store.record_status(last_error_code=None, last_kiot_sync_at=synced_at)
                except Exception:
                    self.logger.warning("website_catalog_warning code=WEBSITE_STATUS_WRITE_FAILED")
                self.builder.build()
                failures = 0
                delay = float(self.settings.cadence_seconds)
            except CatalogError as exc:
                if exc.code == "SYNC_LOCK_BUSY":
                    self.logger.info("sync_worker_skipped code=SYNC_LOCK_BUSY")
                    delay = min(60.0, self.settings.retry_base_seconds)
                else:
                    failures += 1
                    cap = min(
                        self.settings.retry_max_seconds,
                        self.settings.retry_base_seconds * (2 ** min(failures - 1, 6)),
                    )
                    delay = self.jitter(cap * 0.8, cap)
                    self.logger.warning("sync_worker_retry code=%s", exc.code)
            except Exception:
                failures += 1
                cap = min(
                    self.settings.retry_max_seconds,
                    self.settings.retry_base_seconds * (2 ** min(failures - 1, 6)),
                )
                delay = self.jitter(cap * 0.8, cap)
                self.logger.warning("sync_worker_retry code=UNEXPECTED_FAILURE")
            self.stop_event.wait(delay)
        self.logger.info("sync_worker_stopped")

    def request_stop(self, *_args: Any) -> None:
        self.stop_event.set()

    def run(self) -> int:
        previous_handlers: dict[int, Any] = {}
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self.request_stop)
        self.api_thread = threading.Thread(
            target=self.server.serve_forever, name="catalog-api", daemon=False
        )
        self.worker_thread = threading.Thread(
            target=self._worker_loop, name="catalog-sync-worker", daemon=False
        )
        self.api_thread.start()
        self.worker_thread.start()
        self.logger.info("railway_service_started")
        try:
            self.stop_event.wait()
            return 0
        finally:
            self.stop_event.set()
            self.server.shutdown()
            self.server.server_close()
            self.api_thread.join(timeout=10)
            self.worker_thread.join(timeout=10)
            for signum, handler in previous_handlers.items():
                signal.signal(signum, handler)
            self.logger.info("railway_service_stopped")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The Gate Railway catalog runtime")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--build-once", action="store_true")
    args = parser.parse_args(argv)
    try:
        prepare_railway_environment()
        settings = load_railway_runtime_settings()
        logger = build_logger(settings.sync_config.log_path, "kiot_catalog.railway")
        summary = validate_railway_preflight(settings)
        logger.info(
            "railway_preflight status=%s cadence=%s retention=%s",
            summary["status"],
            summary["sync_cadence_seconds"],
            summary["retention_generations"],
        )
        if args.preflight_only:
            print(json.dumps(summary, sort_keys=True))
            return 0
        if args.build_once:
            result = make_website_builder(settings, logger).build()
            print(json.dumps(result, sort_keys=True))
            return 0
        return RailwaySupervisor(settings, logger=logger).run()
    except CatalogError as exc:
        print(json.dumps({"status": "FAILED", "error_code": exc.code}, sort_keys=True))
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        code = "UNEXPECTED_" + type(exc).__name__.upper()
        print(json.dumps({"status": "FAILED", "error_code": code}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
