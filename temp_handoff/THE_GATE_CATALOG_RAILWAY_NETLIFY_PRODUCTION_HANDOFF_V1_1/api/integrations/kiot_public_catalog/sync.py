from __future__ import annotations

import datetime as dt
import fcntl
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from .cache import (
    cache_quick_check,
    cleanup_generation_retention,
    commit_snapshot_atomic,
    generation_cache_path,
    read_sync_status,
    write_sync_status,
)
from .client import KiotVietClient
from .config import SyncConfig, ensure_private_directory, validate_retain_generations
from .contracts import BRANCH_SLUGS
from .errors import CatalogError, ContractError
from .resolver import ResolvedContract, TZ, resolve_live_contract
from .transform import build_record


PENDING_DATA_AS_OF = "PENDING_ATOMIC_CUTOFF"
PENDING_GENERATION_ID = "0" * 32


def iso_now() -> str:
    return dt.datetime.now(TZ).isoformat(timespec="seconds")


class SyncLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any = None

    def __enter__(self) -> "SyncLock":
        ensure_private_directory(self.path.parent)
        descriptor = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        os.chmod(self.path, 0o600)
        self._handle = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._handle.close()
            self._handle = None
            raise ContractError("SYNC_LOCK_BUSY") from exc
        return self

    def __exit__(self, *_args: Any) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None


