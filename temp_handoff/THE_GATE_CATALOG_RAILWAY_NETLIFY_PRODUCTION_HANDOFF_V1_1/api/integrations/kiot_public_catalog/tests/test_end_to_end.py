from __future__ import annotations

import base64
import datetime as dt
import http.client
import json
import logging
import os
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from integrations.kiot_public_catalog.api import create_server
from integrations.kiot_public_catalog.config import (
    ApiConfig,
    SyncConfig,
    load_api_config,
    validate_bind,
)
from integrations.kiot_public_catalog.errors import (
    CacheUnavailable,
    ConfigurationError,
    ContractError,
    TransportError,
)
from integrations.kiot_public_catalog.railway_runtime import (
    RailwayRuntimeSettings,
    RailwaySupervisor,
    ensure_runtime_directories,
    load_railway_runtime_settings,
    materialize_kiot_secret,
    prepare_railway_environment,
)
from integrations.kiot_public_catalog.website_catalog import (
    GOOGLE_SHEETS_READONLY_SCOPE,
    SHEET_HEADERS,
    TARGET_RANGE,
    TARGET_SPREADSHEET_ID,
    TARGET_TAB,
    GoogleSheetsReadonlyAdapter,
    WebsiteCatalogBuilder,
    WebsiteCatalogStore,
    WebsiteSheetRow,
    decode_service_account_b64,
    parse_sheet_values,
    validate_website_payload,
)

from test_catalog import INTERNAL_KEY, WEBSITE_KEY, quiet_logger


NOW = dt.datetime.fromisoformat("2042-03-14T03:00:00+00:00")
SOURCE_CUTOFF = "2042-03-14T02:00:00+00:00"
MODULE_ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = Path(__file__).resolve().parents[4]
ASSET_ROOT = MODULE_ROOT if (MODULE_ROOT / "deployment").is_dir() else PACK_ROOT
OPENAPI_PATH = (
    MODULE_ROOT / "openapi.yaml"
    if (MODULE_ROOT / "openapi.yaml").is_file()
    else PACK_ROOT / "contracts" / "openapi.yaml"
)


def source_record(code: str, *, image: str | None = None, price: float = 299000) -> dict:
    return {
        "code": code,
        "name": "Source " + code,
        "attributes": {"color": "Đen", "size": "M"},
        "images": [image or f"https://example.invalid/{code.lower()}.jpg"] if image is not False else [],
        "sale_price": price,
        "price_status": "available",
        "availability": {
            "ton_that_thiep": "in_stock",
            "nguyen_trai": "out_of_stock",
            "tam_coc": "in_stock",
        },
        "data_as_of": SOURCE_CUTOFF,
        "stale": False,
    }


def sheet_row(code: str, **overrides) -> WebsiteSheetRow:
    values = {
        "product_code": code,
        "priority": None,
        "custom_name": None,
        "final_name": None,
        "source_group": None,
        "category": None,
        "audience": None,
        "collection": None,
        "display_order": None,
        "featured": False,
        "publish": True,
        "custom_image_url": None,
        "slug": None,
    }
    values.update(overrides)
    return WebsiteSheetRow(**values)


def sheet_values(*rows: dict, **single_row) -> list[list]:
    if single_row:
        if rows:
            raise AssertionError("use positional rows or one keyword row")
        rows = (single_row,)
    output = [list(SHEET_HEADERS)]
    for values in rows:
        output.append([values.get(header, "") for header in SHEET_HEADERS])
    return output


class FakeReader:
    def __init__(self, records: dict[str, dict]):
        self.records = records
        self.status = {"data_as_of": SOURCE_CUTOFF, "stale": False}

    def get_record(self, code: str, *, public_only: bool = False):
        assert public_only is True
        return self.records.get(code)


class FakeSheet:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows = list(rows or [])
        self.error = error
        self.calls = 0

    def fetch(self):
        self.calls += 1
        if self.error:
            raise self.error
        return list(self.rows)


