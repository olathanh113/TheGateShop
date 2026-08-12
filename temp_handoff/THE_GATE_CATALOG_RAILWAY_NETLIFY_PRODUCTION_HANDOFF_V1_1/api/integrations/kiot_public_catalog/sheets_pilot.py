from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse


TARGET_SPREADSHEET_ID = "1kWGZy7Stnrs842lnt36Y_3ROO-t_pfNvRcz-cVwU1Eg"
AUTO_TAB = "KIOT_CATALOG_AUTO"
WEBSITE_TAB = "WEBSITE_PRODUCTS"
ALLOWED_TABS = frozenset({AUTO_TAB, WEBSITE_TAB})
PILOT_SIZE = 150

AUTO_WRITABLE_HEADERS = frozenset(
    {
        "Tên SP",
        "kiot_price",
        "image_1_url",
        "image_2_url",
        "image_3_url",
        "image_4_url",
        "image_5_url",
        "sync_status",
    }
)
WEBSITE_WRITABLE_HEADERS = frozenset({"product_id", "kiot_price"})
WEBSITE_MANUAL_HEADERS = frozenset(
    {
        "priority",
        "custom_name",
        "category",
        "audience",
        "collection",
        "display_order",
        "featured",
        "publish",
        "custom_image_url",
        "note",
        "slug",
    }
)


class PilotContractError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CatalogMapping:
    sku: str
    state: str
    name: str | None
    sale_price: int | float | None
    images: tuple[str, ...]
    public_eligible: bool
    invalid_image_count: int


@dataclass(frozen=True)
class CellUpdate:
    tab: str
    row: int
    column_index: int
    header: str
    value: Any


def normalize_sku(value: Any) -> str:
    return str(value or "").strip().casefold()


def header_index(headers: Sequence[Any], expected: str) -> int:
    matches = [index for index, value in enumerate(headers) if str(value).strip() == expected]
    if len(matches) != 1:
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    return matches[0]


def validate_target_identity(
    spreadsheet_id: str, sheets: Sequence[Mapping[str, Any]]
) -> dict[str, int]:
    if spreadsheet_id != TARGET_SPREADSHEET_ID:
        raise PilotContractError("BLOCKED_TARGET_IDENTITY")
    resolved: dict[str, list[int]] = {name: [] for name in ALLOWED_TABS}
    for sheet in sheets:
        title = str(sheet.get("title") or "")
        if title in resolved and isinstance(sheet.get("sheet_id"), int):
            resolved[title].append(int(sheet["sheet_id"]))
    if any(len(ids) != 1 for ids in resolved.values()):
        raise PilotContractError("BLOCKED_TARGET_IDENTITY")
    return {name: ids[0] for name, ids in resolved.items()}


def _validate_skus(values: Sequence[Any]) -> list[str]:
    normalized = [normalize_sku(value) for value in values]
    if len(normalized) != PILOT_SIZE or any(not value for value in normalized):
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    if len(set(normalized)) != PILOT_SIZE:
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    return normalized


def validate_pilot_sku_contract(
    auto_headers: Sequence[Any],
    auto_rows: Sequence[Sequence[Any]],
    website_headers: Sequence[Any],
    website_rows: Sequence[Sequence[Any]],
) -> list[str]:
    auto_key = header_index(auto_headers, "SKU")
    website_key = header_index(website_headers, "product_code")
    auto_skus = _validate_skus(
        [row[auto_key] if auto_key < len(row) else None for row in auto_rows]
    )
    website_skus = _validate_skus(
        [row[website_key] if website_key < len(row) else None for row in website_rows]
    )
    if auto_skus != website_skus:
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    return auto_skus


def is_safe_image_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_public_eligible(record: Mapping[str, Any]) -> bool:
    price = record.get("sale_price")
    valid_price = (
        isinstance(price, (int, float))
        and not isinstance(price, bool)
        and math.isfinite(float(price))
        and float(price) > 0
    )
    return (
        bool(normalize_sku(record.get("code")))
        and record.get("price_status") == "available"
        and valid_price
        and record.get("active_status") == "active"
    )


def map_catalog_records(
    skus: Sequence[str], records: Iterable[Mapping[str, Any]]
) -> list[CatalogMapping]:
    by_code: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        key = normalize_sku(record.get("code"))
        if key:
            by_code.setdefault(key, []).append(record)

    output: list[CatalogMapping] = []
    for sku in skus:
        key = normalize_sku(sku)
        candidates = by_code.get(key, [])
        if not candidates:
            output.append(CatalogMapping(key, "UNMATCHED", None, None, (), False, 0))
            continue
        if len(candidates) != 1:
            output.append(CatalogMapping(key, "AMBIGUOUS", None, None, (), False, 0))
            continue
        record = candidates[0]
        raw_images = record.get("images") or []
        images = tuple(
            str(value).strip() for value in raw_images if is_safe_image_url(value)
        )
        invalid_count = sum(1 for value in raw_images if not is_safe_image_url(value))
        eligible = is_public_eligible(record)
        state = "MATCHED" if eligible else "NOT_PUBLIC_ELIGIBLE"
        if not images:
            state += "_MISSING_IMAGE"
        output.append(
            CatalogMapping(
                sku=key,
                state=state,
                name=str(record.get("name") or "").strip() or None,
                sale_price=record.get("sale_price") if eligible else None,
                images=images,
                public_eligible=eligible,
                invalid_image_count=invalid_count,
            )
        )
    return output


