from __future__ import annotations

import datetime as dt
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import (
    BRANCH_CONTRACTS,
    EXPECTED_PRICEBOOK_ID,
    EXPECTED_PRICEBOOK_NAME,
)
from .errors import ContractError


TZ = dt.timezone(dt.timedelta(hours=7))


@dataclass(frozen=True)
class ResolvedBranch:
    slug: str
    label: str
    branch_id: int
    live_name: str


@dataclass(frozen=True)
class ResolvedContract:
    pricebook_id: int
    pricebook_name: str
    pricebook_active: bool
    pricebook_exact_match_count: int
    pricebook_is_global: bool
    pricebook_start_at: str | None
    pricebook_end_at: str | None
    branches: tuple[ResolvedBranch, ...]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "pricebook": {
                "id": self.pricebook_id,
                "name": self.pricebook_name,
                "is_active": self.pricebook_active,
                "exact_match_count": self.pricebook_exact_match_count,
                "is_global": self.pricebook_is_global,
                "start_at": self.pricebook_start_at,
                "end_at": self.pricebook_end_at,
            },
            "branches": [asdict(branch) for branch in self.branches],
        }


def normalize_branch_name(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"^\s*\d+\s*[.\-:]?\s*", "", text.upper().strip())
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def _parse_datetime(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ContractError("PRICEBOOK_EFFECTIVE_DATE_INVALID") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)


def _all_rows(client: Any, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for batch, _total, _page in client.paginate(path, params, page_size=100):
        rows.extend(batch)
    return rows


def resolve_live_contract(client: Any, *, now: dt.datetime | None = None) -> ResolvedContract:
    branch_rows = _all_rows(client, "/branches", {})
    resolved: list[ResolvedBranch] = []
    for expected in BRANCH_CONTRACTS:
        matches = [
            row
            for row in branch_rows
            if normalize_branch_name(row.get("branchName") or row.get("name"))
            in expected.normalized_aliases
        ]
        if len(matches) != 1:
            raise ContractError("APPROVED_BRANCH_MAPPING_NOT_UNIQUE")
        row = matches[0]
        live_name = row.get("branchName") or row.get("name")
        if row.get("id") != expected.expected_id or live_name != expected.expected_live_name:
            raise ContractError("APPROVED_BRANCH_DRIFT")
        # Owner accepted a live baseline where the branch endpoint exposes no
        # status field. Any later status-field appearance is schema/status drift
        # and requires a new Owner decision, even if its value looks active.
        if "isActive" in row or "status" in row:
            raise ContractError("APPROVED_BRANCH_STATUS_DRIFT")
        resolved.append(
            ResolvedBranch(
                slug=expected.slug,
                label=expected.label,
                branch_id=expected.expected_id,
                live_name=expected.expected_live_name,
            )
        )

    pricebook_rows = _all_rows(
        client,
        "/pricebooks",
        {"includePriceBookBranch": "true"},
    )
    matches = [row for row in pricebook_rows if row.get("name") == EXPECTED_PRICEBOOK_NAME]
    if len(matches) != 1:
        raise ContractError("SALE_PRICEBOOK_NOT_UNIQUE_EXACT")
    pricebook = matches[0]
    if pricebook.get("id") != EXPECTED_PRICEBOOK_ID:
        raise ContractError("PRICEBOOK_ID_DRIFT")
    if pricebook.get("isActive") is not True:
        raise ContractError("SALE_PRICEBOOK_INACTIVE")

    current = (now or dt.datetime.now(TZ)).astimezone(TZ)
    starts = _parse_datetime(pricebook.get("startDate"))
    ends = _parse_datetime(pricebook.get("endDate"))
    if starts is not None and current < starts:
        raise ContractError("SALE_PRICEBOOK_NOT_YET_EFFECTIVE")
    if ends is not None and current > ends:
        raise ContractError("SALE_PRICEBOOK_EXPIRED")

    is_global = pricebook.get("isGlobal") is True
    relation_ids = {
        item.get("branchId")
        for item in (pricebook.get("priceBookBranches") or [])
        if isinstance(item, dict)
    }
    if not is_global and any(branch.branch_id not in relation_ids for branch in resolved):
        raise ContractError("SALE_PRICEBOOK_SCOPE_EXCLUDES_APPROVED_BRANCH")

    return ResolvedContract(
        pricebook_id=EXPECTED_PRICEBOOK_ID,
        pricebook_name=EXPECTED_PRICEBOOK_NAME,
        pricebook_active=True,
        pricebook_exact_match_count=1,
        pricebook_is_global=is_global,
        pricebook_start_at=pricebook.get("startDate"),
        pricebook_end_at=pricebook.get("endDate"),
        branches=tuple(resolved),
    )
