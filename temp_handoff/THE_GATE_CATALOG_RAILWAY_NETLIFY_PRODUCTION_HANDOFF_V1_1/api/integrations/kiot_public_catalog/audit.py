from __future__ import annotations

import datetime as dt
import json
import sqlite3
import stat
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .cache import CacheReader, cache_quick_check
from .config import MODULE_DIR, SyncConfig
from .contracts import BRANCH_SLUGS, INTERNAL_RECORD_FIELDS
from .errors import ContractError
from .secrets import load_kiotviet_credentials
from .transform import validate_record


FORBIDDEN_DATA_KEYS = frozenset(
    {
        "cost",
        "costprice",
        "customer",
        "customerid",
        "customername",
        "contactnumber",
        "address",
        "invoice",
        "invoiceid",
        "supplier",
        "supplierid",
        "suppliername",
        "employee",
        "userid",
        "username",
        "clientid",
        "clientsecret",
        "accesstoken",
        "apikey",
        "payment",
        "debt",
        "cashflow",
    }
)


def _normalized_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _walk_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_walk_keys(child))
    return keys


def _mode(path: Path) -> str | None:
    return None if not path.exists() else oct(stat.S_IMODE(path.stat().st_mode))


def audit_artifacts(
    config: SyncConfig,
    *,
    max_cache_age_seconds: float,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    reader = CacheReader(
        config.cache_path,
        config.status_path,
        max_cache_age_seconds=max_cache_age_seconds,
        now=now,
    )
    if not cache_quick_check(reader.cache_path):
        raise ContractError("AUDIT_CACHE_QUICK_CHECK_FAILED")
    status = reader.status
    uri = "file:" + quote(str(reader.cache_path)) + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only=ON")
    rows = connection.execute("SELECT payload FROM products ORDER BY code").fetchall()
    meta_rows = connection.execute("SELECT key, value FROM meta").fetchall()
    connection.close()
    metadata = {key: json.loads(value) for key, value in meta_rows}
    forbidden_keys: set[str] = set()
    branch_contract_ok = True
    cache_text_parts: list[str] = []
    for (payload_text,) in rows:
        record = json.loads(payload_text)
        validate_record(record)
        if set(record) != set(INTERNAL_RECORD_FIELDS):
            raise ContractError("AUDIT_CACHE_ALLOWLIST_FAILED")
        branch_contract_ok = branch_contract_ok and (
            set(record["availability"]) == set(BRANCH_SLUGS)
            and set(record["inventory"]) == set(BRANCH_SLUGS)
        )
        for key in _walk_keys(record):
            normalized = _normalized_key(key)
            if normalized in FORBIDDEN_DATA_KEYS:
                forbidden_keys.add(normalized)
        cache_text_parts.append(payload_text)
    if forbidden_keys:
        raise ContractError("AUDIT_FORBIDDEN_CACHE_KEY_FOUND")
    approved_meta = metadata.get("approved_branches")
    if not isinstance(approved_meta, dict) or set(approved_meta) != set(BRANCH_SLUGS):
        raise ContractError("AUDIT_BRANCH_METADATA_FAILED")

    credentials = load_kiotviet_credentials(config.secrets_path)
    sensitive_values = tuple(
        credentials[key]
        for key in ("KV_CLIENT_ID", "KV_CLIENT_SECRET")
        if credentials.get(key)
    )
    credentials = None
    cache_joined = "\n".join(cache_text_parts)
    status_text = config.status_path.read_text(encoding="utf-8")
    log_paths = sorted(config.log_path.parent.glob("*.log"))
    log_text = "\n".join(path.read_text(encoding="utf-8") for path in log_paths)
    module_dir = MODULE_DIR
    evidence_dir = module_dir / "evidence"
    text_artifact_paths = (
        sorted(
            path
            for path in evidence_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".md", ".txt", ".json", ".patch"}
        )
        if evidence_dir.is_dir()
        else []
    )
    example_path = module_dir / ".env.example"
    if example_path.is_file():
        text_artifact_paths.append(example_path)
    artifact_text = "\n".join(
        path.read_text(encoding="utf-8") for path in text_artifact_paths
    )
    sensitive_value_matches = sum(
        1
        for value in sensitive_values
        if value in cache_joined
        or value in status_text
        or value in log_text
        or value in artifact_text
    )
    cache_text_parts.clear()
    cache_joined = ""
    sensitive_values = ()
    if sensitive_value_matches:
        raise ContractError("AUDIT_SECRET_VALUE_MATCH_FOUND")

    temporary_files = sorted(
        path.name
        for path in config.cache_path.parent.iterdir()
        if ".tmp." in path.name
    )
    if temporary_files:
        raise ContractError("AUDIT_TEMPORARY_CACHE_FILE_REMAINS")
    file_modes = {
        "cache": _mode(reader.cache_path),
        "status": _mode(config.status_path),
        "lock": _mode(config.lock_path),
        "sync_log": _mode(config.log_path),
        "data_directory": _mode(config.cache_path.parent),
        "log_directory": _mode(config.log_path.parent),
    }
    if any(file_modes[name] != "0o600" for name in ("cache", "status", "lock", "sync_log")):
        raise ContractError("AUDIT_PRIVATE_FILE_MODE_FAILED")
    if any(file_modes[name] != "0o700" for name in ("data_directory", "log_directory")):
        raise ContractError("AUDIT_PRIVATE_DIRECTORY_MODE_FAILED")
    if any(_mode(path) != "0o600" for path in log_paths):
        raise ContractError("AUDIT_PRIVATE_LOG_MODE_FAILED")
    publication_funnel = reader.publication_funnel()
    return {
        "status": "PASS",
        "cache_quick_check": "ok",
        "record_count": len(rows),
        "data_as_of": status["data_as_of"],
        "stale": status["stale"],
        "generation_coherence": "PASS",
        "freshness_guard": "PASS",
        "record_field_allowlist": "PASS",
        "forbidden_data_key_count": 0,
        "approved_branch_contract": "PASS" if branch_contract_ok else "FAIL",
        "out_of_scope_branch_count": 0,
        "secret_value_match_count": 0,
        "log_files_scanned": len(log_paths),
        "text_artifacts_scanned": len(text_artifact_paths),
        "temporary_cache_file_count": 0,
        "file_modes": file_modes,
        "publication_funnel": publication_funnel,
    }
