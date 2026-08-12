from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import logging
import math
import os
import re
import stat
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import requests

from .contracts import BRANCH_SLUGS
from .errors import CacheUnavailable, ConfigurationError, ContractError, TransportError


WEBSITE_SCHEMA_VERSION = "the_gate_website_catalog.v1"
GOOGLE_SHEETS_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/spreadsheets.readonly"
)
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
TARGET_SPREADSHEET_ID = "1kWGZy7Stnrs842lnt36Y_3ROO-t_pfNvRcz-cVwU1Eg"
TARGET_TAB = "WEBSITE_PRODUCTS"
TARGET_RANGE = "WEBSITE_PRODUCTS!A1:U1002"
SHEET_HEADERS = (
    "priority",
    "product_code",
    "product_id",
    "kiot_name",
    "custom_name",
    "final_name",
    "source_group",
    "category",
    "audience",
    "collection",
    "display_order",
    "featured",
    "publish",
    "kiot_price",
    "primary_image_url",
    "custom_image_url",
    "final_image_url",
    "image_preview",
    "sync_status",
    "note",
    "slug",
)
ITEM_FIELDS = frozenset(
    {
        "code",
        "name",
        "slug",
        "attributes",
        "images",
        "sale_price",
        "price_status",
        "availability",
        "source_group",
        "category",
        "audience",
        "collection",
        "display_order",
        "featured",
        "data_as_of",
    }
)
_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    if value.tzinfo is None:
        raise ContractError("WEBSITE_NOW_TIMEZONE_MISSING")
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def _parse_timestamp(value: Any, code: str) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise CacheUnavailable(code)
    raw = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise CacheUnavailable(code) from exc
    if parsed.tzinfo is None:
        raise CacheUnavailable(code)
    return parsed.astimezone(dt.timezone.utc)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json(
    path: Path,
    payload: Mapping[str, Any],
    *,
    fault_injector: Callable[[str], None] | None = None,
) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    body = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        if fault_injector:
            fault_injector("before_replace")
        os.replace(temp, path)
        path.chmod(0o600)
        _fsync_directory(path.parent)
        if fault_injector:
            fault_injector("after_replace")
        return body
    finally:
        if temp.exists() and not temp.is_symlink():
            temp.unlink()


def is_safe_website_image(value: Any) -> bool:
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    parsed = urlparse(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and parsed.fragment == ""
    )


def _strict_sheet_bool(value: Any, field: str) -> bool:
    if value is True or value == "TRUE":
        return True
    if value is False or value in ("FALSE", "", None):
        return False
    raise ContractError(f"SHEET_{field.upper()}_VALUE_INVALID")


def _optional_text(value: Any, field: str, *, maximum: int = 500) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or value != value.strip() or len(value) > maximum:
        raise ContractError(f"SHEET_{field.upper()}_INVALID")
    return value


def _optional_integer(value: Any, field: str) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ContractError(f"SHEET_{field.upper()}_INVALID")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"SHEET_{field.upper()}_INVALID") from exc
    if str(parsed) != str(value).strip() or parsed < 0 or parsed > 1_000_000:
        raise ContractError(f"SHEET_{field.upper()}_INVALID")
    return parsed


@dataclass(frozen=True)
class WebsiteSheetRow:
    product_code: str
    priority: int | None
    custom_name: str | None
    final_name: str | None
    source_group: str | None
    category: str | None
    audience: str | None
    collection: str | None
    display_order: int | None
    featured: bool
    publish: bool
    custom_image_url: str | None
    slug: str | None