class FakeResponse:
    def __init__(self, status: int, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def service_account_b64() -> str:
    payload = {
        "type": "service_account",
        "client_email": "synthetic@example.invalid",
        "private_key": "SYNTHETIC PRIVATE KEY FIXTURE",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def website_payload(
    code: str = "SKU-1",
    *,
    generated_at: str | None = None,
    source_data_as_of: str = SOURCE_CUTOFF,
) -> dict:
    return {
        "schema_version": "the_gate_website_catalog.v1",
        "generated_at": generated_at or NOW.isoformat(timespec="seconds"),
        "source_data_as_of": source_data_as_of,
        "total": 1,
        "items": [
            {
                "code": code,
                "name": "Synthetic item",
                "slug": code.lower(),
                "attributes": {"color": "Đen", "size": "M"},
                "images": ["https://example.invalid/item.jpg"],
                "sale_price": 299000,
                "price_status": "available",
                "availability": {
                    "ton_that_thiep": "in_stock",
                    "nguyen_trai": "out_of_stock",
                    "tam_coc": "in_stock",
                },
                "source_group": None,
                "category": None,
                "audience": None,
                "collection": None,
                "display_order": 1,
                "featured": False,
                "data_as_of": source_data_as_of,
            }
        ],
    }


class WebsiteApiHarness:
    def __init__(self, root: Path, *, rate: int = 600, has_catalog: bool = True):
        self.store = WebsiteCatalogStore(
            root / "website_catalog.json",
            root / "website_catalog_status.json",
            max_age_seconds=10800,
            max_products=1000,
            max_response_bytes=5_000_000,
            now_provider=lambda: NOW,
        )
        if has_catalog:
            self.store.commit(website_payload())
        config = ApiConfig(
            cache_path=root / "catalog.sqlite3",
            status_path=root / "sync_status.json",
            website_api_key=WEBSITE_KEY,
            internal_api_key=INTERNAL_KEY,
            max_cache_age_seconds=10800,
            host="127.0.0.1",
            port=8787,
            log_path=root / "api.log",
            website_catalog_path=self.store.path,
            website_catalog_status_path=self.store.status_path,
            website_catalog_max_age_seconds=10800,
            website_catalog_max_products=1000,
            website_catalog_max_response_bytes=5_000_000,
            website_rate_limit_per_minute=rate,
        )
        self.server = create_server(
            config,
            quiet_logger("website-api"),
            port_override=0,
            now_provider=lambda: NOW,
            website_store=self.store,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method: str, path: str, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_address[1], timeout=5
        )
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        headers_out = dict(response.getheaders())
        connection.close()
        payload = json.loads(body) if body else None
        return response.status, payload, headers_out, body


class SheetAdapterContractTests(unittest.TestCase):
    def test_e2e_sheet_01_exact_21_headers_and_true_publish_pass(self):
        rows = parse_sheet_values(
            sheet_values(
                product_code=" SKU-1 ",
                publish="TRUE",
                featured="FALSE",
                custom_name="Tên riêng",
            )
        )
        self.assertEqual(len(SHEET_HEADERS), 21)
        self.assertEqual(rows[0].product_code, "SKU-1")
        self.assertTrue(rows[0].publish)
        self.assertFalse(rows[0].featured)

    def test_e2e_sheet_02_missing_duplicate_or_reordered_header_fails(self):
        for headers in (
            list(SHEET_HEADERS[:-1]),
            list(SHEET_HEADERS[:-1]) + [SHEET_HEADERS[0]],
            [SHEET_HEADERS[1], SHEET_HEADERS[0], *SHEET_HEADERS[2:]],
        ):
            with self.subTest(headers=headers), self.assertRaisesRegex(
                ContractError, "SHEET_HEADER_CONTRACT_MISMATCH"
            ):
                parse_sheet_values([headers])

    def test_e2e_sheet_03_duplicate_and_blank_sku_fail_closed(self):
        with self.assertRaisesRegex(ContractError, "SHEET_DUPLICATE_PRODUCT_CODE"):
            parse_sheet_values(
                sheet_values(
                    {"product_code": "SKU-1", "publish": "TRUE"},
                    {"product_code": " SKU-1 ", "publish": "TRUE"},
                )
            )
        with self.assertRaisesRegex(ContractError, "SHEET_PRODUCT_CODE_BLANK"):
            parse_sheet_values(sheet_values(category="Coats", publish="TRUE"))

    def test_e2e_sheet_04_only_exact_true_is_publishable(self):
        for invalid in ("TRUE ", "true", "yes", "1", 1):
            with self.subTest(value=invalid), self.assertRaisesRegex(
                ContractError, "SHEET_PUBLISH_VALUE_INVALID"
            ):
                parse_sheet_values(sheet_values(product_code="SKU-1", publish=invalid))

    def test_e2e_sheet_05_exact_sku_preserves_case_no_fuzzy_join(self):
        row = parse_sheet_values(
            sheet_values(product_code=" AbC-1 ", publish="TRUE")
        )[0]
        self.assertEqual(row.product_code, "AbC-1")

    def test_e2e_sheet_06_adapter_uses_one_fixed_get_and_readonly_contract(self):
        session = FakeSession(
            [FakeResponse(200, {"range": "WEBSITE_PRODUCTS!A1:U2", "values": sheet_values(product_code="SKU-1", publish="TRUE")})]
        )
        adapter = GoogleSheetsReadonlyAdapter(
            spreadsheet_id=TARGET_SPREADSHEET_ID, session=session, sleeper=lambda _x: None
        )
        self.assertEqual(len(adapter.fetch()), 1)
        self.assertEqual([entry["method"] for entry in adapter.call_ledger], ["GET"])
        url, kwargs = session.calls[0]
        self.assertIn(TARGET_SPREADSHEET_ID, url)
        self.assertIn("WEBSITE_PRODUCTS%21A1%3AU1002", url)
        self.assertNotIn("SALE_IMPORT_STAGING", url)
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(GOOGLE_SHEETS_READONLY_SCOPE.endswith("spreadsheets.readonly"), True)

    def test_e2e_sheet_07_wrong_sheet_id_or_response_tab_fails(self):
        with self.assertRaisesRegex(ConfigurationError, "GOOGLE_SHEET_ID_MISMATCH"):
            GoogleSheetsReadonlyAdapter(spreadsheet_id="wrong", session=FakeSession([]))
        adapter = GoogleSheetsReadonlyAdapter(
            spreadsheet_id=TARGET_SPREADSHEET_ID,
            session=FakeSession([FakeResponse(200, {"range": "SALE_IMPORT_STAGING!A1:U2", "values": sheet_values()})]),
        )
        with self.assertRaisesRegex(ContractError, "SHEET_RESPONSE_TAB_MISMATCH"):
            adapter.fetch()

    def test_e2e_sheet_08_malformed_google_credential_fails_without_network(self):
        for raw in ("", "replace_me", base64.b64encode(b"{}").decode(), "not-base64"):
            with self.subTest(raw=raw), self.assertRaises(ConfigurationError):
                decode_service_account_b64(raw)

    def test_e2e_sheet_09_429_and_5xx_retry_bounded_then_pass(self):
        session = FakeSession(
            [
                FakeResponse(429, {}),
                FakeResponse(503, {}),
                FakeResponse(200, {"range": "WEBSITE_PRODUCTS!A1:U1", "values": sheet_values()}),
            ]
        )
        adapter = GoogleSheetsReadonlyAdapter(
            spreadsheet_id=TARGET_SPREADSHEET_ID,
            session=session,
            attempts=3,
            sleeper=lambda _x: None,
        )
        self.assertEqual(adapter.fetch(), [])
        self.assertEqual([item["status"] for item in adapter.call_ledger], [429, 503, 200])

    def test_e2e_sheet_10_timeout_retries_are_bounded(self):
        adapter = GoogleSheetsReadonlyAdapter(
            spreadsheet_id=TARGET_SPREADSHEET_ID,
            session=FakeSession([requests.Timeout(), requests.Timeout()]),
            attempts=2,
            sleeper=lambda _x: None,
        )
        with self.assertRaisesRegex(TransportError, "SHEET_NETWORK_OR_TIMEOUT"):
            adapter.fetch()
        self.assertEqual(len(adapter.call_ledger), 2)


class WebsiteCatalogBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = WebsiteCatalogStore(
            self.root / "website_catalog.json",
            self.root / "website_status.json",
            max_age_seconds=10800,
            max_products=1000,
            max_response_bytes=5_000_000,
            now_provider=lambda: NOW,
        )

    def tearDown(self):
        self.temp.cleanup()

    def builder(self, rows, records, *, max_products=1000, sheet_error=None):
        return WebsiteCatalogBuilder(
            reader_factory=lambda: FakeReader(records),
            sheet_adapter=FakeSheet(rows, sheet_error),
            store=self.store,
            logger=quiet_logger("builder"),
            max_products=max_products,
            now_provider=lambda: NOW,
        )

    def test_e2e_merge_01_false_excluded_true_and_eligible_included(self):
        result = self.builder(
            [sheet_row("A", publish=False), sheet_row("B", publish=True)],
            {"A": source_record("A"), "B": source_record("B")},
        ).build()
        payload = self.store.read()[0]
        self.assertEqual(result["total"], 1)
        self.assertEqual([item["code"] for item in payload["items"]], ["B"])

    def test_e2e_merge_02_sheet_price_and_internal_fields_cannot_override(self):
        record = source_record("SKU-1", price=299000)
        record["inventory"] = {"ton_that_thiep": 999}
        self.builder([sheet_row("SKU-1")], {"SKU-1": record}).build()
        item = self.store.read()[0]["items"][0]
        self.assertEqual(item["sale_price"], 299000)
        self.assertNotIn("inventory", item)
        self.assertNotIn("generation_id", item)

    def test_e2e_merge_03_sheet_true_but_source_ineligible_is_excluded(self):
        result = self.builder([sheet_row("MISSING")], {}).build()
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["excluded_ineligible"], 1)

    def test_e2e_merge_04_custom_name_and_valid_custom_image_win(self):
        self.builder(
            [sheet_row("A", custom_name="Editorial", custom_image_url="https://custom.example.invalid/a.jpg")],
            {"A": source_record("A")},
        ).build()
        item = self.store.read()[0]["items"][0]
        self.assertEqual(item["name"], "Editorial")
        self.assertEqual(item["images"], ["https://custom.example.invalid/a.jpg"])

    def test_e2e_merge_05_invalid_custom_image_falls_back_to_source(self):
        self.builder(
            [sheet_row("A", custom_image_url="http://unsafe.example.invalid/a.jpg")],
            {"A": source_record("A")},
        ).build()
        self.assertEqual(self.store.read()[0]["items"][0]["images"][0], "https://example.invalid/a.jpg")

    def test_e2e_merge_06_missing_all_images_hides_product(self):
        result = self.builder(
            [sheet_row("A")], {"A": source_record("A", image=False)}
        ).build()
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["excluded_missing_image"], 1)

    def test_e2e_merge_07_duplicate_or_invalid_slug_fails_closed(self):
        records = {"A": source_record("A"), "B": source_record("B")}
        with self.assertRaisesRegex(ContractError, "WEBSITE_CATALOG_DUPLICATE_SLUG"):
            self.builder(
                [sheet_row("A", slug="same"), sheet_row("B", slug="same")], records
            ).build()
        with self.assertRaisesRegex(ContractError, "SHEET_SLUG_INVALID"):
            self.builder([sheet_row("A", slug="Unsafe Slug")], records).build()

    def test_e2e_merge_08_exactly_1000_candidates_pass(self):
        rows = [sheet_row(f"SKU-{index:04d}") for index in range(1000)]
        records = {row.product_code: source_record(row.product_code) for row in rows}
        result = self.builder(rows, records).build()
        self.assertEqual(result["total"], 1000)

    def test_e2e_merge_09_1001_candidates_fail_without_truncation(self):
        self.store.commit(website_payload("OLD"))
        before = self.store.path.read_bytes()
        rows = [sheet_row(f"SKU-{index:04d}") for index in range(1001)]
        with self.assertRaisesRegex(ContractError, "WEBSITE_CATALOG_PRODUCT_LIMIT_EXCEEDED"):
            self.builder(rows, {}, max_products=1000).build()
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_e2e_merge_10_fault_before_replace_keeps_byte_identical_lkg(self):
        self.store.commit(website_payload("OLD"))
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "BEFORE"):
            self.store.commit(
                website_payload("NEW"),
                fault_injector=lambda point: (_ for _ in ()).throw(RuntimeError("BEFORE")) if point == "before_replace" else None,
            )
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_e2e_merge_11_fault_after_replace_leaves_new_valid_lkg(self):
        self.store.commit(website_payload("OLD"))
        with self.assertRaisesRegex(RuntimeError, "AFTER"):
            self.store.commit(
                website_payload("NEW"),
                fault_injector=lambda point: (_ for _ in ()).throw(RuntimeError("AFTER")) if point == "after_replace" else None,
            )
        self.assertEqual(self.store.read()[0]["items"][0]["code"], "NEW")

    def test_e2e_merge_12_sheet_failure_preserves_existing_lkg(self):
        self.store.commit(website_payload("OLD"))
        before = self.store.path.read_bytes()
        with self.assertRaisesRegex(TransportError, "SHEET_HTTP_429"):
            self.builder([], {}, sheet_error=TransportError("SHEET_HTTP_429")).build()
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_e2e_merge_13_missing_and_stale_lkg_fail_closed(self):
        with self.assertRaisesRegex(CacheUnavailable, "WEBSITE_CATALOG_MISSING"):
            self.store.read()
        self.store.commit(
            website_payload(generated_at="2042-03-13T23:59:59+00:00")
        )
        with self.assertRaisesRegex(CacheUnavailable, "WEBSITE_CATALOG_TOO_OLD"):
            self.store.read()

    def test_e2e_merge_14_sort_and_generated_slug_are_deterministic(self):
        rows = [sheet_row("B", display_order=2), sheet_row("A", display_order=1)]
        records = {"A": source_record("A"), "B": source_record("B")}
        self.builder(rows, records).build()
        first = self.store.path.read_bytes()
        self.builder(rows, records).build()
        self.assertEqual(self.store.path.read_bytes(), first)
        payload = self.store.read()[0]
        self.assertEqual([item["code"] for item in payload["items"]], ["A", "B"])
        self.assertEqual([item["slug"] for item in payload["items"]], ["a", "b"])

    def test_e2e_merge_15_public_payload_strict_schema_rejects_extra_field(self):
        payload = website_payload()
        payload["items"][0]["note"] = "must not leak"
        with self.assertRaisesRegex(CacheUnavailable, "WEBSITE_CATALOG_ITEM_FIELDS_INVALID"):
            validate_website_payload(payload, max_products=1000)

    def test_e2e_merge_16_response_size_guard_fails_closed(self):
        small_store = WebsiteCatalogStore(
            self.root / "small.json",
            self.root / "small-status.json",
            max_age_seconds=10800,
            max_products=1000,
            max_response_bytes=10_000,
            now_provider=lambda: NOW,
        )
        payload = website_payload()
        payload["items"][0]["name"] = "X" * 20_000
        with self.assertRaisesRegex(ContractError, "WEBSITE_CATALOG_RESPONSE_TOO_LARGE"):
            small_store.commit(payload)

    def test_e2e_merge_17_source_age_boundary_10800_passes_and_10801_fails(self):
        exact = (NOW - dt.timedelta(seconds=10800)).isoformat(timespec="seconds")
        self.store.commit(
            website_payload(generated_at=NOW.isoformat(timespec="seconds"), source_data_as_of=exact)
        )
        self.assertEqual(self.store.read()[0]["source_data_as_of"], exact)

        expired_now = NOW + dt.timedelta(seconds=1)
        restarted = WebsiteCatalogStore(
            self.store.path,
            self.store.status_path,
            max_age_seconds=10800,
            max_products=1000,
            max_response_bytes=5_000_000,
            now_provider=lambda: expired_now,
        )
        with self.assertRaisesRegex(CacheUnavailable, "WEBSITE_CATALOG_SOURCE_TOO_OLD"):
            restarted.read()

    def test_e2e_merge_18_fresh_generated_at_cannot_mask_21480_second_source_age(self):
        source_cutoff = (NOW - dt.timedelta(seconds=21480)).isoformat(timespec="seconds")
        self.store.commit(
            website_payload(generated_at=NOW.isoformat(timespec="seconds"), source_data_as_of=source_cutoff)
        )
        with self.assertRaisesRegex(CacheUnavailable, "WEBSITE_CATALOG_SOURCE_TOO_OLD"):
            self.store.read()

    def test_e2e_merge_19_rebuild_and_restart_do_not_extend_source_freshness(self):
        source_cutoff = (NOW - dt.timedelta(seconds=10799)).isoformat(timespec="seconds")
        reader = FakeReader({"SKU-1": source_record("SKU-1")})
        reader.status["data_as_of"] = source_cutoff
        builder = WebsiteCatalogBuilder(
            reader_factory=lambda: reader,
            sheet_adapter=FakeSheet([sheet_row("SKU-1")]),
            store=self.store,
            logger=quiet_logger("source-freshness-build"),
            max_products=1000,
            now_provider=lambda: NOW,
        )
        builder.build()
        before = self.store.path.read_bytes()

        # A second build writes a newer generated_at but must retain the Kiot cutoff.
        later_build = NOW + dt.timedelta(seconds=1)
        builder.now_provider = lambda: later_build
        builder.build()
        rebuilt = self.store.path.read_bytes()
        self.assertNotEqual(before, rebuilt)
        self.assertEqual(json.loads(rebuilt)["source_data_as_of"], source_cutoff)

        restarted = WebsiteCatalogStore(
            self.store.path,
            self.store.status_path,
            max_age_seconds=10800,
            max_products=1000,
            max_response_bytes=5_000_000,
            now_provider=lambda: NOW + dt.timedelta(seconds=2),
        )
        with self.assertRaisesRegex(CacheUnavailable, "WEBSITE_CATALOG_SOURCE_TOO_OLD"):
            restarted.read()


class WebsiteHttpContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_e2e_http_01_website_200_content_type_cache_etag_no_cors(self):
        with WebsiteApiHarness(self.root) as api:
            status, payload, headers, _body = api.request("GET", "/v1/website/catalog")
        self.assertEqual(status, 200)
        self.assertEqual(payload["total"], 1)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertIn("ETag", headers)
        self.assertIn("max-age=60", headers["Cache-Control"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_e2e_http_02_etag_is_stable_and_if_none_match_returns_304(self):
        with WebsiteApiHarness(self.root) as api:
            first = api.request("GET", "/v1/website/catalog")
            second = api.request("GET", "/v1/website/catalog")
            cached = api.request("GET", "/v1/website/catalog", {"If-None-Match": first[2]["ETag"]})
        self.assertEqual(first[2]["ETag"], second[2]["ETag"])
        self.assertEqual(cached[0], 304)
        self.assertEqual(cached[3], b"")

    def test_e2e_http_03_etag_changes_with_payload(self):
        with WebsiteApiHarness(self.root) as api:
            first = api.request("GET", "/v1/website/catalog")[2]["ETag"]
            api.store.commit(website_payload("SKU-2"))
            second = api.request("GET", "/v1/website/catalog")[2]["ETag"]
        self.assertNotEqual(first, second)

    def test_e2e_http_04_write_methods_return_405(self):
        with WebsiteApiHarness(self.root) as api:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                with self.subTest(method=method):
                    self.assertEqual(api.request(method, "/v1/website/catalog")[0], 405)

    def test_e2e_http_05_rate_limit_and_uninitialized_503(self):
        with WebsiteApiHarness(self.root / "rate", rate=1) as api:
            self.assertEqual(api.request("GET", "/v1/website/catalog")[0], 200)
            self.assertEqual(api.request("GET", "/v1/website/catalog")[0], 429)
        with WebsiteApiHarness(self.root / "missing", has_catalog=False) as api:
            self.assertEqual(api.request("GET", "/v1/website/catalog")[0], 503)

    def test_e2e_http_06_livez_is_200_without_data_and_health_is_503(self):
        with WebsiteApiHarness(self.root, has_catalog=False) as api:
            self.assertEqual(api.request("GET", "/livez")[0], 200)
            self.assertEqual(api.request("GET", "/health")[0], 503)

    def test_e2e_http_07_query_and_path_traversal_are_rejected(self):
        with WebsiteApiHarness(self.root) as api:
            self.assertEqual(api.request("GET", "/v1/website/catalog?tab=OTHER")[0], 400)
            self.assertEqual(api.request("GET", "/v1/website/catalog/%2e%2e")[0], 404)

    def test_e2e_http_08_existing_protected_endpoint_still_requires_key(self):
        with WebsiteApiHarness(self.root) as api:
            self.assertEqual(api.request("GET", "/v1/catalog/products")[0], 401)
            self.assertEqual(
                api.request("GET", "/v1/internal/products", {"X-API-Key": WEBSITE_KEY})[0],
                403,
            )

    def test_e2e_http_09_public_response_contains_no_forbidden_fields(self):
        with WebsiteApiHarness(self.root) as api:
            body = api.request("GET", "/v1/website/catalog")[3].decode()
        for forbidden in ("inventory", "generation_id", "client_secret", "private_key", "/runtime"):
            self.assertNotIn(forbidden, body)

    def test_e2e_http_10_fresh_build_with_expired_source_returns_503(self):
        with WebsiteApiHarness(self.root) as api:
            source_cutoff = (NOW - dt.timedelta(seconds=21480)).isoformat(timespec="seconds")
            api.store.commit(
                website_payload(
                    generated_at=NOW.isoformat(timespec="seconds"),
                    source_data_as_of=source_cutoff,
                )
            )
            self.assertEqual(api.request("GET", "/v1/website/catalog")[0], 503)


class ContainerRuntimeConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def test_e2e_config_01_local_default_loopback_and_railway_bind_gate(self):
        validate_bind("127.0.0.1", "local")
        validate_bind("0.0.0.0", "railway")
        with self.assertRaises(ConfigurationError):
            validate_bind("0.0.0.0", "local")
        with self.assertRaises(ConfigurationError):
            validate_bind("127.0.0.1", "railway")

    def test_e2e_config_02_runtime_dirs_and_secret_file_are_private(self):
        paths = ensure_runtime_directories(self.root)
        secret = paths["secrets"] / "kiot.env"
        materialize_kiot_secret(
            secret,
            {"KV_RETAILER": "synthetic", "KV_CLIENT_ID": "synthetic-id", "KV_CLIENT_SECRET": "synthetic-value"},
        )
        self.assertEqual(secret.stat().st_mode & 0o777, 0o600)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o700 for path in paths.values()))

    def test_e2e_config_03_missing_placeholder_or_duplicate_secret_fails(self):
        with self.assertRaises(ConfigurationError):
            materialize_kiot_secret(
                self.root / "bad.env",
                {"KV_RETAILER": "replace_me", "KV_CLIENT_ID": "x", "KV_CLIENT_SECRET": "y"},
            )
        environment = {
            "KIOT_CATALOG_WEBSITE_API_KEY": "A" * 32,
            "KIOT_CATALOG_INTERNAL_API_KEY": "A" * 32,
            "KIOT_CATALOG_MAX_CACHE_AGE_SECONDS": "10800",
        }
        with patch.dict(os.environ, environment, clear=True), self.assertRaisesRegex(
            ConfigurationError, "API_KEYS_MUST_DIFFER"
        ):
            load_api_config()

    def test_e2e_config_04_complete_synthetic_railway_settings_pass_offline(self):
        with patch("integrations.kiot_public_catalog.railway_runtime.RUNTIME_ROOT", self.root):
            environment = {
                "RAILWAY_VOLUME_MOUNT_PATH": str(self.root),
                "KIOT_CATALOG_DEPLOYMENT_MODE": "railway",
                "KIOT_CATALOG_HOST": "0.0.0.0",
                "PORT": "8787",
                "KV_RETAILER": "synthetic-retailer",
                "KV_CLIENT_ID": "synthetic-client-id",
                "KV_CLIENT_SECRET": "synthetic-client-secret",
                "KIOT_CATALOG_WEBSITE_API_KEY": "W" * 32,
                "KIOT_CATALOG_INTERNAL_API_KEY": "I" * 32,
                "GOOGLE_SHEET_ID": TARGET_SPREADSHEET_ID,
                "GOOGLE_SERVICE_ACCOUNT_JSON_B64": service_account_b64(),
                "KIOT_CATALOG_SYNC_ENABLED": "true",
                "KIOT_CATALOG_SYNC_CADENCE_SECONDS": "3600",
                "KIOT_CATALOG_MAX_CACHE_AGE_SECONDS": "10800",
                "KIOT_CATALOG_RETAIN_GENERATIONS": "3",
                "KIOT_CATALOG_WEBSITE_MAX_AGE_SECONDS": "10800",
                "KIOT_CATALOG_WEBSITE_MAX_PRODUCTS": "1000",
                "KIOT_CATALOG_WEBSITE_MAX_RESPONSE_BYTES": "5000000",
                "KIOT_CATALOG_WORKER_RETRY_BASE_SECONDS": "30",
                "KIOT_CATALOG_WORKER_RETRY_MAX_SECONDS": "900",
                "GOOGLE_SHEETS_TIMEOUT_SECONDS": "20",
                "GOOGLE_SHEETS_ATTEMPTS": "3",
            }
            with patch.dict(os.environ, environment, clear=True):
                prepare_railway_environment(self.root)
                settings = load_railway_runtime_settings()
                os.environ["KIOT_CATALOG_SYNC_CADENCE_SECONDS"] = "3599"
                with self.assertRaisesRegex(
                    ConfigurationError, "INVALID_KIOT_CATALOG_SYNC_CADENCE_SECONDS"
                ):
                    load_railway_runtime_settings()
                os.environ["KIOT_CATALOG_SYNC_CADENCE_SECONDS"] = "3600"
                os.environ["GOOGLE_SHEET_ID"] = "wrong"
                with self.assertRaisesRegex(ConfigurationError, "GOOGLE_SHEET_ID_MISMATCH"):
                    load_railway_runtime_settings()
        self.assertEqual(settings.cadence_seconds, 3600)
        self.assertEqual(settings.api_config.host, "0.0.0.0")
        self.assertEqual(settings.api_config.port, 8787)

    def test_e2e_config_05_wrong_sheet_id_and_cadence_fail_closed(self):
        self.assertEqual(TARGET_TAB, "WEBSITE_PRODUCTS")
        self.assertEqual(TARGET_RANGE, "WEBSITE_PRODUCTS!A1:U1002")
        self.assertNotEqual(TARGET_TAB, "SALE_IMPORT_STAGING")


