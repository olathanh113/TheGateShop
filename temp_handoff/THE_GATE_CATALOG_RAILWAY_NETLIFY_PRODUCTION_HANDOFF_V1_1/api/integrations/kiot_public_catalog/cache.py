from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import sqlite3
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from .config import validate_retain_generations
from .errors import CacheUnavailable, CatalogError, ContractError
from .transform import validate_record


CACHE_SCHEMA_VERSION = "kiot_public_catalog_cache.v3"
STATUS_SCHEMA_VERSION = "kiot_public_catalog_sync_status.v2"
GENERATION_ID_RE = re.compile(r"[0-9a-f]{32}\Z")
APPROVED_BRANCH_SLUGS = frozenset(
    {"ton_that_thiep", "nguyen_trai", "tam_coc"}
)

PUBLIC_ELIGIBILITY_SQL = """
price_status = 'available'
AND sale_price IS NOT NULL
AND typeof(sale_price) IN ('integer', 'real')
AND sale_price > 0
AND active_status = 'active'
AND length(trim(code)) > 0
""".strip()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _validate_generation_id(value: Any) -> str:
    if not isinstance(value, str) or not GENERATION_ID_RE.fullmatch(value):
        raise ContractError("GENERATION_ID_INVALID")
    return value


def generation_cache_path(cache_path: Path, generation_id: str) -> Path:
    generation = _validate_generation_id(generation_id)
    return cache_path.with_name(f"{cache_path.stem}.{generation}{cache_path.suffix}")


def _atomic_json(
    path: Path,
    payload: dict[str, Any],
    *,
    before_replace: Callable[[], None] | None = None,
    after_replace: Callable[[], None] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temp, path)
        if after_replace is not None:
            after_replace()
        path.chmod(0o600)
        _fsync_directory(path.parent)
    finally:
        if temp.exists():
            temp.unlink()


def write_sync_status(
    path: Path,
    *,
    data_as_of: str | None,
    generation_id: str | None,
    cache_schema_version: str | None,
    record_count: int | None,
    stale: bool,
    has_successful_sync: bool,
    last_attempt_at: str,
    last_error_code: str | None,
    before_replace: Callable[[], None] | None = None,
    after_replace: Callable[[], None] | None = None,
) -> None:
    _atomic_json(
        path,
        {
            "schema_version": STATUS_SCHEMA_VERSION,
            "has_successful_sync": has_successful_sync,
            "stale": stale,
            "data_as_of": data_as_of,
            "generation_id": generation_id,
            "cache_schema_version": cache_schema_version,
            "record_count": record_count,
            "last_attempt_at": last_attempt_at,
            "last_error_code": last_error_code,
        },
        before_replace=before_replace,
        after_replace=after_replace,
    )