def parse_sheet_values(values: Any) -> list[WebsiteSheetRow]:
    if not isinstance(values, list) or not values:
        raise ContractError("SHEET_VALUES_EMPTY")
    headers = values[0]
    if not isinstance(headers, list) or tuple(headers) != SHEET_HEADERS:
        raise ContractError("SHEET_HEADER_CONTRACT_MISMATCH")
    output: list[WebsiteSheetRow] = []
    seen: set[str] = set()
    for raw in values[1:]:
        if not isinstance(raw, list):
            raise ContractError("SHEET_ROW_NOT_ARRAY")
        padded = raw[: len(SHEET_HEADERS)] + [""] * max(0, len(SHEET_HEADERS) - len(raw))
        if len(raw) > len(SHEET_HEADERS) and any(value not in (None, "") for value in raw[len(SHEET_HEADERS) :]):
            raise ContractError("SHEET_ROW_HAS_EXTRA_COLUMNS")
        if all(value in (None, "") for value in padded):
            continue
        row = dict(zip(SHEET_HEADERS, padded, strict=True))
        raw_code = row["product_code"]
        if not isinstance(raw_code, str) or not raw_code.strip():
            raise ContractError("SHEET_PRODUCT_CODE_BLANK")
        code = raw_code.strip()
        if code in seen:
            raise ContractError("SHEET_DUPLICATE_PRODUCT_CODE")
        seen.add(code)
        output.append(
            WebsiteSheetRow(
                product_code=code,
                priority=_optional_integer(row["priority"], "priority"),
                custom_name=_optional_text(row["custom_name"], "custom_name"),
                final_name=_optional_text(row["final_name"], "final_name"),
                source_group=_optional_text(row["source_group"], "source_group"),
                category=_optional_text(row["category"], "category"),
                audience=_optional_text(row["audience"], "audience"),
                collection=_optional_text(row["collection"], "collection"),
                display_order=_optional_integer(row["display_order"], "display_order"),
                featured=_strict_sheet_bool(row["featured"], "featured"),
                publish=_strict_sheet_bool(row["publish"], "publish"),
                custom_image_url=_optional_text(
                    row["custom_image_url"], "custom_image_url", maximum=2048
                ),
                slug=_optional_text(row["slug"], "slug", maximum=120),
            )
        )
    return output