class CatalogSynchronizer:
    def __init__(
        self,
        config: SyncConfig,
        *,
        logger: logging.Logger,
        client: Any | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.client = client

    def _client(self) -> Any:
        if self.client is None:
            self.client = KiotVietClient(
                secrets_path=self.config.secrets_path,
                logger=self.logger,
                timeout_seconds=self.config.request_timeout_seconds,
                attempts=self.config.request_attempts,
                min_interval_seconds=self.config.request_min_interval_seconds,
            )
        return self.client

    def _fetch_sale_prices(
        self, client: Any, contract: ResolvedContract
    ) -> tuple[dict[str, Any], int]:
        prices: dict[str, Any] = {}
        rows_read = 0
        path = f"/pricebooks/{contract.pricebook_id}"
        for batch, _total, _page in client.paginate(
            path, {}, page_size=self.config.page_size
        ):
            for row in batch:
                code = str(row.get("productCode") or "").strip()
                if not code or "price" not in row:
                    raise ContractError("SALE_PRICE_ROW_SCHEMA_INVALID")
                if code in prices:
                    raise ContractError("SALE_PRICE_DUPLICATE_CODE")
                prices[code] = row.get("price")
                rows_read += 1
        return prices, rows_read

    def _fetch_products(
        self,
        client: Any,
        contract: ResolvedContract,
        sale_prices: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], int]:
        branch_ids = [branch.branch_id for branch in contract.branches]
        params: list[tuple[str, Any]] = [
            ("includeInventory", "true"),
            ("includePricebook", "false"),
            ("includeSoftDeletedAttribute", "false"),
            ("orderBy", "id"),
            ("orderDirection", "Asc"),
        ]
        params.extend(("BranchIds", branch_id) for branch_id in branch_ids)
        records: list[dict[str, Any]] = []
        source_total: int | None = None
        seen_codes: set[str] = set()
        for batch, total, _page in client.paginate(
            "/products", params, page_size=self.config.page_size
        ):
            if source_total is None:
                source_total = total
            for product in batch:
                record = build_record(
                    product,
                    sale_prices=sale_prices,
                    generation_id=PENDING_GENERATION_ID,
                    data_as_of=PENDING_DATA_AS_OF,
                )
                if record["code"] in seen_codes:
                    raise ContractError("DUPLICATE_PRODUCT_CODE")
                seen_codes.add(record["code"])
                records.append(record)
        if source_total is None or len(records) != source_total:
            raise ContractError("PRODUCT_SOURCE_TOTAL_MISMATCH")
        return records, source_total

    def _mark_failure(self, attempt_at: str, error_code: str) -> None:
        previous_data_as_of: str | None = None
        has_success = False
        try:
            previous = read_sync_status(self.config.status_path)
            previous_cache = generation_cache_path(
                self.config.cache_path, previous["generation_id"]
            )
            if cache_quick_check(previous_cache):
                previous_data_as_of = previous["data_as_of"]
                has_success = True
        except CatalogError:
            previous = None
            has_success = False
        write_sync_status(
            self.config.status_path,
            data_as_of=previous_data_as_of,
            generation_id=previous["generation_id"] if has_success else None,
            cache_schema_version=(
                previous["cache_schema_version"] if has_success else None
            ),
            record_count=previous["record_count"] if has_success else None,
            stale=has_success,
            has_successful_sync=has_success,
            last_attempt_at=attempt_at,
            last_error_code=error_code,
        )

    def _clear_token(self) -> None:
        if self.client is not None and hasattr(self.client, "clear_token"):
            self.client.clear_token()

    def _apply_retention_locked(self) -> dict[str, Any]:
        try:
            return cleanup_generation_retention(
                self.config.cache_path,
                self.config.status_path,
                self.config.retain_generations,
                warning_handler=lambda code: self.logger.warning(
                    "retention_warning code=%s", code
                ),
            )
        except Exception:
            self.logger.warning("retention_warning code=RETENTION_CLEANUP_FAILED")
            return {
                "status": "WARNING",
                "retain_generations": self.config.retain_generations,
                "warning_code": "RETENTION_CLEANUP_FAILED",
            }

    def _run_locked(self, attempt_at: str) -> dict[str, Any]:
        """Build and commit one snapshot. The caller must hold ``SyncLock``."""
        client = self._client()
        contract = resolve_live_contract(client)
        sale_prices, sale_rows = self._fetch_sale_prices(client, contract)
        records, products_read = self._fetch_products(client, contract, sale_prices)
        data_as_of = iso_now()
        generation_id = uuid.uuid4().hex
        for record in records:
            record["data_as_of"] = data_as_of
            record["generation_id"] = generation_id
        missing_images = sum(1 for record in records if not record["images"])
        missing_sale_price = sum(
            1 for record in records if record["price_status"] == "unavailable"
        )
        zero_sale_price = sum(
            1 for record in records if record["price_status"] == "zero"
        )
        invalid_sale_price = sum(
            1 for record in records if record["price_status"] == "invalid"
        )
        inactive_records = sum(
            1 for record in records if record["active_status"] == "inactive"
        )
        active_status_unknown = sum(
            1 for record in records if record["active_status"] == "unknown"
        )
        in_stock = {
            slug: sum(
                1
                for record in records
                if record["availability"][slug] == "in_stock"
            )
            for slug in BRANCH_SLUGS
        }
        inserted, _generation_path = commit_snapshot_atomic(
            self.config.cache_path,
            self.config.status_path,
            records,
            metadata={
                "pricebook_name": contract.pricebook_name,
                "pricebook_id": contract.pricebook_id,
                "approved_branches": {
                    branch.slug: branch.branch_id for branch in contract.branches
                },
            },
            generation_id=generation_id,
            data_as_of=data_as_of,
            last_attempt_at=attempt_at,
        )
        if inserted != products_read:
            raise ContractError("CACHE_INSERT_COUNT_MISMATCH")
        retention = self._apply_retention_locked()
        ledger = list(getattr(client, "call_ledger", []))
        business_methods = sorted(
            {
                item["method"]
                for item in ledger
                if item.get("path") != "/connect/token"
            }
        )
        summary = {
            "status": "PASS",
            "data_as_of": data_as_of,
            "products_variants_read": products_read,
            "valid_records": inserted,
            "missing_images": missing_images,
            "missing_sale_price": missing_sale_price,
            "zero_sale_price": zero_sale_price,
            "invalid_sale_price": invalid_sale_price,
            "inactive_records": inactive_records,
            "active_status_unknown": active_status_unknown,
            "product_active_status": (
                "UNKNOWN" if active_status_unknown else "VERIFIED_FROM_IS_ACTIVE"
            ),
            "in_stock_by_branch": in_stock,
            "sale_price_rows_read": sale_rows,
            "contract": contract.safe_summary(),
            "authentication": {
                "token_endpoint": "https://id.kiotviet.vn/connect/token",
                "method": "POST",
                "purpose": "OAuth token issuance only",
                "token_persisted_to_disk": False,
                "redirect_observed": False,
            },
            "business_api_methods": business_methods,
            "kiotviet_write_observed": False,
            "kiotviet_call_count": len(ledger),
            "retention": retention,
        }
        self.logger.info(
            "sync_pass records=%s missing_images=%s missing_sale_price=%s",
            inserted,
            missing_images,
            missing_sale_price,
        )
        self._clear_token()
        return summary

    def run(self) -> dict[str, Any]:
        attempt_at = iso_now()
        validate_retain_generations(self.config.retain_generations)
        ensure_private_directory(self.config.cache_path.parent)
        ensure_private_directory(self.config.log_path.parent)
        lock_acquired = False
        try:
            with SyncLock(self.config.lock_path):
                lock_acquired = True
                try:
                    return self._run_locked(attempt_at)
                except CatalogError as exc:
                    # Failure status is part of the same serialized critical section.
                    self._mark_failure(attempt_at, exc.code)
                    self.logger.error("sync_failed code=%s", exc.code)
                    self._clear_token()
                    raise
                except Exception as exc:
                    error_code = "UNEXPECTED_" + type(exc).__name__.upper()
                    # Do not release the lock until the authoritative status is marked.
                    self._mark_failure(attempt_at, error_code)
                    self.logger.error("sync_failed code=%s", error_code)
                    self._clear_token()
                    raise ContractError(error_code) from exc
        except CatalogError as exc:
            if not lock_acquired and exc.code == "SYNC_LOCK_BUSY":
                self.logger.info("sync_skipped code=SYNC_LOCK_BUSY")
                self._clear_token()
            raise
        except Exception as exc:
            error_code = "UNEXPECTED_" + type(exc).__name__.upper()
            self.logger.error("sync_failed code=%s", error_code)
            self._clear_token()
            raise ContractError(error_code) from exc
