from __future__ import annotations

import math
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from .contracts import (
    ACTIVE_STATUSES,
    BRANCH_CONTRACTS,
    BRANCH_SLUGS,
    INTERNAL_RECORD_FIELDS,
    PRICE_STATUSES,
)
from .errors import ContractError


COLOR_NAMES = frozenset({"COLOR", "COLOUR", "MAU", "MAU SAC"})
SIZE_NAMES = frozenset({"SIZE", "KICH CO", "KICH THUOC"})


def _normalize_attribute_name(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def extract_attributes(product: dict[str, Any]) -> dict[str, str | None]:
    color: str | None = None
    size: str | None = None
    for item in product.get("attributes") or []:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_attribute_name(item.get("attributeName"))
        value = _clean_text(item.get("attributeValue"))
        if normalized in COLOR_NAMES and color is None:
            color = value
        elif normalized in SIZE_NAMES and size is None:
            size = value
    return {"color": color, "size": size}


def extract_images(product: dict[str, Any]) -> list[str]:
    images: list[str] = []
    seen: set[str] = set()
    for item in product.get("images") or []:
        candidate: Any
        if isinstance(item, str):
            candidate = item
        elif isinstance(item, dict):
            candidate = item.get("Image") or item.get("image") or item.get("url")
        else:
            continue
        value = _clean_text(candidate)
        if not value or value in seen:
            continue
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            continue
        seen.add(value)
        images.append(value)
    return images


def extract_inventory(product: dict[str, Any]) -> dict[str, int | float | None]:
    by_id: dict[int, int | float | None] = {}
    approved_ids = {branch.expected_id for branch in BRANCH_CONTRACTS}
    for item in product.get("inventories") or []:
        if not isinstance(item, dict):
            raise ContractError("INVENTORY_ITEM_NOT_OBJECT")
        branch_id = item.get("branchId")
        if branch_id not in approved_ids:
            raise ContractError("OUT_OF_SCOPE_BRANCH_IN_SOURCE_RESPONSE")
        if branch_id in by_id:
            raise ContractError("DUPLICATE_BRANCH_INVENTORY_ROW")
        by_id[int(branch_id)] = _number(item.get("onHand"))
    return {
        branch.slug: by_id.get(branch.expected_id)
        for branch in BRANCH_CONTRACTS
    }


def build_record(
    product: dict[str, Any],
    *,
    sale_prices: dict[str, Any],
    generation_id: str,
    data_as_of: str,
) -> dict[str, Any]:
    code = _clean_text(product.get("code"))
    if not code:
        raise ContractError("PRODUCT_CODE_MISSING")
    name = _clean_text(product.get("fullName")) or _clean_text(product.get("name"))
    if not name:
        raise ContractError("PRODUCT_NAME_MISSING")
    inventory = extract_inventory(product)
    availability = {
        slug: (
            "unavailable"
            if inventory[slug] is None
            else "in_stock"
            if inventory[slug] > 0
            else "out_of_stock"
        )
        for slug in BRANCH_SLUGS
    }
    if code in sale_prices:
        sale_price, price_status = classify_sale_price(sale_prices[code])
    else:
        sale_price, price_status = None, "unavailable"
    source_active = product.get("isActive")
    active_status = (
        "active"
        if source_active is True
        else "inactive"
        if source_active is False
        else "unknown"
    )
    record = {
        "code": code,
        "generation_id": generation_id,
        "name": name,
        "attributes": extract_attributes(product),
        "images": extract_images(product),
        "sale_price": sale_price,
        "price_status": price_status,
        "active_status": active_status,
        "availability": availability,
        "inventory": inventory,
        "modified_at": _clean_text(product.get("modifiedDate")),
        "data_as_of": data_as_of,
        "stale": False,
    }
    validate_record(record)
    return record


def validate_record(record: dict[str, Any]) -> None:
    if set(record) != INTERNAL_RECORD_FIELDS:
        raise ContractError("CACHE_RECORD_FIELD_ALLOWLIST_VIOLATION")
    if not isinstance(record.get("code"), str) or not record["code"].strip():
        raise ContractError("CACHE_PRODUCT_CODE_INVALID")
    if not isinstance(record.get("generation_id"), str) or not re.fullmatch(
        r"[0-9a-f]{32}", record["generation_id"]
    ):
        raise ContractError("CACHE_GENERATION_ID_INVALID")
    if not isinstance(record.get("name"), str) or not record["name"].strip():
        raise ContractError("CACHE_PRODUCT_NAME_INVALID")
    if set(record.get("attributes") or {}) != {"color", "size"}:
        raise ContractError("CACHE_ATTRIBUTE_FIELD_ALLOWLIST_VIOLATION")
    if set(record.get("availability") or {}) != set(BRANCH_SLUGS):
        raise ContractError("CACHE_AVAILABILITY_BRANCH_ALLOWLIST_VIOLATION")
    if set(record.get("inventory") or {}) != set(BRANCH_SLUGS):
        raise ContractError("CACHE_INVENTORY_BRANCH_ALLOWLIST_VIOLATION")
    if record.get("price_status") not in PRICE_STATUSES:
        raise ContractError("CACHE_PRICE_STATUS_INVALID")
    if record.get("active_status") not in ACTIVE_STATUSES:
        raise ContractError("CACHE_ACTIVE_STATUS_INVALID")
    for value in (record.get("inventory") or {}).values():
        if value is not None and (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(float(value))
        ):
            raise ContractError("CACHE_INVENTORY_VALUE_INVALID")
    if record.get("sale_price") is not None and (
        not isinstance(record["sale_price"], (int, float))
        or isinstance(record["sale_price"], bool)
        or not math.isfinite(float(record["sale_price"]))
    ):
        raise ContractError("CACHE_SALE_PRICE_INVALID")
    price_status = record["price_status"]
    sale_price = record["sale_price"]
    if price_status == "available" and not (sale_price is not None and sale_price > 0):
        raise ContractError("CACHE_AVAILABLE_PRICE_NOT_POSITIVE")
    if price_status == "zero" and sale_price != 0:
        raise ContractError("CACHE_ZERO_PRICE_STATUS_INVALID")
    if price_status == "unavailable" and sale_price is not None:
        raise ContractError("CACHE_UNAVAILABLE_PRICE_STATUS_INVALID")
    if price_status == "invalid" and sale_price is not None and sale_price >= 0:
        raise ContractError("CACHE_INVALID_PRICE_STATUS_INVALID")


def classify_sale_price(value: Any) -> tuple[int | float | None, str]:
    parsed = _number(value)
    if parsed is None:
        return None, "invalid"
    if parsed > 0:
        return parsed, "available"
    if parsed == 0:
        return parsed, "zero"
    return parsed, "invalid"