def build_auto_updates(
    headers: Sequence[Any], mappings: Sequence[CatalogMapping], *, first_row: int = 3
) -> list[CellUpdate]:
    if len(mappings) != PILOT_SIZE:
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    positions = {str(value).strip(): index for index, value in enumerate(headers)}
    required = {"Tên SP", "kiot_price", "image_1_url", "sync_status"}
    if not required.issubset(positions):
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    image_headers = [f"image_{index}_url" for index in range(1, 6)]
    updates: list[CellUpdate] = []
    for offset, mapping in enumerate(mappings):
        row = first_row + offset
        values = {
            "Tên SP": mapping.name or "",
            "kiot_price": mapping.sale_price if mapping.sale_price is not None else "",
            "sync_status": mapping.state,
        }
        for index, header in enumerate(image_headers):
            if header in positions:
                values[header] = mapping.images[index] if index < len(mapping.images) else ""
        for header, value in values.items():
            updates.append(
                CellUpdate(AUTO_TAB, row, positions[header], header, value)
            )
    return updates


def website_formula_repairs(
    auto_headers: Sequence[Any],
    website_headers: Sequence[Any],
    current_formula_rows: Sequence[Sequence[Any]],
    *,
    first_row: int = 2,
    last_row: int = 151,
) -> list[CellUpdate]:
    auto_product_id = header_index(auto_headers, "product_id") + 1
    auto_price = header_index(auto_headers, "kiot_price") + 1
    website_code = header_index(website_headers, "product_code")
    targets = {
        "product_id": auto_product_id,
        "kiot_price": auto_price,
    }
    positions = {str(value).strip(): index for index, value in enumerate(website_headers)}
    repairs: list[CellUpdate] = []
    code_column = a1_column(website_code)
    for row_number in range(first_row, last_row + 1):
        source_row = current_formula_rows[row_number - first_row]
        for header, lookup_index in targets.items():
            column = positions.get(header)
            if column is None:
                raise PilotContractError("BLOCKED_PILOT_CONTRACT")
            expected = (
                f'=IFERROR(VLOOKUP({code_column}{row_number};'
                f'KIOT_CATALOG_AUTO!$A$3:$Z$152;{lookup_index};FALSE);"")'
            )
            current = source_row[column] if column < len(source_row) else None
            if current != expected:
                repairs.append(
                    CellUpdate(WEBSITE_TAB, row_number, column, header, expected)
                )
    return repairs


def final_image_formula(row: int, website_headers: Sequence[Any]) -> str:
    primary = a1_column(header_index(website_headers, "primary_image_url"))
    custom = a1_column(header_index(website_headers, "custom_image_url"))
    return f'=IF({custom}{row}<>"";{custom}{row};{primary}{row})'


def a1_column(zero_based_index: int) -> str:
    if zero_based_index < 0:
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    value = zero_based_index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def validate_write_plan(plan: Mapping[str, Iterable[str]]) -> None:
    if not set(plan).issubset(ALLOWED_TABS):
        raise PilotContractError("BLOCKED_TARGET_IDENTITY")
    for tab, headers in plan.items():
        allowed = AUTO_WRITABLE_HEADERS if tab == AUTO_TAB else WEBSITE_WRITABLE_HEADERS
        if not set(headers).issubset(allowed):
            raise PilotContractError("BLOCKED_PILOT_CONTRACT")


def manual_snapshot(
    headers: Sequence[Any], rows: Sequence[Sequence[Any]]
) -> tuple[tuple[Any, ...], ...]:
    positions = [
        index
        for index, value in enumerate(headers)
        if str(value).strip() in WEBSITE_MANUAL_HEADERS
    ]
    if {str(headers[index]).strip() for index in positions} != WEBSITE_MANUAL_HEADERS:
        raise PilotContractError("BLOCKED_PILOT_CONTRACT")
    return tuple(
        tuple(row[index] if index < len(row) else None for index in positions)
        for row in rows
    )


def assert_manual_preserved(
    headers: Sequence[Any],
    before_rows: Sequence[Sequence[Any]],
    after_rows: Sequence[Sequence[Any]],
) -> None:
    if manual_snapshot(headers, before_rows) != manual_snapshot(headers, after_rows):
        raise PilotContractError("MANUAL_COLUMNS_CHANGED")


def build_rollback_updates(
    applied: Sequence[CellUpdate],
    before_values: Sequence[Sequence[Any]],
    before_formulas: Sequence[Sequence[Any]],
    *,
    first_sheet_row: int,
) -> list[CellUpdate]:
    rollback: list[CellUpdate] = []
    for update in applied:
        row_index = update.row - first_sheet_row
        if row_index < 0 or row_index >= len(before_formulas):
            raise PilotContractError("ROLLBACK_RANGE_INVALID")
        formula_row = before_formulas[row_index]
        value_row = before_values[row_index]
        prior_formula = (
            formula_row[update.column_index]
            if update.column_index < len(formula_row)
            else None
        )
        prior_value = (
            value_row[update.column_index]
            if update.column_index < len(value_row)
            else None
        )
        prior = (
            prior_formula
            if isinstance(prior_formula, str) and prior_formula.startswith("=")
            else prior_value
        )
        rollback.append(
            CellUpdate(
                update.tab,
                update.row,
                update.column_index,
                update.header,
                "" if prior is None else prior,
            )
        )
    return rollback