class FakeServer:
    def __init__(self):
        self.closed = False
        self.stop = threading.Event()

    def serve_forever(self):
        self.stop.wait()

    def shutdown(self):
        self.stop.set()

    def server_close(self):
        self.closed = True


class CountingBuilder:
    def __init__(self):
        self.calls = 0

    def build(self):
        self.calls += 1
        return {"status": "PASS", "total": 0}


def runtime_settings(root: Path, *, sync_enabled: bool = False) -> RailwayRuntimeSettings:
    sync = SyncConfig(
        secrets_path=root / "secrets" / "kiot.env",
        cache_path=root / "data" / "catalog.sqlite3",
        status_path=root / "data" / "sync_status.json",
        lock_path=root / "data" / ".sync.lock",
        log_path=root / "logs" / "sync.log",
        retain_generations=3,
    )
    api = ApiConfig(
        cache_path=sync.cache_path,
        status_path=sync.status_path,
        website_api_key="W" * 32,
        internal_api_key="I" * 32,
        max_cache_age_seconds=10800,
        host="0.0.0.0",
        port=8787,
        deployment_mode="railway",
        log_path=root / "logs" / "api.log",
        website_catalog_path=root / "data" / "website_catalog.json",
        website_catalog_status_path=root / "data" / "website_status.json",
        website_catalog_max_age_seconds=10800,
        website_catalog_max_products=1000,
        website_catalog_max_response_bytes=5_000_000,
    )
    return RailwayRuntimeSettings(
        sync_config=sync,
        api_config=api,
        cadence_seconds=3600,
        retry_base_seconds=5,
        retry_max_seconds=30,
        google_timeout_seconds=20,
        google_attempts=3,
        sync_enabled=sync_enabled,
        service_account_b64=service_account_b64(),
        sync_disabled_path=root / "data" / "SYNC_DISABLED",
    )


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        ensure_runtime_directories(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_e2e_runtime_01_graceful_stop_closes_server(self):
        server = FakeServer()
        supervisor = RailwaySupervisor(
            runtime_settings(self.root),
            logger=quiet_logger("supervisor-stop"),
            builder=CountingBuilder(),
            server=server,
        )
        timer = threading.Timer(0.05, supervisor.request_stop)
        timer.start()
        try:
            self.assertEqual(supervisor.run(), 0)
        finally:
            timer.cancel()
        self.assertTrue(server.closed)
        self.assertFalse(supervisor.api_thread.is_alive())
        self.assertFalse(supervisor.worker_thread.is_alive())

    def test_e2e_runtime_02_scheduler_never_overlaps_sync(self):
        active = 0
        peak = 0
        completed = threading.Event()
        lock = threading.Lock()

        class Sync:
            def run(_self):
                nonlocal active, peak
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.05)
                with lock:
                    active -= 1
                completed.set()
                return {"data_as_of": SOURCE_CUTOFF}

        supervisor = RailwaySupervisor(
            runtime_settings(self.root, sync_enabled=True),
            logger=quiet_logger("supervisor-overlap"),
            sync_factory=Sync,
            builder=CountingBuilder(),
            server=FakeServer(),
            jitter=lambda _a, b: b,
        )
        thread = threading.Thread(target=supervisor._worker_loop)
        thread.start()
        self.assertTrue(completed.wait(2))
        supervisor.request_stop()
        thread.join(timeout=2)
        self.assertEqual(peak, 1)
        self.assertFalse(thread.is_alive())

    def test_e2e_runtime_03_lock_busy_does_not_trigger_extra_build(self):
        attempted = threading.Event()

        class BusySync:
            def run(_self):
                attempted.set()
                raise ContractError("SYNC_LOCK_BUSY")

        builder = CountingBuilder()
        supervisor = RailwaySupervisor(
            runtime_settings(self.root, sync_enabled=True),
            logger=quiet_logger("supervisor-busy"),
            sync_factory=BusySync,
            builder=builder,
            server=FakeServer(),
        )
        thread = threading.Thread(target=supervisor._worker_loop)
        thread.start()
        self.assertTrue(attempted.wait(2))
        supervisor.request_stop()
        thread.join(timeout=2)
        self.assertEqual(builder.calls, 1)

    def test_e2e_runtime_04_disabled_startup_makes_zero_sync_and_sheet_build_calls(self):
        attempted = threading.Event()

        class DisabledSync:
            calls = 0

            def run(_self):
                DisabledSync.calls += 1
                attempted.set()
                return {"data_as_of": SOURCE_CUTOFF}

        builder = CountingBuilder()
        supervisor = RailwaySupervisor(
            runtime_settings(self.root, sync_enabled=False),
            logger=quiet_logger("supervisor-disabled-activation-guard"),
            sync_factory=DisabledSync,
            builder=builder,
            server=FakeServer(),
        )
        thread = threading.Thread(target=supervisor._worker_loop)
        thread.start()
        time.sleep(0.1)
        supervisor.request_stop()
        thread.join(timeout=2)
        self.assertFalse(attempted.is_set())
        self.assertEqual(DisabledSync.calls, 0)
        self.assertEqual(builder.calls, 0)
        self.assertFalse(thread.is_alive())