def decode_service_account_b64(encoded: str) -> dict[str, Any]:
    if not isinstance(encoded, str) or not encoded or "REPLACE" in encoded.upper():
        raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_SECRET_MISSING")
    try:
        raw = base64.b64decode(encoded, validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_SECRET_INVALID") from exc
    required = {"type", "client_email", "private_key", "token_uri"}
    if (
        not isinstance(payload, dict)
        or set(payload) < required
        or payload.get("type") != "service_account"
        or payload.get("token_uri") != GOOGLE_TOKEN_URI
        or not isinstance(payload.get("client_email"), str)
        or "@" not in payload["client_email"]
        or not isinstance(payload.get("private_key"), str)
        or "PRIVATE KEY" not in payload["private_key"]
    ):
        raise ConfigurationError("GOOGLE_SERVICE_ACCOUNT_SECRET_STRUCTURE_INVALID")
    return payload


class GoogleSheetsReadonlyAdapter:
    def __init__(
        self,
        *,
        spreadsheet_id: str,
        service_account_b64: str | None = None,
        session: Any | None = None,
        timeout_seconds: float = 20.0,
        attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if spreadsheet_id != TARGET_SPREADSHEET_ID:
            raise ConfigurationError("GOOGLE_SHEET_ID_MISMATCH")
        if not math.isfinite(float(timeout_seconds)) or timeout_seconds <= 0:
            raise ConfigurationError("GOOGLE_TIMEOUT_INVALID")
        if attempts < 1 or attempts > 5:
            raise ConfigurationError("GOOGLE_ATTEMPTS_INVALID")
        self.spreadsheet_id = spreadsheet_id
        self.timeout_seconds = float(timeout_seconds)
        self.attempts = int(attempts)
        self.sleeper = sleeper
        self.call_ledger: list[dict[str, Any]] = []
        if session is not None:
            self.session = session
        else:
            info = decode_service_account_b64(service_account_b64 or "")
            try:
                from google.auth.transport.requests import AuthorizedSession
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_info(
                    info, scopes=[GOOGLE_SHEETS_READONLY_SCOPE]
                )
                self.session = AuthorizedSession(credentials)
            except Exception as exc:
                raise ConfigurationError("GOOGLE_CREDENTIAL_INITIALIZATION_FAILED") from exc
            finally:
                info = None

    def fetch(self) -> list[WebsiteSheetRow]:
        encoded_range = quote(TARGET_RANGE, safe="")
        url = (
            "https://sheets.googleapis.com/v4/spreadsheets/"
            f"{TARGET_SPREADSHEET_ID}/values/{encoded_range}"
        )
        params = {"majorDimension": "ROWS", "valueRenderOption": "FORMATTED_VALUE"}
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.timeout_seconds,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                self.call_ledger.append(
                    {"method": "GET", "endpoint": "sheets.values.get", "status": "NETWORK_ERROR"}
                )
                if attempt == self.attempts:
                    raise TransportError("SHEET_NETWORK_OR_TIMEOUT") from exc
                self.sleeper(min(8.0, float(2 ** (attempt - 1))))
                continue
            status = int(response.status_code)
            self.call_ledger.append(
                {"method": "GET", "endpoint": "sheets.values.get", "status": status}
            )
            if 300 <= status < 400 or "Location" in response.headers:
                raise TransportError("SHEET_REDIRECT_REJECTED")
            if status == 200:
                try:
                    payload = response.json()
                except Exception as exc:
                    raise TransportError("SHEET_RESPONSE_NOT_JSON") from exc
                if not isinstance(payload, dict):
                    raise TransportError("SHEET_RESPONSE_NOT_OBJECT")
                returned_range = payload.get("range")
                if returned_range is not None and not (
                    isinstance(returned_range, str)
                    and returned_range.startswith(
                        (TARGET_TAB + "!", "'" + TARGET_TAB + "'!")
                    )
                ):
                    raise ContractError("SHEET_RESPONSE_TAB_MISMATCH")
                return parse_sheet_values(payload.get("values"))
            if status not in {429, 500, 502, 503, 504}:
                raise TransportError(f"SHEET_HTTP_{status}")
            if attempt < self.attempts:
                self.sleeper(min(8.0, float(2 ** (attempt - 1))))
        raise TransportError("SHEET_RETRY_EXHAUSTED")


def _slugify(code: str) -> str:
    normalized = unicodedata.normalize("NFKD", code).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if not value:
        value = "sku-" + hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
    return value[:120].rstrip("-")


def _validate_slug(value: str) -> str:
    if not _SLUG_RE.fullmatch(value) or len(value) > 120:
        raise ContractError("SHEET_SLUG_INVALID")
    return value


def validate_website_payload(payload: Any, *, max_products: int) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "generated_at",
        "source_data_as_of",
        "total",
        "items",
    }:
        raise CacheUnavailable("WEBSITE_CATALOG_SCHEMA_INVALID")
    if payload.get("schema_version") != WEBSITE_SCHEMA_VERSION:
        raise CacheUnavailable("WEBSITE_CATALOG_SCHEMA_VERSION_INVALID")
    items = payload.get("items")
    total = payload.get("total")
    if (
        not isinstance(items, list)
        or not isinstance(total, int)
        or isinstance(total, bool)
        or total != len(items)
        or total > max_products
    ):
        raise CacheUnavailable("WEBSITE_CATALOG_COUNT_INVALID")
    _parse_timestamp(payload.get("generated_at"), "WEBSITE_CATALOG_GENERATED_AT_INVALID")
    _parse_timestamp(payload.get("source_data_as_of"), "WEBSITE_CATALOG_SOURCE_CUTOFF_INVALID")
    seen_codes: set[str] = set()
    seen_slugs: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != ITEM_FIELDS:
            raise CacheUnavailable("WEBSITE_CATALOG_ITEM_FIELDS_INVALID")
        code = item.get("code")
        slug = item.get("slug")
        price = item.get("sale_price")
        availability = item.get("availability")
        images = item.get("images")
        if not isinstance(code, str) or not code or code != code.strip() or code in seen_codes:
            raise CacheUnavailable("WEBSITE_CATALOG_CODE_INVALID")
        if not isinstance(slug, str) or not _SLUG_RE.fullmatch(slug) or slug in seen_slugs:
            raise CacheUnavailable("WEBSITE_CATALOG_SLUG_INVALID")
        seen_codes.add(code)
        seen_slugs.add(slug)
        if (
            not isinstance(item.get("name"), str)
            or not item["name"]
            or not isinstance(item.get("attributes"), dict)
            or set(item["attributes"]) != {"color", "size"}
            or not isinstance(images, list)
            or len(images) != 1
            or not is_safe_website_image(images[0])
            or not isinstance(price, (int, float))
            or isinstance(price, bool)
            or not math.isfinite(float(price))
            or price <= 0
            or item.get("price_status") != "available"
            or not isinstance(availability, dict)
            or set(availability) != set(BRANCH_SLUGS)
            or any(
                value not in {"in_stock", "out_of_stock", "unavailable"}
                for value in availability.values()
            )
            or not isinstance(item.get("featured"), bool)
            or (
                item.get("display_order") is not None
                and (not isinstance(item["display_order"], int) or isinstance(item["display_order"], bool))
            )
        ):
            raise CacheUnavailable("WEBSITE_CATALOG_ITEM_VALUE_INVALID")
        _parse_timestamp(item.get("data_as_of"), "WEBSITE_CATALOG_ITEM_CUTOFF_INVALID")
        if item["data_as_of"] != payload["source_data_as_of"]:
            raise CacheUnavailable("WEBSITE_CATALOG_ITEM_CUTOFF_MISMATCH")
        for field in ("source_group", "category", "audience", "collection"):
            if item[field] is not None and not isinstance(item[field], str):
                raise CacheUnavailable("WEBSITE_CATALOG_EDITORIAL_VALUE_INVALID")
    return payload


class WebsiteCatalogStore:
    def __init__(
        self,
        path: Path,
        status_path: Path,
        *,
        max_age_seconds: float,
        source_max_age_seconds: float | None = None,
        max_products: int,
        max_response_bytes: int,
        now_provider: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        source_age_limit = (
            max_age_seconds if source_max_age_seconds is None else source_max_age_seconds
        )
        if (
            max_age_seconds <= 0
            or source_age_limit <= 0
            or max_products < 1
            or max_response_bytes < 10_000
        ):
            raise ConfigurationError("WEBSITE_CATALOG_STORE_CONFIG_INVALID")
        self.path = path
        self.status_path = status_path
        self.max_age_seconds = float(max_age_seconds)
        self.source_max_age_seconds = float(source_age_limit)
        self.max_products = int(max_products)
        self.max_response_bytes = int(max_response_bytes)
        self.now_provider = now_provider

    def commit(
        self,
        payload: Mapping[str, Any],
        *,
        fault_injector: Callable[[str], None] | None = None,
    ) -> dict[str, Any]:
        validated = validate_website_payload(dict(payload), max_products=self.max_products)
        body = (
            json.dumps(validated, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        if len(body) > self.max_response_bytes:
            raise ContractError("WEBSITE_CATALOG_RESPONSE_TOO_LARGE")
        body = _atomic_json(self.path, validated, fault_injector=fault_injector)
        return {
            "etag": '"' + hashlib.sha256(body).hexdigest() + '"',
            "bytes": len(body),
            "total": validated["total"],
        }

    def read(self) -> tuple[dict[str, Any], bytes, str]:
        if self.path.is_symlink() or not self.path.is_file():
            raise CacheUnavailable("WEBSITE_CATALOG_MISSING")
        if stat.S_IMODE(self.path.stat().st_mode) & 0o077:
            raise CacheUnavailable("WEBSITE_CATALOG_PERMISSIONS_UNSAFE")
        if self.path.stat().st_size > self.max_response_bytes:
            raise CacheUnavailable("WEBSITE_CATALOG_RESPONSE_TOO_LARGE")
        body = self.path.read_bytes()
        try:
            payload = json.loads(body)
        except Exception as exc:
            raise CacheUnavailable("WEBSITE_CATALOG_INVALID_JSON") from exc
        validated = validate_website_payload(payload, max_products=self.max_products)
        now = self.now_provider()
        if now.tzinfo is None:
            raise CacheUnavailable("WEBSITE_CATALOG_NOW_TIMEZONE_MISSING")
        generated = _parse_timestamp(
            validated["generated_at"], "WEBSITE_CATALOG_GENERATED_AT_INVALID"
        )
        age = (now.astimezone(dt.timezone.utc) - generated).total_seconds()
        if age < 0:
            raise CacheUnavailable("WEBSITE_CATALOG_GENERATED_IN_FUTURE")
        if age > self.max_age_seconds:
            raise CacheUnavailable("WEBSITE_CATALOG_TOO_OLD")
        source_cutoff = _parse_timestamp(
            validated["source_data_as_of"], "WEBSITE_CATALOG_SOURCE_CUTOFF_INVALID"
        )
        source_age = (now.astimezone(dt.timezone.utc) - source_cutoff).total_seconds()
        if source_age < 0:
            raise CacheUnavailable("WEBSITE_CATALOG_SOURCE_IN_FUTURE")
        if source_age > self.source_max_age_seconds:
            raise CacheUnavailable("WEBSITE_CATALOG_SOURCE_TOO_OLD")
        return validated, body, '"' + hashlib.sha256(body).hexdigest() + '"'

    def record_status(
        self,
        *,
        last_error_code: str | None,
        last_kiot_sync_at: str | None = None,
        last_sheet_read_at: str | None = None,
        last_website_build_at: str | None = None,
        source_data_as_of: str | None = None,
        item_count: int | None = None,
    ) -> None:
        prior: dict[str, Any] = {}
        if self.status_path.is_file() and not self.status_path.is_symlink():
            try:
                candidate = json.loads(self.status_path.read_text(encoding="utf-8"))
                if isinstance(candidate, dict):
                    prior = candidate
            except Exception:
                prior = {}
        payload = {
            "schema_version": "the_gate_website_catalog_status.v1",
            "last_kiot_sync_at": last_kiot_sync_at or prior.get("last_kiot_sync_at"),
            "last_sheet_read_at": last_sheet_read_at or prior.get("last_sheet_read_at"),
            "last_website_build_at": last_website_build_at or prior.get("last_website_build_at"),
            "source_data_as_of": source_data_as_of or prior.get("source_data_as_of"),
            "item_count": item_count if item_count is not None else prior.get("item_count"),
            "last_error_code": last_error_code,
        }
        _atomic_json(self.status_path, payload)


class WebsiteCatalogBuilder:
    def __init__(
        self,
        *,
        reader_factory: Callable[[], Any],
        sheet_adapter: Any,
        store: WebsiteCatalogStore,
        logger: logging.Logger,
        max_products: int,
        now_provider: Callable[[], dt.datetime] = utc_now,
    ) -> None:
        self.reader_factory = reader_factory
        self.sheet_adapter = sheet_adapter
        self.store = store
        self.logger = logger
        self.max_products = max_products
        self.now_provider = now_provider

    def build(
        self, *, fault_injector: Callable[[str], None] | None = None
    ) -> dict[str, Any]:
        now = self.now_provider()
        try:
            reader = self.reader_factory()
            rows = self.sheet_adapter.fetch()
            try:
                self.store.record_status(
                    last_error_code=None,
                    last_sheet_read_at=_iso(now),
                    source_data_as_of=reader.status["data_as_of"],
                )
            except Exception:
                self.logger.warning("website_catalog_warning code=WEBSITE_STATUS_WRITE_FAILED")
            candidates = [row for row in rows if row.publish]
            if len(candidates) > self.max_products:
                raise ContractError("WEBSITE_CATALOG_PRODUCT_LIMIT_EXCEEDED")
            items: list[dict[str, Any]] = []
            seen_slugs: set[str] = set()
            excluded_ineligible = 0
            excluded_missing_image = 0
            for row in candidates:
                record = reader.get_record(row.product_code, public_only=True)
                if record is None:
                    excluded_ineligible += 1
                    continue
                custom_image = row.custom_image_url if is_safe_website_image(row.custom_image_url) else None
                source_images = [image for image in record.get("images", []) if is_safe_website_image(image)]
                image = custom_image or (source_images[0] if source_images else None)
                if image is None:
                    excluded_missing_image += 1
                    continue
                slug = _validate_slug(row.slug) if row.slug else _slugify(row.product_code)
                if slug in seen_slugs:
                    raise ContractError("WEBSITE_CATALOG_DUPLICATE_SLUG")
                seen_slugs.add(slug)
                name = row.custom_name or row.final_name or record["name"]
                items.append(
                    {
                        "code": record["code"],
                        "name": name,
                        "slug": slug,
                        "attributes": record["attributes"],
                        "images": [image],
                        "sale_price": record["sale_price"],
                        "price_status": record["price_status"],
                        "availability": record["availability"],
                        "source_group": row.source_group,
                        "category": row.category,
                        "audience": row.audience,
                        "collection": row.collection,
                        "display_order": row.display_order,
                        "featured": row.featured,
                        "data_as_of": reader.status["data_as_of"],
                    }
                )
            items.sort(
                key=lambda item: (
                    item["display_order"] if item["display_order"] is not None else 1_000_001,
                    item["code"],
                )
            )
            payload = {
                "schema_version": WEBSITE_SCHEMA_VERSION,
                "generated_at": _iso(now),
                "source_data_as_of": reader.status["data_as_of"],
                "total": len(items),
                "items": items,
            }
            committed = self.store.commit(payload, fault_injector=fault_injector)
            try:
                self.store.record_status(
                    last_error_code=None,
                    last_sheet_read_at=_iso(now),
                    last_website_build_at=_iso(now),
                    source_data_as_of=reader.status["data_as_of"],
                    item_count=len(items),
                )
            except Exception:
                self.logger.warning("website_catalog_warning code=WEBSITE_STATUS_WRITE_FAILED")
            self.logger.info(
                "website_catalog_pass items=%s excluded_ineligible=%s excluded_missing_image=%s",
                len(items),
                excluded_ineligible,
                excluded_missing_image,
            )
            return {
                "status": "PASS",
                "total": len(items),
                "excluded_ineligible": excluded_ineligible,
                "excluded_missing_image": excluded_missing_image,
                **committed,
            }
        except Exception as exc:
            code = exc.code if isinstance(exc, (ContractError, CacheUnavailable, TransportError)) else "WEBSITE_CATALOG_BUILD_UNEXPECTED"
            try:
                self.store.record_status(last_error_code=code)
            except Exception:
                self.logger.warning("website_catalog_warning code=WEBSITE_STATUS_WRITE_FAILED")
            self.logger.error("website_catalog_failed code=%s", code)
            if isinstance(exc, (ContractError, CacheUnavailable, TransportError)):
                raise
            raise ContractError(code) from exc
