from __future__ import annotations

from dataclasses import dataclass


TOKEN_URL = "https://id.kiotviet.vn/connect/token"
API_ORIGIN = "https://public.kiotapi.com"
TOKEN_SCOPE = "PublicApi.Access"

EXPECTED_PRICEBOOK_NAME = "SALE"
EXPECTED_PRICEBOOK_ID = 18892


@dataclass(frozen=True)
class BranchContract:
    slug: str
    label: str
    expected_id: int
    expected_live_name: str
    normalized_aliases: frozenset[str]


BRANCH_CONTRACTS = (
    BranchContract(
        slug="ton_that_thiep",
        label="Tôn Thất Thiệp",
        expected_id=83336,
        expected_live_name="3. TÔN THẤT THIỆP",
        normalized_aliases=frozenset({"TON THAT THIEP"}),
    ),
    BranchContract(
        slug="nguyen_trai",
        label="Nguyễn Trãi",
        expected_id=83335,
        expected_live_name="2. NGUYỄN TRÃI",
        normalized_aliases=frozenset({"NGUYEN TRAI"}),
    ),
    BranchContract(
        slug="tam_coc",
        label="Tam Cốc",
        expected_id=83348,
        expected_live_name="9. TC",
        normalized_aliases=frozenset({"TC"}),
    ),
)

BRANCH_SLUGS = tuple(branch.slug for branch in BRANCH_CONTRACTS)
APPROVED_BRANCH_IDS = tuple(branch.expected_id for branch in BRANCH_CONTRACTS)

INTERNAL_RECORD_FIELDS = frozenset(
    {
        "code",
        "generation_id",
        "name",
        "attributes",
        "images",
        "sale_price",
        "price_status",
        "active_status",
        "availability",
        "inventory",
        "modified_at",
        "data_as_of",
        "stale",
    }
)

PRICE_STATUSES = frozenset({"available", "unavailable", "zero", "invalid"})
ACTIVE_STATUSES = frozenset({"active", "inactive", "unknown"})

CATALOG_RESPONSE_FIELDS = (
    "code",
    "name",
    "attributes",
    "images",
    "sale_price",
    "price_status",
    "availability",
    "data_as_of",
    "stale",
)

INTERNAL_RESPONSE_FIELDS = CATALOG_RESPONSE_FIELDS + ("inventory",)
