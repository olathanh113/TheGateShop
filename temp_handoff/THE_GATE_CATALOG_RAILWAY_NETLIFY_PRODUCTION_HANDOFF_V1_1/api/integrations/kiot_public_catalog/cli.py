from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Any

from .api import serve
from .audit import audit_artifacts
from .client import KiotVietClient
from .config import (
    SyncConfig,
    ensure_private_directory,
    load_api_config,
    load_max_cache_age_seconds,
    load_sync_config,
)
from .errors import CatalogError, ContractError
from .resolver import resolve_live_contract
from .sync import CatalogSynchronizer


def build_logger(path: Path, name: str) -> logging.Logger:
    ensure_private_directory(path.parent)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    if path.exists():
        path.chmod(0o600)
    return logger


def make_client(config: SyncConfig, logger: logging.Logger) -> KiotVietClient:
    return KiotVietClient(
        secrets_path=config.secrets_path,
        logger=logger,
        timeout_seconds=config.request_timeout_seconds,
        attempts=config.request_attempts,
        min_interval_seconds=config.request_min_interval_seconds,
    )


def run_preflight(config: SyncConfig, logger: logging.Logger) -> dict[str, Any]:
    client = make_client(config, logger)
    try:
        contract = resolve_live_contract(client)
        detail = client.get(
            f"/pricebooks/{contract.pricebook_id}",
            {"pageSize": 100, "currentItem": 0},
        )
        price_rows = detail.get("data") or []
        if not price_rows or any(
            not isinstance(row, dict)
            or not row.get("productCode")
            or "price" not in row
            for row in price_rows
        ):
            raise ContractError("SALE_PRICE_SCHEMA_INVALID")
        branch_ids = [branch.branch_id for branch in contract.branches]
        params: list[tuple[str, Any]] = [
            ("includeInventory", "true"),
            ("includePricebook", "false"),
            ("includeSoftDeletedAttribute", "false"),
            ("pageSize", 100),
            ("currentItem", 0),
            ("orderBy", "id"),
            ("orderDirection", "Asc"),
        ]
        params.extend(("BranchIds", branch_id) for branch_id in branch_ids)
        products_payload = client.get("/products", params)
        products = products_payload.get("data") or []
        if not products:
            raise ContractError("PRODUCT_SAMPLE_EMPTY")
        top_keys = sorted({str(key) for row in products for key in row.keys()})
        attribute_keys = sorted(
            {
                str(key)
                for row in products
                for item in (row.get("attributes") or [])
                if isinstance(item, dict)
                for key in item.keys()
            }
        )
        inventory_keys = sorted(
            {
                str(key)
                for row in products
                for item in (row.get("inventories") or [])
                if isinstance(item, dict)
                for key in item.keys()
            }
        )
        returned_branch_ids = {
            item.get("branchId")
            for row in products
            for item in (row.get("inventories") or [])
            if isinstance(item, dict)
        }
        if returned_branch_ids - set(branch_ids):
            raise ContractError("PRODUCT_BRANCH_FILTER_NOT_ENFORCED")
        required = {"code", "name", "attributes", "images", "inventories", "modifiedDate"}
        if not required.issubset(top_keys):
            raise ContractError("PRODUCT_SCHEMA_REQUIRED_FIELDS_MISSING")
        if not {"attributeName", "attributeValue"}.issubset(attribute_keys):
            raise ContractError("ATTRIBUTE_SCHEMA_REQUIRED_FIELDS_MISSING")
        if not {"branchId", "onHand"}.issubset(inventory_keys):
            raise ContractError("INVENTORY_SCHEMA_REQUIRED_FIELDS_MISSING")
        return {
            "status": "PASS",
            "contract": contract.safe_summary(),
            "source_schema": {
                "sale_price_total": detail.get("total"),
                "sale_price_fields_verified": {
                    "productCode": all("productCode" in row for row in price_rows),
                    "price": all("price" in row for row in price_rows),
                },
                "product_total": products_payload.get("total"),
                "product_fields_verified": {
                    field: field in top_keys
                    for field in (
                        "code",
                        "name",
                        "fullName",
                        "attributes",
                        "images",
                        "inventories",
                        "modifiedDate",
                        "isActive",
                    )
                },
                "attribute_fields_verified": {
                    field: field in attribute_keys
                    for field in ("attributeName", "attributeValue")
                },
                "inventory_fields_verified": {
                    field: field in inventory_keys for field in ("branchId", "onHand")
                },
                "out_of_scope_inventory_branch_count": 0,
            },
            "authentication": {
                "token_endpoint": "https://id.kiotviet.vn/connect/token",
                "method": "POST",
                "purpose": "OAuth token issuance only",
                "redirect_observed": False,
                "token_persisted_to_disk": False,
            },
            "business_api_methods": sorted(
                {
                    row["method"]
                    for row in client.call_ledger
                    if row.get("path") != "/connect/token"
                }
            ),
            "kiotviet_write_observed": False,
        }
    finally:
        client.clear_token()


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The Gate filtered KiotViet catalog")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("preflight", help="Run guarded read-only live preflight")
    subparsers.add_parser("sync", help="Run one manual full atomic sync")
    subparsers.add_parser("audit", help="Audit the clean cache, logs, scope and permissions")
    subparsers.add_parser(
        "publication-funnel", help="Report aggregate public eligibility counts from clean cache"
    )
    subparsers.add_parser("serve", help="Serve the localhost read-only API")
    subparsers.add_parser(
        "service-status", help="Read sanitized local runtime status without network access"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            api_config = load_api_config()
            logger = build_logger(api_config.log_path, "kiot_catalog.api")
            serve(api_config, logger)
            return 0
        if args.command == "service-status":
            api_config = load_api_config()
            status: dict[str, Any] = {
                "status": "UNINITIALIZED",
                "last_kiot_sync_at": None,
                "last_sheet_read_at": None,
                "last_website_build_at": None,
                "source_data_as_of": None,
                "item_count": None,
                "last_error_code": None,
            }
            if api_config.website_catalog_status_path.is_file():
                try:
                    payload = json.loads(
                        api_config.website_catalog_status_path.read_text(encoding="utf-8")
                    )
                except Exception as exc:
                    raise ContractError("WEBSITE_STATUS_INVALID") from exc
                allowed = set(status) - {"status"}
                if not isinstance(payload, dict) or not allowed.issubset(payload):
                    raise ContractError("WEBSITE_STATUS_INVALID")
                status.update({field: payload.get(field) for field in allowed})
                status["status"] = "AVAILABLE"
            _print_json(status)
            return 0
        sync_config = load_sync_config()
        logger = build_logger(sync_config.log_path, "kiot_catalog.sync")
        if args.command == "preflight":
            _print_json(run_preflight(sync_config, logger))
            return 0
        if args.command == "audit":
            _print_json(
                audit_artifacts(
                    sync_config,
                    max_cache_age_seconds=load_max_cache_age_seconds(),
                )
            )
            return 0
        if args.command == "publication-funnel":
            from .cache import CacheReader

            reader = CacheReader(
                sync_config.cache_path,
                sync_config.status_path,
                max_cache_age_seconds=load_max_cache_age_seconds(),
            )
            _print_json(
                {
                    "status": "PASS",
                    "data_as_of": reader.status["data_as_of"],
                    "stale": reader.status["stale"],
                    "publication_funnel": reader.publication_funnel(),
                }
            )
            return 0
        summary = CatalogSynchronizer(sync_config, logger=logger).run()
        _print_json(summary)
        return 0
    except CatalogError as exc:
        _print_json({"status": "FAILED", "error_code": exc.code})
        return 2
    except KeyboardInterrupt:
        _print_json({"status": "STOPPED"})
        return 130
    except Exception as exc:
        _print_json(
            {"status": "FAILED", "error_code": "UNEXPECTED_" + type(exc).__name__.upper()}
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