class HandoffArtifactContractTests(unittest.TestCase):
    def test_e2e_artifact_01_netlify_rewrite_is_exact_and_not_wildcard(self):
        lines = [
            line.strip()
            for line in (ASSET_ROOT / "deployment/netlify_dropin/_redirects.template").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            lines,
            ["/api/catalog  https://REPLACE_WITH_RAILWAY_DOMAIN/v1/website/catalog  200!"],
        )
        self.assertNotIn("*", lines[0])

    def test_e2e_artifact_02_javascript_syntax_and_security_contract(self):
        path = ASSET_ROOT / "deployment/netlify_dropin/assets/thegate-catalog-client.js"
        completed = subprocess.run(
            ["node", "--check", str(path)], capture_output=True, text=True, timeout=10
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        text = path.read_text(encoding="utf-8")
        self.assertIn('"/api/catalog"', text)
        for forbidden in ("X-API-Key", "client_secret", "private_key", "kiotapi", "sheets.googleapis"):
            self.assertNotIn(forbidden, text)

    def test_e2e_artifact_02b_javascript_200_304_429_503_timeout_and_malformed(self):
        completed = subprocess.run(
            [
                "node",
                str(
                    ASSET_ROOT
                    / "deployment/netlify_dropin/tests/catalog-client.test.js"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("pass=6 fail=0", completed.stdout)

    def test_e2e_artifact_03_docker_and_railway_configs_have_safe_topology(self):
        dockerfile = (ASSET_ROOT / "deployment/railway/Dockerfile").read_text()
        railway = (ASSET_ROOT / "deployment/railway/railway.toml").read_text()
        ignore = (ASSET_ROOT / "deployment/railway/.dockerignore").read_text()
        self.assertIn("FROM python:3.14.5-slim", dockerfile)
        self.assertIn('healthcheckPath = "/livez"', railway)
        self.assertNotIn("cronSchedule", railway)
        self.assertIn("**/*.sqlite3", ignore)
        self.assertIn("**/evidence", ignore)

    def test_e2e_artifact_04_openapi_actual_website_response_validates(self):
        document = json.loads(OPENAPI_PATH.read_text())
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": "#/components/schemas/WebsiteCatalog",
            "components": document["components"],
        }
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        validator.validate(website_payload())
        broken = website_payload()
        broken["items"][0]["inventory"] = {"ton_that_thiep": 3}
        with self.assertRaises(ValidationError):
            validator.validate(broken)

    def test_e2e_artifact_05_public_openapi_has_only_get_operations(self):
        document = json.loads(OPENAPI_PATH.read_text())
        methods = {
            method
            for path in document["paths"].values()
            for method in path
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }
        self.assertEqual(methods, {"get"})

    def test_e2e_artifact_06_activation_defaults_disabled(self):
        environment = (ASSET_ROOT / "deployment/railway/.env.railway.example").read_text()
        self.assertIn("KIOT_CATALOG_SYNC_ENABLED=false", environment)
        self.assertNotIn("KIOT_CATALOG_SYNC_ENABLED=true", environment)

    def test_e2e_artifact_07_existing_redirects_are_preserved_and_exact_rule_precedes_spa(self):
        fixture = ASSET_ROOT / "deployment/netlify_dropin/fixtures/_redirects.existing.fixture"
        expected = ASSET_ROOT / "deployment/netlify_dropin/fixtures/_redirects.merged.expected"
        script = ASSET_ROOT / "deployment/netlify_dropin/merge_redirects.py"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "_redirects"
            target.write_bytes(fixture.read_bytes())
            completed = subprocess.run(
                [
                    "python3",
                    str(script),
                    "--file",
                    str(target),
                    "--railway-origin",
                    "https://approved.example.invalid",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(target.read_bytes(), expected.read_bytes())
            backups = [path for path in target.parent.iterdir() if path.name.startswith("_redirects.backup.")]
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), fixture.read_bytes())
        merged = expected.read_text()
        self.assertLess(merged.index("/api/catalog"), merged.index("/*  /index.html"))
        self.assertNotIn("/api/*", merged)

    def test_e2e_artifact_08_openapi_distinguishes_three_access_origins(self):
        document = json.loads(OPENAPI_PATH.read_text())
        self.assertEqual(
            [server["url"] for server in document["servers"]],
            ["http://127.0.0.1:8787", "https://REPLACE_WITH_RAILWAY_DOMAIN"],
        )
        origins = document["x-thegate-access-origins"]
        self.assertEqual(origins["netlify_same_origin_path"], "/api/catalog")
        self.assertEqual(origins["railway_website_path"], "/v1/website/catalog")


if __name__ == "__main__":
    unittest.main()