def read_sync_status(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CacheUnavailable("CACHE_STATUS_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CacheUnavailable("CACHE_STATUS_INVALID") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != STATUS_SCHEMA_VERSION
        or payload.get("has_successful_sync") is not True
        or not isinstance(payload.get("stale"), bool)
        or not isinstance(payload.get("data_as_of"), str)
        or payload.get("cache_schema_version") != CACHE_SCHEMA_VERSION
        or not isinstance(payload.get("record_count"), int)
        or isinstance(payload.get("record_count"), bool)
        or payload.get("record_count") < 0
    ):
        raise CacheUnavailable("CACHE_NEVER_SYNCED_SUCCESSFULLY")
    try:
        _validate_generation_id(payload.get("generation_id"))
    except ContractError as exc:
        raise CacheUnavailable("CACHE_STATUS_GENERATION_INVALID") from exc
    return payload


def write_cache_atomic(
    path: Path,
    records: Iterable[dict[str, Any]],
    *,
    metadata: dict[str, Any],
    before_replace: Callable[[], None] | None = None,
) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    inserted = 0
    connection: sqlite3.Connection | None = None
    generation_id = _validate_generation_id(metadata.get("generation_id"))
    data_as_of = metadata.get("data_as_of")
    if not isinstance(data_as_of, str) or not data_as_of:
        raise ContractError("CACHE_DATA_AS_OF_INVALID")
    if path.exists():
        raise ContractError("GENERATION_CACHE_ALREADY_EXISTS")
    try:
        connection = sqlite3.connect(temp)
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            """
            CREATE TABLE products (
                code TEXT PRIMARY KEY NOT NULL,
                payload TEXT NOT NULL,
                generation_id TEXT NOT NULL CHECK (generation_id = json_extract(payload, '$.generation_id')),
                data_as_of TEXT NOT NULL CHECK (data_as_of = json_extract(payload, '$.data_as_of')),
                sale_price REAL,
                price_status TEXT NOT NULL,
                active_status TEXT NOT NULL,
                has_image INTEGER NOT NULL CHECK (has_image IN (0, 1)),
                ton_that_thiep_in_stock INTEGER NOT NULL CHECK (ton_that_thiep_in_stock IN (0, 1)),
                nguyen_trai_in_stock INTEGER NOT NULL CHECK (nguyen_trai_in_stock IN (0, 1)),
                tam_coc_in_stock INTEGER NOT NULL CHECK (tam_coc_in_stock IN (0, 1)),
                all_three_out_of_stock INTEGER NOT NULL CHECK (all_three_out_of_stock IN (0, 1))
            )
            """
        )
        connection.execute(
            "CREATE INDEX products_public_eligibility ON products(active_status, price_status, sale_price, code)"
        )
        connection.execute(
            "CREATE TABLE meta (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)"
        )
        for record in records:
            validate_record(record)
            if record["generation_id"] != generation_id:
                raise ContractError("CACHE_RECORD_GENERATION_MISMATCH")
            if record["data_as_of"] != data_as_of:
                raise ContractError("CACHE_RECORD_CUTOFF_MISMATCH")
            payload = json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            try:
                availability = record["availability"]
                connection.execute(
                    """
                    INSERT INTO products(
                        code, payload, generation_id, data_as_of,
                        sale_price, price_status, active_status, has_image,
                        ton_that_thiep_in_stock, nguyen_trai_in_stock, tam_coc_in_stock,
                        all_three_out_of_stock
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["code"],
                        payload,
                        record["generation_id"],
                        record["data_as_of"],
                        record["sale_price"],
                        record["price_status"],
                        record["active_status"],
                        int(bool(record["images"])),
                        int(availability["ton_that_thiep"] == "in_stock"),
                        int(availability["nguyen_trai"] == "in_stock"),
                        int(availability["tam_coc"] == "in_stock"),
                        int(all(value == "out_of_stock" for value in availability.values())),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ContractError("DUPLICATE_PRODUCT_CODE") from exc
            inserted += 1
        complete_meta = {
            **metadata,
            "schema_version": CACHE_SCHEMA_VERSION,
            "record_count": inserted,
        }
        for key, value in complete_meta.items():
            connection.execute(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                (
                    str(key),
                    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                ),
            )
        connection.commit()
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        connection.close()
        connection = None
        if quick_check != ("ok",) or count != inserted:
            raise ContractError("CACHE_VALIDATION_FAILED")
        temp.chmod(0o600)
        with temp.open("rb") as handle:
            os.fsync(handle.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temp, path)
        path.chmod(0o600)
        _fsync_directory(path.parent)
        return inserted
    finally:
        if connection is not None:
            connection.close()
        if temp.exists():
            temp.unlink()


def commit_snapshot_atomic(
    cache_path: Path,
    status_path: Path,
    records: Iterable[dict[str, Any]],
    *,
    metadata: dict[str, Any],
    generation_id: str,
    data_as_of: str,
    last_attempt_at: str,
    fault_injector: Callable[[str], None] | None = None,
) -> tuple[int, Path]:
    generation = _validate_generation_id(generation_id)
    target = generation_cache_path(cache_path, generation)
    if target.exists():
        raise ContractError("GENERATION_CACHE_ALREADY_EXISTS")
    committed = False

    def inject(point: str) -> None:
        if fault_injector is not None:
            fault_injector(point)

    def mark_committed() -> None:
        nonlocal committed
        committed = True

    try:
        inserted = write_cache_atomic(
            target,
            records,
            metadata={**metadata, "generation_id": generation, "data_as_of": data_as_of},
            before_replace=lambda: inject("after_cache_temp_ready"),
        )
        inject("after_generation_database_ready")
        write_sync_status(
            status_path,
            data_as_of=data_as_of,
            generation_id=generation,
            cache_schema_version=CACHE_SCHEMA_VERSION,
            record_count=inserted,
            stale=False,
            has_successful_sync=True,
            last_attempt_at=last_attempt_at,
            last_error_code=None,
            before_replace=lambda: inject("before_status_commit"),
            after_replace=mark_committed,
        )
        inject("after_status_commit")
        return inserted, target
    finally:
        if not committed and target.exists():
            target.unlink()
            _fsync_directory(target.parent)


def cache_quick_check(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        uri = "file:" + quote(str(path)) + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only=ON")
        result = connection.execute("PRAGMA quick_check").fetchone()
        connection.close()
        return result == ("ok",)
    except sqlite3.Error:
        return False


@dataclass(frozen=True)
class GenerationCandidate:
    path: Path
    name: str
    generation_id: str
    data_as_of: str
    cutoff: dt.datetime
    record_count: int
    device: int
    inode: int


def _generation_filename_pattern(cache_path: Path) -> re.Pattern[str]:
    return re.compile(
        rf"{re.escape(cache_path.stem)}\.([0-9a-f]{{32}}){re.escape(cache_path.suffix)}\Z"
    )


def _validated_generation_candidate_path(
    cache_path: Path, candidate_name: str
) -> tuple[Path, str, os.stat_result]:
    if (
        not isinstance(candidate_name, str)
        or not candidate_name
        or Path(candidate_name).is_absolute()
        or "/" in candidate_name
        or "\\" in candidate_name
        or len(Path(candidate_name).parts) != 1
        or Path(candidate_name).name != candidate_name
    ):
        raise ContractError("RETENTION_CANDIDATE_PATH_REJECTED")
    match = _generation_filename_pattern(cache_path).fullmatch(candidate_name)
    if match is None:
        raise ContractError("RETENTION_CANDIDATE_NAME_REJECTED")
    generation_id = _validate_generation_id(match.group(1))
    try:
        cache_directory = cache_path.parent.resolve(strict=True)
    except OSError as exc:
        raise ContractError("RETENTION_CACHE_DIRECTORY_INVALID") from exc
    candidate = cache_directory / candidate_name
    try:
        candidate_stat = candidate.lstat()
    except OSError as exc:
        raise ContractError("RETENTION_CANDIDATE_UNAVAILABLE") from exc
    if stat.S_ISLNK(candidate_stat.st_mode):
        raise ContractError("RETENTION_CANDIDATE_SYMLINK_REJECTED")
    if not stat.S_ISREG(candidate_stat.st_mode):
        raise ContractError("RETENTION_CANDIDATE_NOT_REGULAR")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ContractError("RETENTION_CANDIDATE_UNAVAILABLE") from exc
    if resolved.parent != cache_directory or resolved != candidate:
        raise ContractError("RETENTION_CANDIDATE_PATH_REJECTED")
    return candidate, generation_id, candidate_stat


def _parse_generation_cutoff(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise ContractError("RETENTION_CANDIDATE_CUTOFF_INVALID")
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError("RETENTION_CANDIDATE_CUTOFF_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError("RETENTION_CANDIDATE_CUTOFF_INVALID")
    return parsed.astimezone(dt.timezone.utc)


def _inspect_generation_candidate(
    cache_path: Path, candidate_name: str
) -> GenerationCandidate:
    candidate, generation_id, candidate_stat = _validated_generation_candidate_path(
        cache_path, candidate_name
    )
    connection: sqlite3.Connection | None = None
    try:
        uri = "file:" + quote(str(candidate)) + "?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
            raise ContractError("RETENTION_CANDIDATE_QUICK_CHECK_FAILED")
        raw_metadata = connection.execute("SELECT key, value FROM meta").fetchall()
        try:
            metadata = {str(key): json.loads(value) for key, value in raw_metadata}
        except Exception as exc:
            raise ContractError("RETENTION_CANDIDATE_METADATA_INVALID") from exc
        record_count = metadata.get("record_count")
        approved_branches = metadata.get("approved_branches")
        if (
            metadata.get("schema_version") != CACHE_SCHEMA_VERSION
            or metadata.get("generation_id") != generation_id
            or not isinstance(record_count, int)
            or isinstance(record_count, bool)
            or record_count < 0
            or metadata.get("pricebook_name") != "SALE"
            or not isinstance(metadata.get("pricebook_id"), int)
            or isinstance(metadata.get("pricebook_id"), bool)
            or not isinstance(approved_branches, dict)
            or set(approved_branches) != APPROVED_BRANCH_SLUGS
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value <= 0
                for value in approved_branches.values()
            )
        ):
            raise ContractError("RETENTION_CANDIDATE_METADATA_INVALID")
        data_as_of = metadata.get("data_as_of")
        cutoff = _parse_generation_cutoff(data_as_of)
        actual_count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        invalid_json = connection.execute(
            "SELECT COUNT(*) FROM products WHERE json_valid(payload) != 1"
        ).fetchone()[0]
        if invalid_json:
            raise ContractError("RETENTION_CANDIDATE_COHERENCE_INVALID")
        mismatch_count = connection.execute(
            """
            SELECT COUNT(*) FROM products
            WHERE generation_id IS NOT ?
               OR data_as_of IS NOT ?
               OR json_extract(payload, '$.generation_id') IS NOT ?
               OR json_extract(payload, '$.data_as_of') IS NOT ?
            """,
            (generation_id, data_as_of, generation_id, data_as_of),
        ).fetchone()[0]
        if actual_count != record_count or mismatch_count:
            raise ContractError("RETENTION_CANDIDATE_COHERENCE_INVALID")
    except ContractError:
        raise
    except sqlite3.Error as exc:
        raise ContractError("RETENTION_CANDIDATE_DATABASE_INVALID") from exc
    finally:
        if connection is not None:
            connection.close()
    return GenerationCandidate(
        path=candidate,
        name=candidate_name,
        generation_id=generation_id,
        data_as_of=data_as_of,
        cutoff=cutoff,
        record_count=record_count,
        device=candidate_stat.st_dev,
        inode=candidate_stat.st_ino,
    )


def cleanup_generation_retention(
    cache_path: Path,
    status_path: Path,
    retain_generations: int,
    *,
    warning_handler: Callable[[str], None] | None = None,
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Delete only validated old generations. Caller must hold the sync lock."""
    retain = validate_retain_generations(retain_generations)
    status_payload = read_sync_status(status_path)
    authoritative_id = status_payload["generation_id"]
    authoritative_name = generation_cache_path(cache_path, authoritative_id).name
    try:
        authoritative = _inspect_generation_candidate(cache_path, authoritative_name)
    except CatalogError as exc:
        raise ContractError("RETENTION_AUTHORITATIVE_INVALID") from exc
    if (
        authoritative.data_as_of != status_payload["data_as_of"]
        or authoritative.record_count != status_payload["record_count"]
        or status_payload["cache_schema_version"] != CACHE_SCHEMA_VERSION
    ):
        raise ContractError("RETENTION_AUTHORITATIVE_INVALID")

    warnings: set[str] = set()

    def warn(code: str) -> None:
        warnings.add(code)
        if warning_handler is not None:
            warning_handler(code)

    cache_directory = cache_path.parent.resolve(strict=True)
    pattern = _generation_filename_pattern(cache_path)
    valid: list[GenerationCandidate] = []
    for entry in cache_directory.iterdir():
        if pattern.fullmatch(entry.name) is None:
            continue
        try:
            valid.append(_inspect_generation_candidate(cache_path, entry.name))
        except CatalogError:
            warn("RETENTION_CANDIDATE_SKIPPED")

    if not any(item.generation_id == authoritative_id for item in valid):
        raise ContractError("RETENTION_AUTHORITATIVE_INVALID")

    cutoff_counts: dict[dt.datetime, int] = {}
    for item in valid:
        cutoff_counts[item.cutoff] = cutoff_counts.get(item.cutoff, 0) + 1

    safe_predecessors: list[GenerationCandidate] = []
    protected_ids = {authoritative_id}
    for item in valid:
        if item.generation_id == authoritative_id:
            continue
        if item.cutoff >= authoritative.cutoff or cutoff_counts[item.cutoff] != 1:
            protected_ids.add(item.generation_id)
            warn("RETENTION_CANDIDATE_ORDER_AMBIGUOUS")
            continue
        safe_predecessors.append(item)
    safe_predecessors.sort(key=lambda item: item.cutoff, reverse=True)
    protected_ids.update(
        item.generation_id for item in safe_predecessors[: retain - 1]
    )

    deleted = 0
    for item in reversed(safe_predecessors[retain - 1 :]):
        if item.generation_id in protected_ids or item.generation_id == authoritative_id:
            continue
        current = _inspect_generation_candidate(cache_path, item.name)
        current_stat = current.path.lstat()
        if (
            current.generation_id != item.generation_id
            or current.data_as_of != item.data_as_of
            or current.record_count != item.record_count
            or current_stat.st_dev != item.device
            or current_stat.st_ino != item.inode
        ):
            warn("RETENTION_CANDIDATE_CHANGED")
            continue
        if fault_injector is not None:
            fault_injector("before_unlink")
        current.path.unlink()
        _fsync_directory(cache_directory)
        deleted += 1
        if fault_injector is not None:
            fault_injector("after_unlink")

    return {
        "status": "PASS_WITH_WARNINGS" if warnings else "PASS",
        "retain_generations": retain,
        "valid_before": len(valid),
        "deleted": deleted,
        "valid_after": len(valid) - deleted,
        "skipped_warning_count": len(warnings),
        "warning_codes": sorted(warnings),
    }


class CacheReader:
    def __init__(
        self,
        cache_path: Path,
        status_path: Path,
        *,
        max_cache_age_seconds: float,
        now: dt.datetime | None = None,
    ) -> None:
        if (
            not isinstance(max_cache_age_seconds, (int, float))
            or isinstance(max_cache_age_seconds, bool)
            or not math.isfinite(float(max_cache_age_seconds))
            or max_cache_age_seconds <= 0
        ):
            raise CacheUnavailable("CACHE_MAX_AGE_INVALID")
        self.base_cache_path = cache_path
        self.status = read_sync_status(status_path)
        self._validate_freshness(float(max_cache_age_seconds), now=now)
        self.cache_path = generation_cache_path(
            cache_path, self.status["generation_id"]
        )
        if not cache_quick_check(self.cache_path):
            raise CacheUnavailable("CACHE_DATABASE_UNAVAILABLE")
        self._metadata = self.metadata()
        self._validate_generation_coherence()

    def _validate_freshness(
        self, max_cache_age_seconds: float, *, now: dt.datetime | None
    ) -> None:
        raw = self.status["data_as_of"]
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        try:
            cutoff = dt.datetime.fromisoformat(raw)
        except ValueError as exc:
            raise CacheUnavailable("CACHE_CUTOFF_INVALID") from exc
        if cutoff.tzinfo is None:
            raise CacheUnavailable("CACHE_CUTOFF_TIMEZONE_MISSING")
        current = now or dt.datetime.now(dt.timezone.utc)
        if current.tzinfo is None:
            raise CacheUnavailable("CACHE_NOW_TIMEZONE_MISSING")
        age = (current.astimezone(dt.timezone.utc) - cutoff.astimezone(dt.timezone.utc)).total_seconds()
        if age < 0:
            raise CacheUnavailable("CACHE_CUTOFF_IN_FUTURE")
        if age > max_cache_age_seconds:
            raise CacheUnavailable("CACHE_TOO_OLD")

    def _connect(self) -> sqlite3.Connection:
        uri = "file:" + quote(str(self.cache_path)) + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.execute("PRAGMA query_only=ON")
        return connection

    def metadata(self) -> dict[str, Any]:
        connection = self._connect()
        try:
            rows = connection.execute("SELECT key, value FROM meta").fetchall()
        finally:
            connection.close()
        try:
            metadata = {key: json.loads(value) for key, value in rows}
        except Exception as exc:
            raise CacheUnavailable("CACHE_METADATA_INVALID") from exc
        if metadata.get("schema_version") != CACHE_SCHEMA_VERSION:
            raise CacheUnavailable("CACHE_SCHEMA_VERSION_MISMATCH")
        return metadata

    def _validate_generation_coherence(self) -> None:
        metadata = self._metadata
        expected = {
            "generation_id": self.status["generation_id"],
            "data_as_of": self.status["data_as_of"],
            "schema_version": self.status["cache_schema_version"],
            "record_count": self.status["record_count"],
        }
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise CacheUnavailable("CACHE_GENERATION_FENCE_MISMATCH")
        connection = self._connect()
        try:
            actual_count = int(
                connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            )
            mismatch = connection.execute(
                """
                SELECT 1 FROM products
                WHERE generation_id IS NOT ?
                   OR data_as_of IS NOT ?
                   OR json_extract(payload, '$.generation_id') IS NOT ?
                   OR json_extract(payload, '$.data_as_of') IS NOT ?
                LIMIT 1
                """,
                (
                    expected["generation_id"],
                    expected["data_as_of"],
                    expected["generation_id"],
                    expected["data_as_of"],
                ),
            ).fetchone()
        except sqlite3.Error as exc:
            raise CacheUnavailable("CACHE_COHERENCE_QUERY_FAILED") from exc
        finally:
            connection.close()
        if actual_count != expected["record_count"]:
            raise CacheUnavailable("CACHE_RECORD_COUNT_MISMATCH")
        if mismatch is not None:
            raise CacheUnavailable("CACHE_RECORD_GENERATION_MISMATCH")

    def list_records(
        self, *, offset: int, limit: int, public_only: bool = False
    ) -> tuple[list[dict[str, Any]], int]:
        connection = self._connect()
        try:
            where = f" WHERE {PUBLIC_ELIGIBILITY_SQL}" if public_only else ""
            total = connection.execute(f"SELECT COUNT(*) FROM products{where}").fetchone()[0]
            rows = connection.execute(
                f"SELECT payload FROM products{where} ORDER BY code LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        finally:
            connection.close()
        return [self._decode(row[0]) for row in rows], int(total)

    def get_record(self, code: str, *, public_only: bool = False) -> dict[str, Any] | None:
        connection = self._connect()
        try:
            public_clause = f" AND {PUBLIC_ELIGIBILITY_SQL}" if public_only else ""
            row = connection.execute(
                f"SELECT payload FROM products WHERE code = ?{public_clause}", (code,)
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else self._decode(row[0])

    def publication_funnel(self) -> dict[str, int]:
        connection = self._connect()
        try:
            count = lambda where="1=1": int(
                connection.execute(f"SELECT COUNT(*) FROM products WHERE {where}").fetchone()[0]
            )
            duplicate_codes = int(
                connection.execute(
                    "SELECT COUNT(*) FROM (SELECT code FROM products GROUP BY code HAVING COUNT(*) > 1)"
                ).fetchone()[0]
            )
            eligible = f"({PUBLIC_ELIGIBILITY_SQL})"
            result = {
                "total_internal_records": count(),
                "sale_price_present": count("price_status <> 'unavailable'"),
                "sale_price_missing": count("price_status = 'unavailable'"),
                "sale_price_zero": count("price_status = 'zero'"),
                "sale_price_invalid": count("price_status = 'invalid'"),
                "inactive_records": count("active_status = 'inactive'"),
                "active_status_unknown": count("active_status = 'unknown'"),
                "empty_product_code": count("length(trim(code)) = 0"),
                "duplicate_product_codes": duplicate_codes,
                "public_eligible_records": count(eligible),
                "public_eligible_missing_images": count(f"{eligible} AND has_image = 0"),
                "public_eligible_in_stock_ton_that_thiep": count(
                    f"{eligible} AND ton_that_thiep_in_stock = 1"
                ),
                "public_eligible_in_stock_nguyen_trai": count(
                    f"{eligible} AND nguyen_trai_in_stock = 1"
                ),
                "public_eligible_in_stock_tam_coc": count(
                    f"{eligible} AND tam_coc_in_stock = 1"
                ),
                "public_eligible_out_of_stock_all_three": count(
                    f"{eligible} AND all_three_out_of_stock = 1"
                ),
            }
        finally:
            connection.close()
        if result["sale_price_present"] + result["sale_price_missing"] != result["total_internal_records"]:
            raise CacheUnavailable("CACHE_PUBLICATION_FUNNEL_RECONCILIATION_FAILED")
        return result

    def _decode(self, payload: str) -> dict[str, Any]:
        try:
            record = json.loads(payload)
            validate_record(record)
        except Exception as exc:
            raise CacheUnavailable("CACHE_RECORD_INVALID") from exc
        if record["generation_id"] != self.status["generation_id"]:
            raise CacheUnavailable("CACHE_RECORD_GENERATION_MISMATCH")
        if record["data_as_of"] != self.status["data_as_of"]:
            raise CacheUnavailable("CACHE_RECORD_CUTOFF_MISMATCH")
        record["stale"] = bool(self.status["stale"])
        return record
