from __future__ import annotations

import unittest

from integrations.kiot_public_catalog.sheets_pilot import (
    AUTO_TAB,
    TARGET_SPREADSHEET_ID,
    WEBSITE_TAB,
    CellUpdate,
    PilotContractError,
    assert_manual_preserved,
    build_auto_updates,
    build_rollback_updates,
    final_image_formula,
    map_catalog_records,
    validate_pilot_sku_contract,
    validate_target_identity,
    validate_write_plan,
    website_formula_repairs,
)


AUTO_HEADERS = [
    "SKU",
    "Tên SP",
    "Nhóm",
    "product_id",
    "kiot_price",
    "image_1_url",
    "image_2_url",
    "image_3_url",
    "image_4_url",
    "image_5_url",
    "sync_status",
]
WEBSITE_HEADERS = [
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
]


def skus() -> list[str]:
    return [f"SKU-{index:03d}" for index in range(150)]


def record(code: str, *, price=100, active="active", images=None) -> dict:
    return {
        "code": code,
        "name": f"Name {code}",
        "sale_price": price,
        "price_status": "available" if price is not None else "unavailable",
        "active_status": active,
        "images": ["https://img.example/one.jpg"] if images is None else images,
    }


class SheetsPilotTests(unittest.TestCase):
    def test_sheets_01_target_identity_and_exact_tab_ids(self):
        result = validate_target_identity(
            TARGET_SPREADSHEET_ID,
            [
                {"title": AUTO_TAB, "sheet_id": 10},
                {"title": WEBSITE_TAB, "sheet_id": 20},
            ],
        )
        self.assertEqual(result, {AUTO_TAB: 10, WEBSITE_TAB: 20})

    def test_sheets_02_target_or_tab_identity_mismatch_fails_closed(self):
        cases = (
            ("wrong", [{"title": AUTO_TAB, "sheet_id": 1}, {"title": WEBSITE_TAB, "sheet_id": 2}]),
            (TARGET_SPREADSHEET_ID, [{"title": AUTO_TAB, "sheet_id": 1}]),
            (
                TARGET_SPREADSHEET_ID,
                [
                    {"title": AUTO_TAB, "sheet_id": 1},
                    {"title": AUTO_TAB, "sheet_id": 2},
                    {"title": WEBSITE_TAB, "sheet_id": 3},
                ],
            ),
        )
        for spreadsheet_id, sheets in cases:
            with self.subTest(spreadsheet_id=spreadsheet_id, sheet_count=len(sheets)):
                with self.assertRaises(PilotContractError):
                    validate_target_identity(spreadsheet_id, sheets)

    def test_sheets_03_exact_sku_contract_allows_trim_case_but_not_fuzzy(self):
        codes = skus()
        auto = [[f" {code} "] for code in codes]
        website = [[index, code.lower()] for index, code in enumerate(codes)]
        resolved = validate_pilot_sku_contract(
            ["SKU"], auto, ["priority", "product_code"], website
        )
        self.assertEqual(len(resolved), 150)
        website[-1][1] += "-fuzzy"
        with self.assertRaises(PilotContractError):
            validate_pilot_sku_contract(
                ["SKU"], auto, ["priority", "product_code"], website
            )

    def test_sheets_04_blank_duplicate_or_wrong_count_fails_closed(self):
        codes = skus()
        for candidate in (codes[:-1], [*codes[:-1], ""], [*codes[:-1], codes[0]]):
            auto = [[value] for value in candidate]
            website = [[value] for value in candidate]
            with self.subTest(count=len(candidate)):
                with self.assertRaises(PilotContractError):
                    validate_pilot_sku_contract(["SKU"], auto, ["product_code"], website)

    def test_sheets_05_mapping_is_exact_and_ambiguous_does_not_choose(self):
        mappings = map_catalog_records(
            ["SKU-001", "SKU-002", "SKU-003"],
            [record("sku-001"), record("SKU-003"), record(" sku-003 ")],
        )
        self.assertEqual([item.state for item in mappings], ["MATCHED", "UNMATCHED", "AMBIGUOUS"])
        self.assertIsNone(mappings[1].sale_price)
        self.assertIsNone(mappings[2].name)

    def test_sheets_06_no_price_fallback_for_ineligible_record(self):
        mappings = map_catalog_records(
            ["SKU-001", "SKU-002"],
            [record("SKU-001", price=None), record("SKU-002", price=100, active="inactive")],
        )
        self.assertTrue(all(not item.public_eligible for item in mappings))
        self.assertTrue(all(item.sale_price is None for item in mappings))
        self.assertTrue(all(item.state.startswith("NOT_PUBLIC_ELIGIBLE") for item in mappings))

    def test_sheets_07_image_validation_and_missing_image_status(self):
        mappings = map_catalog_records(
            ["SKU-001"],
            [record("SKU-001", images=["javascript:bad", "https://img.example/good.jpg"])],
        )
        self.assertEqual(mappings[0].images, ("https://img.example/good.jpg",))
        self.assertEqual(mappings[0].invalid_image_count, 1)
        missing = map_catalog_records(["SKU-002"], [record("SKU-002", images=[])])[0]
        self.assertEqual(missing.state, "MATCHED_MISSING_IMAGE")

    def test_sheets_08_auto_updates_touch_only_allowlisted_headers(self):
        mappings = map_catalog_records(skus(), [record(code) for code in skus()])
        updates = build_auto_updates(AUTO_HEADERS, mappings)
        self.assertEqual({item.header for item in updates}, {"Tên SP", "kiot_price", "image_1_url", "image_2_url", "image_3_url", "image_4_url", "image_5_url", "sync_status"})
        self.assertNotIn("SKU", {item.header for item in updates})
        self.assertNotIn("product_id", {item.header for item in updates})

    def test_sheets_09_locale_formula_repairs_use_semicolon_and_live_indexes(self):
        current = [[""] * len(WEBSITE_HEADERS) for _ in range(150)]
        repairs = website_formula_repairs(AUTO_HEADERS, WEBSITE_HEADERS, current)
        first_product_id = next(item for item in repairs if item.header == "product_id")
        first_price = next(item for item in repairs if item.header == "kiot_price")
        self.assertEqual(first_product_id.value, '=IFERROR(VLOOKUP(B2;KIOT_CATALOG_AUTO!$A$3:$Z$152;4;FALSE);"")')
        self.assertEqual(first_price.value, '=IFERROR(VLOOKUP(B2;KIOT_CATALOG_AUTO!$A$3:$Z$152;5;FALSE);"")')
        self.assertNotIn(",", first_price.value)

    def test_sheets_10_custom_image_remains_preferred(self):
        self.assertEqual(final_image_formula(2, WEBSITE_HEADERS), '=IF(P2<>"";P2;O2)')

    def test_sheets_11_manual_publish_and_featured_columns_are_protected(self):
        before = [[None] * len(WEBSITE_HEADERS) for _ in range(150)]
        for index, row in enumerate(before):
            row[0] = index + 1
            row[4] = "Owner name" if index == 3 else ""
            row[7:11] = ["Category", "Audience", "Collection", index + 1]
            row[11:13] = [False, False]
            row[15] = "https://owner.example/custom.jpg" if index == 4 else ""
            row[19:21] = ["Owner note", "owner-slug"]
        after = [list(row) for row in before]
        assert_manual_preserved(WEBSITE_HEADERS, before, after)
        after[0][12] = True
        with self.assertRaisesRegex(PilotContractError, "MANUAL_COLUMNS_CHANGED"):
            assert_manual_preserved(WEBSITE_HEADERS, before, after)

    def test_sheets_12_write_target_allowlist_rejects_other_tabs_and_columns(self):
        validate_write_plan({AUTO_TAB: {"Tên SP", "sync_status"}, WEBSITE_TAB: {"kiot_price"}})
        with self.assertRaises(PilotContractError):
            validate_write_plan({"OTHER": {"sync_status"}})
        with self.assertRaises(PilotContractError):
            validate_write_plan({WEBSITE_TAB: {"publish"}})

    def test_sheets_13_partial_write_rollback_restores_formula_or_literal(self):
        applied = [
            CellUpdate(WEBSITE_TAB, 2, 2, "product_id", "new"),
            CellUpdate(WEBSITE_TAB, 2, 13, "kiot_price", 100),
        ]
        values = [[None] * len(WEBSITE_HEADERS)]
        formulas = [[None] * len(WEBSITE_HEADERS)]
        formulas[0][2] = "=OLD_FORMULA()"
        values[0][13] = 50
        rollback = build_rollback_updates(
            applied, values, formulas, first_sheet_row=2
        )
        self.assertEqual(rollback[0].value, "=OLD_FORMULA()")
        self.assertEqual(rollback[1].value, 50)


if __name__ == "__main__":
    unittest.main()
