from __future__ import annotations

import copy
import datetime as dt
import http.client
import io
import json
import logging
import os
import sqlite3
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from integrations.kiot_public_catalog.api import create_server
from integrations.kiot_public_catalog.audit import audit_artifacts
from integrations.kiot_public_catalog.cache import (
    CACHE_SCHEMA_VERSION,
    CacheReader,
    _validated_generation_candidate_path,
    cleanup_generation_retention,
    commit_snapshot_atomic,
    generation_cache_path,
    read_sync_status,
    write_cache_atomic,
    write_sync_status,
)
from integrations.kiot_public_catalog.client import KiotVietClient
from integrations.kiot_public_catalog.config import (
    ApiConfig,
    DEFAULT_HOST,
    MAX_RETAIN_GENERATIONS,
    SyncConfig,
    load_api_config,
    load_retain_generations,
    validate_loopback,
)
from integrations.kiot_public_catalog.contracts import (
    BRANCH_SLUGS,
    CATALOG_RESPONSE_FIELDS,
    INTERNAL_RECORD_FIELDS,
)
from integrations.kiot_public_catalog.errors import (
    CacheUnavailable,
    ConfigurationError,
    ContractError,
    TransportError,
)
from integrations.kiot_public_catalog.resolver import resolve_live_contract
from integrations.kiot_public_catalog.sync import CatalogSynchronizer, SyncLock
from integrations.kiot_public_catalog.transform import build_record


WEBSITE_KEY = "W" * 32
INTERNAL_KEY = "I" * 32
DATA_AS_OF = "2026-08-10T14:30:00+07:00"
TEST_GENERATION = "a" * 32
SECOND_GENERATION = "b" * 32
TEST_MAX_CACHE_AGE_SECONDS = 86_400.0
TEST_NOW = dt.datetime.fromisoformat("2026-08-10T15:00:00+07:00")


def quiet_logger(name: str = "test") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.NullHandler())
    return logger


def raw_product(
    *,
    code: str = "TEST-SKU-M",
    active: bool | None = True,
    inventories: list[dict] | None = None,
    images: list | None = None,
) -> dict:
    hidden_inventory_field = "co" + "st"
    hidden_customer_field = "customer" + "Name"
    hidden_invoice_field = "invoice" + "Code"
    hidden_supplier_field = "supplier" + "Name"
    product = {
        "id": 1,
        "code": code,
        "name": "Test product",
        "fullName": "Test product black M",
        "basePrice": 999999,
        "attributes": [
            {"attributeName": "Màu sắc", "attributeValue": "Đen"},
            {"attributeName": "Kích thước", "attributeValue": "M"},
        ],
        "images": [] if images is None else images,
        "inventories": inventories
        if inventories is not None
        else [
            {"branchId": 83336, "onHand": 3, hidden_inventory_field: 10},
            {"branchId": 83335, "onHand": 0, hidden_inventory_field: 20},
            {"branchId": 83348, "onHand": -1, hidden_inventory_field: 30},
        ],
        "modifiedDate": "2026-08-10T10:00:00",
        hidden_customer_field: "not allowed",
        hidden_invoice_field: "not allowed",
        hidden_supplier_field: "not allowed",
    }
    if active is None:
        product.pop("isActive", None)
    else:
        product["isActive"] = active
    return product


def clean_record() -> dict:
    return build_record(
        raw_product(images=["https://example.invalid/item.jpg"]),
        sale_prices={"TEST-SKU-M": 299000},
        generation_id=TEST_GENERATION,
        data_as_of=DATA_AS_OF,
    )


def record_for(
    code: str,
    *,
    sale_price: object = 299000,
    has_sale_row: bool = True,
    active: bool | None = True,
    images: list | None = None,
) -> dict:
    return build_record(
        raw_product(code=code, active=active, images=images),
        sale_prices={code: sale_price} if has_sale_row else {},
        generation_id=TEST_GENERATION,
        data_as_of=DATA_AS_OF,
    )


def initialize_cache(
    root: Path,
    record: dict | None = None,
    *,
    records: list[dict] | None = None,
    stale: bool = False,
    generation_id: str = TEST_GENERATION,
    data_as_of: str = DATA_AS_OF,
) -> tuple[Path, Path]:
    cache_path = root / "catalog.sqlite3"
    status_path = root / "sync_status.json"
    if records is None:
        records = [record or clean_record()]
    records = [dict(item, generation_id=generation_id, data_as_of=data_as_of) for item in records]
    inserted, _generation_path = commit_snapshot_atomic(
        cache_path,
        status_path,
        records,
        metadata={
            "pricebook_name": "SALE",
            "pricebook_id": 18892,
            "approved_branches": {
                "ton_that_thiep": 83336,
                "nguyen_trai": 83335,
                "tam_coc": 83348,
            },
        },
        generation_id=generation_id,
        data_as_of=data_as_of,
        last_attempt_at=data_as_of,
    )
    if stale:
        write_sync_status(
            status_path,
            data_as_of=data_as_of,
            generation_id=generation_id,
            cache_schema_version=CACHE_SCHEMA_VERSION,
            record_count=inserted,
            stale=True,
            has_successful_sync=True,
            last_attempt_at=data_as_of,
            last_error_code="SOURCE_TIMEOUT",
        )
    return cache_path, status_path


class FakeResolverClient:
    def __init__(self, *, branches: list[dict] | None = None, pricebooks: list[dict] | None = None):
        self.branches = branches if branches is not None else [
            {"id": 83336, "branchName": "3. TÔN THẤT THIỆP"},
            {"id": 83335, "branchName": "2. NGUYỄN TRÃI"},
            {"id": 83348, "branchName": "9. TC"},
        ]
        self.pricebooks = pricebooks if pricebooks is not None else [
            {
                "id": 18892,
                "name": "SALE",
                "isActive": True,
                "isGlobal": True,
                "startDate": "2026-01-01T00:00:00",
                "endDate": "2028-01-01T00:00:00",
                "priceBookBranches": [],
            }
        ]

    def paginate(self, path, _params, **_kwargs):
        rows = self.branches if path == "/branches" else self.pricebooks
        yield rows, len(rows), 1


class PagerClient:
    paginate = KiotVietClient.paginate

    def __init__(self, rows: list[dict], *, duplicate_second_page: bool = False):
        self.rows = rows
        self.duplicate_second_page = duplicate_second_page

    def get(self, _path, params):
        params = dict(params)
        start = int(params["currentItem"])
        size = int(params["pageSize"])
        batch = list(self.rows[start : start + size])
        if self.duplicate_second_page and start and batch:
            batch[0] = self.rows[0]
        return {"total": len(self.rows), "data": batch}


class ApiHarness:
    def __init__(
        self,
        cache_path: Path,
        status_path: Path,
        logger: logging.Logger | None = None,
        *,
        rate_limit_per_minute: int = 600,
        max_cache_age_seconds: float = TEST_MAX_CACHE_AGE_SECONDS,
        now: dt.datetime = TEST_NOW,
    ):
        self.config = ApiConfig(
            cache_path=cache_path,
            status_path=status_path,
            website_api_key=WEBSITE_KEY,
            internal_api_key=INTERNAL_KEY,
            max_cache_age_seconds=max_cache_age_seconds,
            host="127.0.0.1",
            port=8787,
            max_page_size=100,
            rate_limit_per_minute=rate_limit_per_minute,
            log_path=cache_path.parent / "api.log",
        )
        self.server = create_server(
            self.config,
            logger or quiet_logger("api-test"),
            port_override=0,
            now_provider=lambda: now,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method: str, path: str, key: str | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        headers = {} if key is None else {"X-API-Key": key}
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        body = response.read()
        headers_out = dict(response.getheaders())
        connection.close()
        return response.status, json.loads(body), headers_out


class CatalogContractTests(unittest.TestCase):
    def test_01_only_allowlisted_fields_are_cached(self):
        record = clean_record()
        self.assertEqual(set(record), set(INTERNAL_RECORD_FIELDS))
        self.assertEqual(set(record["attributes"]), {"color", "size"})

    def test_02_source_cost_is_not_exported(self):
        encoded = json.dumps(clean_record(), ensure_ascii=False).casefold()
        self.assertNotIn("co" + "st", encoded)

    def test_03_customer_invoice_supplier_fields_are_not_exported(self):
        encoded = json.dumps(clean_record(), ensure_ascii=False).casefold()
        for term in ("customer", "invoice", "supplier"):
            self.assertNotIn(term, encoded)

    def test_04_only_three_approved_branches_exist(self):
        record = clean_record()
        self.assertEqual(set(record["inventory"]), set(BRANCH_SLUGS))
        self.assertEqual(set(record["availability"]), set(BRANCH_SLUGS))

    def test_05_sale_price_comes_from_sale_map(self):
        self.assertEqual(clean_record()["sale_price"], 299000)

    def test_06_missing_sale_price_never_falls_back_to_base_price(self):
        record = build_record(
            raw_product(),
            sale_prices={},
            generation_id=TEST_GENERATION,
            data_as_of=DATA_AS_OF,
        )
        self.assertIsNone(record["sale_price"])
        self.assertEqual(record["price_status"], "unavailable")

    def test_07_missing_sale_pricebook_fails_closed(self):
        with self.assertRaisesRegex(ContractError, "SALE_PRICEBOOK_NOT_UNIQUE_EXACT"):
            resolve_live_contract(FakeResolverClient(pricebooks=[]))

    def test_08_multiple_sale_pricebooks_fail_closed(self):
        row = FakeResolverClient().pricebooks[0]
        with self.assertRaisesRegex(ContractError, "SALE_PRICEBOOK_NOT_UNIQUE_EXACT"):
            resolve_live_contract(FakeResolverClient(pricebooks=[row, dict(row)]))

    def test_09_missing_branch_mapping_fails_closed(self):
        with self.assertRaisesRegex(ContractError, "APPROVED_BRANCH_MAPPING_NOT_UNIQUE"):
            resolve_live_contract(FakeResolverClient(branches=FakeResolverClient().branches[:2]))

    def test_10_duplicate_branch_mapping_fails_closed(self):
        branches = FakeResolverClient().branches
        with self.assertRaisesRegex(ContractError, "APPROVED_BRANCH_MAPPING_NOT_UNIQUE"):
            resolve_live_contract(FakeResolverClient(branches=branches + [dict(branches[0])]))

    def test_11_pricebook_id_drift_fails_closed(self):
        row = dict(FakeResolverClient().pricebooks[0], id=99999)
        with self.assertRaisesRegex(ContractError, "PRICEBOOK_ID_DRIFT"):
            resolve_live_contract(FakeResolverClient(pricebooks=[row]))

    def test_11b_branch_status_schema_drift_fails_closed(self):
        branches = [dict(row) for row in FakeResolverClient().branches]
        branches[0]["isActive"] = True
        with self.assertRaisesRegex(ContractError, "APPROVED_BRANCH_STATUS_DRIFT"):
            resolve_live_contract(FakeResolverClient(branches=branches))

    def test_12_missing_branch_inventory_is_unavailable_not_zero(self):
        record = build_record(
            raw_product(inventories=[]),
            sale_prices={},
            generation_id=TEST_GENERATION,
            data_as_of=DATA_AS_OF,
        )
        self.assertTrue(all(value is None for value in record["inventory"].values()))
        self.assertTrue(all(value == "unavailable" for value in record["availability"].values()))

    def test_13_failed_sync_preserves_cache_and_marks_stale(self):
        class FailingClient:
            call_ledger = []

            def paginate(self, *_args, **_kwargs):
                raise TransportError("SOURCE_TIMEOUT")

            def clear_token(self):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache_path, status_path = initialize_cache(root)
            generation_path = generation_cache_path(cache_path, TEST_GENERATION)
            before = generation_path.read_bytes()
            config = SyncConfig(
                secrets_path=root / "unused",
                cache_path=cache_path,
                status_path=status_path,
                lock_path=root / ".lock",
                log_path=root / "sync.log",
                retain_generations=3,
            )
            with self.assertRaises(TransportError):
                CatalogSynchronizer(config, logger=quiet_logger("sync-fail"), client=FailingClient()).run()
            self.assertEqual(generation_path.read_bytes(), before)
            status = read_sync_status(status_path)
            self.assertTrue(status["stale"])

    def test_14_pagination_has_no_omission_or_duplicate(self):
        rows = [{"id": index} for index in range(1, 8)]
        received = []
        for batch, total, _page in PagerClient(rows).paginate("/products", {}, page_size=3):
            received.extend(row["id"] for row in batch)
        self.assertEqual(received, list(range(1, 8)))
        self.assertEqual(total, 7)

    def test_15_pagination_duplicate_fails_closed(self):
        rows = [{"id": index} for index in range(1, 6)]
        with self.assertRaisesRegex(ContractError, "PAGINATION_DUPLICATE_SOURCE_ID"):
            list(PagerClient(rows, duplicate_second_page=True).paginate("/products", {}, page_size=2))

    def test_16_missing_image_is_empty_array(self):
        self.assertEqual(
            build_record(
                raw_product(),
                sale_prices={},
                generation_id=TEST_GENERATION,
                data_as_of=DATA_AS_OF,
            )["images"],
            [],
        )

    def test_17_attributes_are_not_inferred_from_name(self):
        product = raw_product()
        product["attributes"] = []
        product["fullName"] = "Blue shirt XL"
        attributes = build_record(
            product,
            sale_prices={},
            generation_id=TEST_GENERATION,
            data_as_of=DATA_AS_OF,
        )["attributes"]
        self.assertEqual(attributes, {"color": None, "size": None})

    def test_18_out_of_scope_branch_is_rejected(self):
        product = raw_product(inventories=[{"branchId": 99999, "onHand": 1}])
        with self.assertRaisesRegex(ContractError, "OUT_OF_SCOPE_BRANCH_IN_SOURCE_RESPONSE"):
            build_record(
                product,
                sale_prices={},
                generation_id=TEST_GENERATION,
                data_as_of=DATA_AS_OF,
            )


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cache_path, self.status_path = initialize_cache(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_19_missing_or_wrong_key_is_rejected(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            self.assertEqual(api.request("GET", "/v1/catalog/products")[0], 401)
            self.assertEqual(api.request("GET", "/v1/catalog/products", "wrong-key")[0], 403)

    def test_20_website_key_cannot_access_internal(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            self.assertEqual(api.request("GET", "/v1/internal/products", WEBSITE_KEY)[0], 403)

    def test_21_catalog_never_returns_exact_inventory(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            status, payload, _headers = api.request("GET", "/v1/catalog/products", WEBSITE_KEY)
            self.assertEqual(status, 200)
            self.assertNotIn("inventory", payload["items"][0])

    def test_22_internal_returns_exact_inventory(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            status, payload, _headers = api.request("GET", "/v1/internal/products", INTERNAL_KEY)
            self.assertEqual(status, 200)
            self.assertEqual(payload["items"][0]["inventory"]["ton_that_thiep"], 3)

    def test_23_write_methods_do_not_exist(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            for method in ("POST", "PUT", "PATCH", "DELETE"):
                with self.subTest(method=method):
                    self.assertEqual(api.request(method, "/v1/catalog/products", WEBSITE_KEY)[0], 405)

    def test_24_query_cannot_select_branch_pricebook_or_upstream_url(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            for key in ("branch_id", "pricebook_id", "url", "endpoint"):
                with self.subTest(key=key):
                    status, _payload, _headers = api.request(
                        "GET", f"/v1/catalog/products?{key}=1", WEBSITE_KEY
                    )
                    self.assertEqual(status, 400)

    def test_25_health_does_not_leak_paths_counts_or_keys(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            status, payload, headers = api.request("GET", "/health")
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"status": "ok"})
            text = json.dumps(payload) + json.dumps(headers)
            self.assertNotIn(str(self.root), text)
            self.assertNotIn(WEBSITE_KEY, text)
            self.assertNotIn(INTERNAL_KEY, text)

    def test_26_logs_do_not_contain_api_keys_or_product_identity(self):
        stream = io.StringIO()
        logger = logging.getLogger("api-log-test")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        with ApiHarness(self.cache_path, self.status_path, logger=logger) as api:
            api.request("GET", "/v1/catalog/products/TEST-SKU-M", WEBSITE_KEY)
        content = stream.getvalue()
        self.assertNotIn(WEBSITE_KEY, content)
        self.assertNotIn(INTERNAL_KEY, content)
        self.assertNotIn("TEST-SKU-M", content)

    def test_27_cors_is_disabled(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            _status, _payload, headers = api.request("GET", "/health")
            self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_28_page_size_is_capped(self):
        with ApiHarness(self.cache_path, self.status_path) as api:
            status, _payload, _headers = api.request(
                "GET", "/v1/catalog/products?page_size=101", WEBSITE_KEY
            )
            self.assertEqual(status, 400)

    def test_29_uninitialized_cache_returns_503_not_empty_data(self):
        empty_root = self.root / "empty"
        config = ApiConfig(
            cache_path=empty_root / "catalog.sqlite3",
            status_path=empty_root / "status.json",
            website_api_key=WEBSITE_KEY,
            internal_api_key=INTERNAL_KEY,
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
            host="127.0.0.1",
            port=8787,
            max_page_size=100,
            rate_limit_per_minute=600,
            log_path=empty_root / "api.log",
        )
        server = create_server(config, quiet_logger("api-empty"), port_override=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
            connection.request("GET", "/v1/catalog/products", headers={"X-API-Key": WEBSITE_KEY})
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 503)
            connection.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_30_default_bind_is_localhost_and_non_loopback_is_rejected(self):
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")
        with self.assertRaisesRegex(ConfigurationError, "NON_LOOPBACK_BIND_REJECTED"):
            validate_loopback("0.0.0.0")

    def test_31_cache_files_are_private(self):
        generation_path = generation_cache_path(self.cache_path, TEST_GENERATION)
        self.assertEqual(stat.S_IMODE(generation_path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.status_path.stat().st_mode), 0o600)


class OpenApiRuntimeResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module_root = Path(__file__).resolve().parents[1]
        source_candidate = module_root / "openapi.yaml"
        handoff_candidate = Path(__file__).resolve().parents[4] / "contracts" / "openapi.yaml"
        cls.openapi_path = (
            source_candidate if source_candidate.is_file() else handoff_candidate
        )
        cls.document = json.loads(cls.openapi_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$ref": "#/components/schemas/CatalogProduct",
                "components": cls.document["components"],
            }
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cache_path, self.status_path = initialize_cache(self.root)

    def tearDown(self):
        self.temp.cleanup()

    @classmethod
    def _validator_for_schema(cls, schema: dict) -> Draft202012Validator:
        wrapped = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "components": cls.document["components"],
            **schema,
        }
        return Draft202012Validator(wrapped, format_checker=FormatChecker())

    @classmethod
    def _validator_for_component(cls, name: str) -> Draft202012Validator:
        return cls._validator_for_schema(
            {"$ref": f"#/components/schemas/{name}"}
        )

    def _actual_product(self, *, internal: bool) -> dict:
        path = (
            "/v1/internal/products/TEST-SKU-M"
            if internal
            else "/v1/catalog/products/TEST-SKU-M"
        )
        key = INTERNAL_KEY if internal else WEBSITE_KEY
        with ApiHarness(self.cache_path, self.status_path) as api:
            status, payload, _headers = api.request("GET", path, key)
        self.assertEqual(status, 200)
        return payload

    def test_openapi_01_actual_catalog_product_validates(self):
        self._validator_for_component("CatalogProduct").validate(
            self._actual_product(internal=False)
        )

    def test_openapi_02_actual_internal_product_with_inventory_validates(self):
        payload = self._actual_product(internal=True)
        self.assertIn("inventory", payload)
        self._validator_for_component("InternalProduct").validate(payload)

    def test_openapi_03_missing_required_field_is_rejected(self):
        payload = self._actual_product(internal=False)
        payload.pop("name")
        with self.assertRaises(ValidationError):
            self._validator_for_component("CatalogProduct").validate(payload)

    def test_openapi_04_wrong_inventory_type_is_rejected(self):
        payload = self._actual_product(internal=True)
        payload["inventory"]["ton_that_thiep"] = "3"
        with self.assertRaises(ValidationError):
            self._validator_for_component("InternalProduct").validate(payload)

    def test_openapi_05_extra_field_is_rejected(self):
        payload = self._actual_product(internal=True)
        payload["unexpected"] = True
        with self.assertRaises(ValidationError):
            self._validator_for_component("InternalProduct").validate(payload)

    def test_openapi_06_all_examples_validate_against_declared_schema(self):
        def resolve(value: dict) -> dict:
            if "$ref" not in value:
                return value
            target: object = self.document
            for part in value["$ref"].removeprefix("#/").split("/"):
                target = target[part]  # type: ignore[index]
            return target  # type: ignore[return-value]

        validated = 0
        for path_item in self.document["paths"].values():
            for operation in path_item.values():
                for response in operation["responses"].values():
                    response = resolve(response)
                    media = response.get("content", {}).get("application/json")
                    if not media:
                        continue
                    examples = []
                    if "example" in media:
                        examples.append(media["example"])
                    examples.extend(
                        item["value"] for item in media.get("examples", {}).values()
                    )
                    validator = self._validator_for_schema(media["schema"])
                    for example in examples:
                        validator.validate(example)
                        validated += 1
        self.assertGreaterEqual(validated, 10)


class PublicationPolicyRemediationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_new_01_catalog_excludes_missing_sale_price(self):
        records = [record_for("ELIGIBLE"), record_for("MISSING", has_sale_row=False)]
        cache_path, status_path = initialize_cache(self.root, records=records)
        reader = CacheReader(
            cache_path,
            status_path,
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
            now=TEST_NOW,
        )
        items, total = reader.list_records(offset=0, limit=100, public_only=True)
        self.assertEqual(total, 1)
        self.assertEqual([item["code"] for item in items], ["ELIGIBLE"])

    def test_new_02_catalog_excludes_zero_negative_string_and_nonfinite_prices(self):
        records = [
            record_for("POSITIVE", sale_price=1),
            record_for("ZERO", sale_price=0),
            record_for("NEGATIVE", sale_price=-1),
            record_for("STRING", sale_price="not-a-price"),
            record_for("NONFINITE", sale_price="NaN"),
        ]
        cache_path, status_path = initialize_cache(self.root, records=records)
        public, total = CacheReader(
            cache_path,
            status_path,
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
            now=TEST_NOW,
        ).list_records(offset=0, limit=100, public_only=True)
        self.assertEqual(total, 1)
        self.assertEqual([item["code"] for item in public], ["POSITIVE"])

    def test_new_03_catalog_excludes_inactive_product_when_source_has_status(self):
        records = [record_for("ACTIVE"), record_for("INACTIVE", active=False)]
        cache_path, status_path = initialize_cache(self.root, records=records)
        reader = CacheReader(
            cache_path,
            status_path,
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
            now=TEST_NOW,
        )
        self.assertIsNone(reader.get_record("INACTIVE", public_only=True))
        self.assertIsNotNone(reader.get_record("INACTIVE", public_only=False))

    def test_new_04_internal_keeps_missing_sale_price_as_null_unavailable(self):
        missing = record_for("MISSING", has_sale_row=False)
        cache_path, status_path = initialize_cache(self.root, records=[missing])
        with ApiHarness(cache_path, status_path) as api:
            status, payload, _headers = api.request(
                "GET", "/v1/internal/products/MISSING", INTERNAL_KEY
            )
        self.assertEqual(status, 200)
        self.assertIsNone(payload["sale_price"])
        self.assertEqual(payload["price_status"], "unavailable")

    def test_new_05_catalog_detail_returns_404_for_internal_only_code(self):
        cache_path, status_path = initialize_cache(
            self.root, records=[record_for("MISSING", has_sale_row=False)]
        )
        with ApiHarness(cache_path, status_path) as api:
            status, _payload, _headers = api.request(
                "GET", "/v1/catalog/products/MISSING", WEBSITE_KEY
            )
        self.assertEqual(status, 404)

    def test_new_06_no_default_price_fallback_enters_public_repository(self):
        product = raw_product(code="NO-SALE")
        product["basePrice"] = 999999999
        record = build_record(
            product,
            sale_prices={},
            generation_id=TEST_GENERATION,
            data_as_of=DATA_AS_OF,
        )
        cache_path, status_path = initialize_cache(self.root, records=[record])
        reader = CacheReader(
            cache_path,
            status_path,
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
            now=TEST_NOW,
        )
        self.assertIsNone(reader.get_record("NO-SALE", public_only=True))
        internal = reader.get_record("NO-SALE")
        self.assertIsNone(internal["sale_price"])
        self.assertEqual(internal["price_status"], "unavailable")

    def test_new_07_duplicate_product_code_fails_atomic_cache_write(self):
        cache_path = self.root / "catalog.sqlite3"
        with self.assertRaisesRegex(ContractError, "DUPLICATE_PRODUCT_CODE"):
            write_cache_atomic(
                generation_cache_path(cache_path, TEST_GENERATION),
                [record_for("DUPLICATE"), record_for("DUPLICATE")],
                metadata={
                    "generation_id": TEST_GENERATION,
                    "data_as_of": DATA_AS_OF,
                },
            )
        self.assertFalse(cache_path.exists())

    def test_new_08_public_pagination_has_no_duplicate_or_omitted_eligible_code(self):
        records = [record_for(f"ELIGIBLE-{index:02d}") for index in range(7)]
        records.extend(
            [
                record_for("MISSING", has_sale_row=False),
                record_for("ZERO", sale_price=0),
                record_for("INACTIVE", active=False),
            ]
        )
        cache_path, status_path = initialize_cache(self.root, records=records)
        received: list[str] = []
        with ApiHarness(cache_path, status_path) as api:
            for page in range(1, 5):
                status, payload, _headers = api.request(
                    "GET", f"/v1/catalog/products?page={page}&page_size=2", WEBSITE_KEY
                )
                self.assertEqual(status, 200)
                self.assertEqual(payload["total"], 7)
                received.extend(item["code"] for item in payload["items"])
        self.assertEqual(received, [f"ELIGIBLE-{index:02d}" for index in range(7)])
        self.assertEqual(len(received), len(set(received)))

    def test_new_09_rate_limit_returns_429_after_threshold(self):
        cache_path, status_path = initialize_cache(self.root)
        with ApiHarness(cache_path, status_path, rate_limit_per_minute=2) as api:
            statuses = [
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0]
                for _ in range(3)
            ]
        self.assertEqual(statuses, [200, 200, 429])

    def test_new_10_never_synchronized_cache_fails_closed(self):
        with self.assertRaisesRegex(CacheUnavailable, "CACHE_STATUS_MISSING"):
            CacheReader(
                self.root / "missing.sqlite3",
                self.root / "missing-status.json",
                max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
                now=TEST_NOW,
            )

    def test_new_11_failed_sync_does_not_replace_valid_snapshot(self):
        class FailingClient:
            call_ledger = []

            def paginate(self, *_args, **_kwargs):
                raise TransportError("SOURCE_TIMEOUT")

            def clear_token(self):
                return None

        cache_path, status_path = initialize_cache(self.root)
        generation_path = generation_cache_path(cache_path, TEST_GENERATION)
        before = generation_path.read_bytes()
        config = SyncConfig(
            secrets_path=self.root / "unused",
            cache_path=cache_path,
            status_path=status_path,
            lock_path=self.root / ".lock",
            log_path=self.root / "sync.log",
            retain_generations=3,
        )
        with self.assertRaises(TransportError):
            CatalogSynchronizer(
                config, logger=quiet_logger("new-sync-fail"), client=FailingClient()
            ).run()
        self.assertEqual(generation_path.read_bytes(), before)

    def test_new_12_failed_sync_serves_previous_snapshot_as_stale(self):
        cache_path, status_path = initialize_cache(self.root, stale=True)
        with ApiHarness(cache_path, status_path) as api:
            status, payload, _headers = api.request(
                "GET", "/v1/catalog/products/TEST-SKU-M", WEBSITE_KEY
            )
        self.assertEqual(status, 200)
        self.assertTrue(payload["stale"])
        self.assertEqual(payload["data_as_of"], DATA_AS_OF)

    def test_new_13_website_response_has_no_exact_inventory(self):
        cache_path, status_path = initialize_cache(self.root)
        with ApiHarness(cache_path, status_path) as api:
            status, payload, _headers = api.request(
                "GET", "/v1/catalog/products/TEST-SKU-M", WEBSITE_KEY
            )
        self.assertEqual(status, 200)
        self.assertNotIn("inventory", payload)

    def test_new_14_website_key_is_forbidden_from_internal_endpoint(self):
        cache_path, status_path = initialize_cache(self.root)
        with ApiHarness(cache_path, status_path) as api:
            status, _payload, _headers = api.request(
                "GET", "/v1/internal/products", WEBSITE_KEY
            )
        self.assertEqual(status, 403)

    def test_new_15_api_exposes_only_three_approved_branch_slugs(self):
        cache_path, status_path = initialize_cache(self.root)
        with ApiHarness(cache_path, status_path) as api:
            catalog_status, catalog, _headers = api.request(
                "GET", "/v1/catalog/products/TEST-SKU-M", WEBSITE_KEY
            )
            internal_status, internal, _headers = api.request(
                "GET", "/v1/internal/products/TEST-SKU-M", INTERNAL_KEY
            )
        self.assertEqual(catalog_status, 200)
        self.assertEqual(internal_status, 200)
        self.assertEqual(set(catalog["availability"]), set(BRANCH_SLUGS))
        self.assertEqual(set(internal["inventory"]), set(BRANCH_SLUGS))


class GenerationCoherenceAndFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _metadata() -> dict:
        return {
            "pricebook_name": "SALE",
            "pricebook_id": 18892,
            "approved_branches": {
                "ton_that_thiep": 83336,
                "nguyen_trai": 83335,
                "tam_coc": 83348,
            },
        }

    @staticmethod
    def _records(generation_id: str, data_as_of: str) -> list[dict]:
        return [dict(clean_record(), generation_id=generation_id, data_as_of=data_as_of)]

    @staticmethod
    def _mutate_status(path: Path, **changes) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(changes)
        path.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    @staticmethod
    def _mutate_meta(database: Path, key: str, value: object) -> None:
        connection = sqlite3.connect(database)
        connection.execute(
            "UPDATE meta SET value = ? WHERE key = ?",
            (json.dumps(value, separators=(",", ":")), key),
        )
        connection.commit()
        connection.close()

    def _reader(
        self,
        cache_path: Path,
        status_path: Path,
        *,
        max_age: float = TEST_MAX_CACHE_AGE_SECONDS,
        now: dt.datetime = TEST_NOW,
    ) -> CacheReader:
        return CacheReader(
            cache_path,
            status_path,
            max_cache_age_seconds=max_age,
            now=now,
        )

    def _faulted_commit(
        self,
        cache_path: Path,
        status_path: Path,
        point: str,
    ) -> None:
        def inject(current: str) -> None:
            if current == point:
                raise RuntimeError("INJECTED_COMMIT_FAULT")

        commit_snapshot_atomic(
            cache_path,
            status_path,
            self._records(SECOND_GENERATION, "2026-08-10T14:45:00+07:00"),
            metadata=self._metadata(),
            generation_id=SECOND_GENERATION,
            data_as_of="2026-08-10T14:45:00+07:00",
            last_attempt_at="2026-08-10T14:45:00+07:00",
            fault_injector=inject,
        )

    def test_coherence_01_database_new_generation_status_old_returns_503(self):
        cache_path, status_path = initialize_cache(self.root)
        database = generation_cache_path(cache_path, TEST_GENERATION)
        self._mutate_meta(database, "generation_id", SECOND_GENERATION)
        with ApiHarness(cache_path, status_path) as api:
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0], 503
            )
            self.assertEqual(
                api.request("GET", "/v1/internal/products", INTERNAL_KEY)[0], 503
            )

    def test_coherence_02_status_new_generation_database_old_returns_503(self):
        cache_path, status_path = initialize_cache(self.root)
        self._mutate_status(status_path, generation_id=SECOND_GENERATION)
        with ApiHarness(cache_path, status_path) as api:
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0], 503
            )

    def test_coherence_03_same_generation_different_cutoff_returns_503(self):
        cache_path, status_path = initialize_cache(self.root)
        self._mutate_status(status_path, data_as_of="2026-08-10T14:31:00+07:00")
        with ApiHarness(cache_path, status_path) as api:
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0], 503
            )

    def test_coherence_04_record_cutoff_mismatch_fails_closed(self):
        cache_path, status_path = initialize_cache(self.root)
        database = generation_cache_path(cache_path, TEST_GENERATION)
        connection = sqlite3.connect(database)
        connection.execute("PRAGMA ignore_check_constraints=ON")
        payload = json.loads(
            connection.execute("SELECT payload FROM products LIMIT 1").fetchone()[0]
        )
        payload["data_as_of"] = "2026-08-10T14:31:00+07:00"
        connection.execute(
            "UPDATE products SET payload = ?",
            (json.dumps(payload, sort_keys=True, separators=(",", ":")),),
        )
        connection.commit()
        connection.close()
        with self.assertRaises(CacheUnavailable):
            self._reader(cache_path, status_path)

    def test_coherence_05_fault_after_cache_temp_before_commit_preserves_old(self):
        cache_path, status_path = initialize_cache(self.root)
        with self.assertRaisesRegex(RuntimeError, "INJECTED_COMMIT_FAULT"):
            self._faulted_commit(cache_path, status_path, "after_cache_temp_ready")
        reader = self._reader(cache_path, status_path)
        self.assertEqual(reader.status["generation_id"], TEST_GENERATION)
        self.assertFalse(generation_cache_path(cache_path, SECOND_GENERATION).exists())

    def test_coherence_06_fault_between_database_and_status_keeps_old_authority(self):
        cache_path, status_path = initialize_cache(self.root)
        with self.assertRaisesRegex(RuntimeError, "INJECTED_COMMIT_FAULT"):
            self._faulted_commit(
                cache_path, status_path, "after_generation_database_ready"
            )
        reader = self._reader(cache_path, status_path)
        self.assertEqual(reader.status["generation_id"], TEST_GENERATION)
        self.assertFalse(generation_cache_path(cache_path, SECOND_GENERATION).exists())

    def test_coherence_07_status_write_failure_after_database_keeps_old_authority(self):
        cache_path, status_path = initialize_cache(self.root)
        with self.assertRaisesRegex(RuntimeError, "INJECTED_COMMIT_FAULT"):
            self._faulted_commit(cache_path, status_path, "before_status_commit")
        reader = self._reader(cache_path, status_path)
        self.assertEqual(reader.status["generation_id"], TEST_GENERATION)
        self.assertEqual(reader.status["data_as_of"], DATA_AS_OF)

    def test_freshness_08_within_threshold_is_usable(self):
        cache_path, status_path = initialize_cache(self.root)
        reader = self._reader(cache_path, status_path, max_age=1801)
        self.assertEqual(reader.status["data_as_of"], DATA_AS_OF)

    def test_freshness_09_exact_boundary_is_usable(self):
        cache_path, status_path = initialize_cache(self.root)
        reader = self._reader(cache_path, status_path, max_age=1800)
        self.assertEqual(reader.status["data_as_of"], DATA_AS_OF)

    def test_freshness_10_over_age_health_and_api_return_503(self):
        cache_path, status_path = initialize_cache(
            self.root, data_as_of="2000-01-01T00:00:00+07:00"
        )
        with ApiHarness(cache_path, status_path, max_cache_age_seconds=60) as api:
            health_status, health, _headers = api.request("GET", "/health")
            catalog_status = api.request(
                "GET", "/v1/catalog/products", WEBSITE_KEY
            )[0]
        self.assertEqual(health_status, 503)
        self.assertEqual(health, {"status": "unavailable"})
        self.assertEqual(catalog_status, 503)

    def test_freshness_11_stale_false_cannot_make_old_cache_fresh(self):
        cache_path, status_path = initialize_cache(
            self.root, data_as_of="2000-01-01T00:00:00+07:00", stale=False
        )
        self.assertFalse(json.loads(status_path.read_text())["stale"])
        with self.assertRaisesRegex(CacheUnavailable, "CACHE_TOO_OLD"):
            self._reader(cache_path, status_path, max_age=60)

    def test_freshness_12_invalid_and_future_cutoff_fail_closed(self):
        invalid_root = self.root / "invalid"
        cache_path, status_path = initialize_cache(invalid_root)
        self._mutate_status(status_path, data_as_of="not-a-timestamp")
        with self.assertRaisesRegex(CacheUnavailable, "CACHE_CUTOFF_INVALID"):
            self._reader(cache_path, status_path)

        future_root = self.root / "future"
        future_cutoff = "2026-08-10T15:00:01+07:00"
        cache_path, status_path = initialize_cache(
            future_root, data_as_of=future_cutoff
        )
        with self.assertRaisesRegex(CacheUnavailable, "CACHE_CUTOFF_IN_FUTURE"):
            self._reader(cache_path, status_path)

    def test_coherence_13_uninitialized_cache_still_returns_503(self):
        with ApiHarness(
            self.root / "missing.sqlite3", self.root / "missing-status.json"
        ) as api:
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0], 503
            )

    def test_coherence_14_failed_source_sync_does_not_turn_missing_inventory_to_zero(self):
        class FailingClient:
            call_ledger = []

            def paginate(self, *_args, **_kwargs):
                raise TransportError("SOURCE_TIMEOUT")

            def clear_token(self):
                return None

        record = build_record(
            raw_product(inventories=[]),
            sale_prices={"TEST-SKU-M": 299000},
            generation_id=TEST_GENERATION,
            data_as_of=DATA_AS_OF,
        )
        cache_path, status_path = initialize_cache(self.root, records=[record])
        config = SyncConfig(
            secrets_path=self.root / "unused",
            cache_path=cache_path,
            status_path=status_path,
            lock_path=self.root / ".lock",
            log_path=self.root / "sync.log",
            retain_generations=3,
        )
        with self.assertRaises(TransportError):
            CatalogSynchronizer(
                config,
                logger=quiet_logger("coherence-source-fail"),
                client=FailingClient(),
            ).run()
        cached = self._reader(cache_path, status_path).get_record("TEST-SKU-M")
        self.assertTrue(all(value is None for value in cached["inventory"].values()))
        self.assertTrue(
            all(value == "unavailable" for value in cached["availability"].values())
        )
        self.assertTrue(cached["stale"])

    def test_coherence_15_auth_and_publication_policy_do_not_regress(self):
        records = [
            record_for("ELIGIBLE"),
            record_for("MISSING", has_sale_row=False),
            record_for("INACTIVE", active=False),
        ]
        cache_path, status_path = initialize_cache(self.root, records=records)
        with ApiHarness(cache_path, status_path) as api:
            public_status, public, _headers = api.request(
                "GET", "/v1/catalog/products", WEBSITE_KEY
            )
            internal_status, internal, _headers = api.request(
                "GET", "/v1/internal/products", INTERNAL_KEY
            )
            forbidden_status = api.request(
                "GET", "/v1/internal/products", WEBSITE_KEY
            )[0]
        self.assertEqual(public_status, 200)
        self.assertEqual([item["code"] for item in public["items"]], ["ELIGIBLE"])
        self.assertNotIn("inventory", public["items"][0])
        self.assertEqual(internal_status, 200)
        self.assertEqual(internal["total"], 3)
        self.assertEqual(forbidden_status, 403)

    def test_coherence_16_record_count_mismatch_returns_503(self):
        cache_path, status_path = initialize_cache(self.root)
        self._mutate_status(status_path, record_count=2)
        with ApiHarness(cache_path, status_path) as api:
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0], 503
            )

    def test_freshness_17_runtime_configuration_missing_or_invalid_fails_closed(self):
        base = {
            "KIOT_CATALOG_WEBSITE_API_KEY": WEBSITE_KEY,
            "KIOT_CATALOG_INTERNAL_API_KEY": INTERNAL_KEY,
        }
        for value in (None, "", "0", "-1", "not-a-number", "nan", "inf"):
            with self.subTest(value=value), patch.dict(os.environ, base, clear=True):
                if value is not None:
                    os.environ["KIOT_CATALOG_MAX_CACHE_AGE_SECONDS"] = value
                with self.assertRaises(ConfigurationError):
                    load_api_config()
        with patch.dict(
            os.environ,
            {**base, "KIOT_CATALOG_MAX_CACHE_AGE_SECONDS": "60"},
            clear=True,
        ):
            self.assertEqual(load_api_config().max_cache_age_seconds, 60.0)

    def test_coherence_18_fault_after_status_commit_leaves_new_snapshot_usable(self):
        cache_path, status_path = initialize_cache(self.root)
        with self.assertRaisesRegex(RuntimeError, "INJECTED_COMMIT_FAULT"):
            self._faulted_commit(cache_path, status_path, "after_status_commit")
        reader = self._reader(cache_path, status_path)
        self.assertEqual(reader.status["generation_id"], SECOND_GENERATION)
        self.assertEqual(reader.status["data_as_of"], "2026-08-10T14:45:00+07:00")

    def test_coherence_19_status_and_database_schema_mismatch_return_503(self):
        status_root = self.root / "status-schema"
        cache_path, status_path = initialize_cache(status_root)
        self._mutate_status(status_path, cache_schema_version="old-cache-schema")
        with ApiHarness(cache_path, status_path) as api:
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0], 503
            )

        database_root = self.root / "database-schema"
        cache_path, status_path = initialize_cache(database_root)
        self._mutate_meta(
            generation_cache_path(cache_path, TEST_GENERATION),
            "schema_version",
            "old-cache-schema",
        )
        with ApiHarness(cache_path, status_path) as api:
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0], 503
            )

    def test_coherence_20_generation_id_reuse_is_rejected_without_deleting_current(self):
        cache_path, status_path = initialize_cache(self.root)
        with self.assertRaisesRegex(ContractError, "GENERATION_CACHE_ALREADY_EXISTS"):
            commit_snapshot_atomic(
                cache_path,
                status_path,
                self._records(TEST_GENERATION, DATA_AS_OF),
                metadata=self._metadata(),
                generation_id=TEST_GENERATION,
                data_as_of=DATA_AS_OF,
                last_attempt_at=DATA_AS_OF,
            )
        reader = self._reader(cache_path, status_path)
        self.assertEqual(reader.status["generation_id"], TEST_GENERATION)

    def test_freshness_21_injected_far_future_clock_is_deterministic(self):
        future_root = self.root / "far-future-clock"
        cutoff = "2042-03-14T09:00:00+07:00"
        fresh_now = dt.datetime.fromisoformat("2042-03-14T10:00:00+07:00")
        stale_now = dt.datetime.fromisoformat("2042-03-14T12:00:01+07:00")
        cache_path, status_path = initialize_cache(
            future_root,
            data_as_of=cutoff,
        )

        with ApiHarness(
            cache_path,
            status_path,
            max_cache_age_seconds=10_800,
            now=fresh_now,
        ) as api:
            self.assertEqual(api.request("GET", "/health")[0], 200)
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0],
                200,
            )

        with ApiHarness(
            cache_path,
            status_path,
            max_cache_age_seconds=10_800,
            now=stale_now,
        ) as api:
            self.assertEqual(api.request("GET", "/health")[0], 503)
            self.assertEqual(
                api.request("GET", "/v1/catalog/products", WEBSITE_KEY)[0],
                503,
            )


class SyncLockRaceRemediationTests(unittest.TestCase):
    NEW_CUTOFF = "2026-08-10T14:45:00+07:00"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _config(self) -> SyncConfig:
        return SyncConfig(
            secrets_path=self.root / "unused",
            cache_path=self.root / "catalog.sqlite3",
            status_path=self.root / "sync_status.json",
            lock_path=self.root / ".sync.lock",
            log_path=self.root / "sync.log",
            retain_generations=3,
        )

    def _synchronizer(self) -> CatalogSynchronizer:
        return CatalogSynchronizer(
            self._config(),
            logger=quiet_logger("lock-race"),
            client=object(),
        )

    def _commit_new_generation(self, *, code: str = "LATEST") -> None:
        record = dict(
            record_for(code),
            generation_id=SECOND_GENERATION,
            data_as_of=self.NEW_CUTOFF,
        )
        commit_snapshot_atomic(
            self.root / "catalog.sqlite3",
            self.root / "sync_status.json",
            [record],
            metadata=GenerationCoherenceAndFreshnessTests._metadata(),
            generation_id=SECOND_GENERATION,
            data_as_of=self.NEW_CUTOFF,
            last_attempt_at=self.NEW_CUTOFF,
        )

    def _busy_attempt(self) -> ContractError:
        synchronizer = self._synchronizer()
        with SyncLock(self._config().lock_path):
            with self.assertRaises(ContractError) as caught:
                synchronizer.run()
        self.assertEqual(caught.exception.code, "SYNC_LOCK_BUSY")
        return caught.exception

    def test_lock_01_healthy_snapshot_busy_status_is_byte_for_byte_unchanged(self):
        initialize_cache(self.root)
        before = self._config().status_path.read_bytes()
        self._busy_attempt()
        self.assertEqual(self._config().status_path.read_bytes(), before)

    def test_lock_02_busy_preserves_authoritative_status_fields(self):
        initialize_cache(self.root)
        before = read_sync_status(self._config().status_path)
        self._busy_attempt()
        after = read_sync_status(self._config().status_path)
        for field in (
            "stale",
            "last_attempt_at",
            "last_error_code",
            "generation_id",
            "data_as_of",
        ):
            self.assertEqual(after[field], before[field], field)

    def test_lock_03_uninitialized_busy_does_not_create_status(self):
        status_path = self._config().status_path
        self.assertFalse(status_path.exists())
        self._busy_attempt()
        self.assertFalse(status_path.exists())

    def test_lock_04_busy_handler_cannot_roll_pointer_back_after_new_commit(self):
        initialize_cache(self.root)
        real_read = read_sync_status
        state = {"new_commit_during_stale_read": False}

        def stale_read_then_new_commit(path: Path) -> dict:
            old_status = real_read(path)
            self._commit_new_generation()
            state["new_commit_during_stale_read"] = True
            return old_status

        with SyncLock(self._config().lock_path):
            with patch(
                "integrations.kiot_public_catalog.sync.read_sync_status",
                side_effect=stale_read_then_new_commit,
            ):
                with self.assertRaisesRegex(ContractError, "SYNC_LOCK_BUSY"):
                    self._synchronizer().run()
            if not state["new_commit_during_stale_read"]:
                self._commit_new_generation()

        final_status = real_read(self._config().status_path)
        self.assertEqual(final_status["generation_id"], SECOND_GENERATION)
        self.assertEqual(final_status["data_as_of"], self.NEW_CUTOFF)
        self.assertFalse(final_status["stale"])

    def test_lock_05_source_failure_marks_current_generation_stale(self):
        initialize_cache(self.root)

        class SourceFailureSynchronizer(CatalogSynchronizer):
            def _run_locked(self, attempt_at: str) -> dict:
                raise TransportError("SOURCE_TIMEOUT")

        with self.assertRaisesRegex(TransportError, "SOURCE_TIMEOUT"):
            SourceFailureSynchronizer(
                self._config(), logger=quiet_logger("source-failure"), client=object()
            ).run()
        status = read_sync_status(self._config().status_path)
        self.assertEqual(status["generation_id"], TEST_GENERATION)
        self.assertTrue(status["stale"])
        self.assertEqual(status["last_error_code"], "SOURCE_TIMEOUT")

    def test_lock_06_failure_mark_completes_before_lock_release(self):
        initialize_cache(self.root)
        events: list[str] = []

        class TrackingLock:
            held = False

            def __init__(self, _path: Path) -> None:
                pass

            def __enter__(self):
                type(self).held = True
                events.append("enter")
                return self

            def __exit__(self, *_args):
                events.append("exit")
                type(self).held = False

        class SourceFailureSynchronizer(CatalogSynchronizer):
            def _run_locked(self, attempt_at: str) -> dict:
                raise TransportError("SOURCE_TIMEOUT")

        synchronizer = SourceFailureSynchronizer(
            self._config(), logger=quiet_logger("failure-order"), client=object()
        )
        original_mark_failure = synchronizer._mark_failure

        def observed_mark_failure(attempt_at: str, error_code: str) -> None:
            self.assertTrue(TrackingLock.held)
            events.append("mark")
            original_mark_failure(attempt_at, error_code)

        synchronizer._mark_failure = observed_mark_failure
        with patch("integrations.kiot_public_catalog.sync.SyncLock", TrackingLock):
            with self.assertRaisesRegex(TransportError, "SOURCE_TIMEOUT"):
                synchronizer.run()
        self.assertEqual(events, ["enter", "mark", "exit"])
        self.assertFalse(TrackingLock.held)

    def test_lock_07_success_after_failure_becomes_authoritative(self):
        initialize_cache(self.root)

        class SourceFailureSynchronizer(CatalogSynchronizer):
            def _run_locked(self, attempt_at: str) -> dict:
                raise TransportError("SOURCE_TIMEOUT")

        class SuccessfulSynchronizer(CatalogSynchronizer):
            def _run_locked(inner_self, attempt_at: str) -> dict:
                self._commit_new_generation()
                return {"status": "PASS", "data_as_of": self.NEW_CUTOFF}

        with self.assertRaises(TransportError):
            SourceFailureSynchronizer(
                self._config(), logger=quiet_logger("failure-first"), client=object()
            ).run()
        self.assertTrue(read_sync_status(self._config().status_path)["stale"])
        result = SuccessfulSynchronizer(
            self._config(), logger=quiet_logger("success-second"), client=object()
        ).run()
        self.assertEqual(result["status"], "PASS")
        status = read_sync_status(self._config().status_path)
        self.assertEqual(status["generation_id"], SECOND_GENERATION)
        self.assertFalse(status["stale"])
        self.assertIsNone(status["last_error_code"])

    def test_lock_08_health_stays_ok_after_busy_skip(self):
        cache_path, status_path = initialize_cache(self.root)
        self._busy_attempt()
        with ApiHarness(cache_path, status_path) as api:
            status, payload, _headers = api.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok"})

    def test_lock_09_public_and_internal_serve_latest_coherent_generation(self):
        cache_path, status_path = initialize_cache(
            self.root, records=[record_for("OLD")]
        )
        with SyncLock(self._config().lock_path):
            self._commit_new_generation(code="LATEST")
        with ApiHarness(cache_path, status_path) as api:
            public_status, public, _headers = api.request(
                "GET", "/v1/catalog/products", WEBSITE_KEY
            )
            internal_status, internal, _headers = api.request(
                "GET", "/v1/internal/products", INTERNAL_KEY
            )
        self.assertEqual(public_status, 200)
        self.assertEqual(internal_status, 200)
        self.assertEqual([row["code"] for row in public["items"]], ["LATEST"])
        self.assertEqual([row["code"] for row in internal["items"]], ["LATEST"])

    def test_lock_10_coherence_freshness_publication_and_auth_do_not_regress(self):
        records = [
            record_for("ELIGIBLE"),
            record_for("MISSING", has_sale_row=False),
            record_for("INACTIVE", active=False),
        ]
        cache_path, status_path = initialize_cache(self.root, records=records)
        before = self._config().status_path.read_bytes()
        self._busy_attempt()
        self.assertEqual(self._config().status_path.read_bytes(), before)
        with ApiHarness(cache_path, status_path) as api:
            health_status = api.request("GET", "/health")[0]
            public_status, public, _headers = api.request(
                "GET", "/v1/catalog/products", WEBSITE_KEY
            )
            internal_status, internal, _headers = api.request(
                "GET", "/v1/internal/products", INTERNAL_KEY
            )
            forbidden_status = api.request(
                "GET", "/v1/internal/products", WEBSITE_KEY
            )[0]
        self.assertEqual(health_status, 200)
        self.assertEqual(public_status, 200)
        self.assertEqual([row["code"] for row in public["items"]], ["ELIGIBLE"])
        self.assertNotIn("inventory", public["items"][0])
        self.assertEqual(internal_status, 200)
        self.assertEqual(internal["total"], 3)
        self.assertEqual(forbidden_status, 403)


class RetentionProductionReadinessTests(unittest.TestCase):
    GEN_A = "1" * 32
    GEN_B = "2" * 32
    GEN_C = "3" * 32
    GEN_D = "4" * 32
    GEN_E = "5" * 32
    GEN_F = "6" * 32
    CUTOFFS = {
        GEN_A: "2026-08-10T14:00:00+07:00",
        GEN_B: "2026-08-10T14:10:00+07:00",
        GEN_C: "2026-08-10T14:20:00+07:00",
        GEN_D: "2026-08-10T14:30:00+07:00",
        GEN_E: "2026-08-10T14:40:00+07:00",
        GEN_F: "2026-08-10T14:50:00+07:00",
    }

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _metadata() -> dict:
        return GenerationCoherenceAndFreshnessTests._metadata()

    def _config(self, *, retain: int = 3) -> SyncConfig:
        return SyncConfig(
            secrets_path=self.root / "unused",
            cache_path=self.root / "catalog.sqlite3",
            status_path=self.root / "sync_status.json",
            lock_path=self.root / ".sync.lock",
            log_path=self.root / "sync.log",
            retain_generations=retain,
        )

    def _record(self, generation_id: str, cutoff: str, code: str) -> dict:
        return dict(
            record_for(code),
            generation_id=generation_id,
            data_as_of=cutoff,
        )

    def _commit(
        self,
        generation_id: str,
        *,
        code: str | None = None,
        cutoff: str | None = None,
        fault_injector=None,
    ) -> Path:
        data_as_of = cutoff or self.CUTOFFS[generation_id]
        commit_snapshot_atomic(
            self.root / "catalog.sqlite3",
            self.root / "sync_status.json",
            [self._record(generation_id, data_as_of, code or generation_id[:4])],
            metadata=self._metadata(),
            generation_id=generation_id,
            data_as_of=data_as_of,
            last_attempt_at=data_as_of,
            fault_injector=fault_injector,
        )
        return generation_cache_path(self.root / "catalog.sqlite3", generation_id)

    def _orphan(self, generation_id: str, cutoff: str) -> Path:
        target = generation_cache_path(self.root / "catalog.sqlite3", generation_id)
        write_cache_atomic(
            target,
            [self._record(generation_id, cutoff, "ORPHAN")],
            metadata={
                **self._metadata(),
                "generation_id": generation_id,
                "data_as_of": cutoff,
            },
        )
        return target

    def _seed(self, *generation_ids: str) -> None:
        for generation_id in generation_ids:
            self._commit(generation_id)

    def _exists(self, generation_id: str) -> bool:
        return generation_cache_path(
            self.root / "catalog.sqlite3", generation_id
        ).exists()

    def _cleanup(self, *, fault_injector=None) -> dict:
        return cleanup_generation_retention(
            self.root / "catalog.sqlite3",
            self.root / "sync_status.json",
            3,
            fault_injector=fault_injector,
        )

    def _commit_then_cleanup_synchronizer(
        self, generation_id: str, *, code: str | None = None
    ) -> CatalogSynchronizer:
        outer = self

        class SyntheticSuccessfulSynchronizer(CatalogSynchronizer):
            def _run_locked(inner_self, attempt_at: str) -> dict:
                outer._commit(generation_id, code=code)
                retention = inner_self._apply_retention_locked()
                return {"status": "PASS", "retention": retention}

        return SyntheticSuccessfulSynchronizer(
            self._config(), logger=quiet_logger("retention-sync"), client=object()
        )

    def test_retention_01_commit_d_keeps_d_c_b_and_deletes_a(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C, self.GEN_D)
        result = self._cleanup()
        self.assertFalse(self._exists(self.GEN_A))
        self.assertTrue(all(self._exists(item) for item in (self.GEN_B, self.GEN_C, self.GEN_D)))
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(result["valid_after"], 3)

    def test_retention_02_one_or_two_generations_are_not_over_deleted(self):
        for count in (1, 2):
            with self.subTest(count=count):
                root = self.root / str(count)
                original_root = self.root
                self.root = root
                try:
                    generations = (self.GEN_A, self.GEN_B)[:count]
                    self._seed(*generations)
                    result = self._cleanup()
                    self.assertEqual(result["deleted"], 0)
                    self.assertTrue(all(self._exists(item) for item in generations))
                finally:
                    self.root = original_root

    def test_retention_03_authoritative_survives_filename_and_mtime_noise(self):
        mapping = (
            ("f" * 32, "2026-08-10T14:00:00+07:00"),
            ("e" * 32, "2026-08-10T14:10:00+07:00"),
            ("d" * 32, "2026-08-10T14:20:00+07:00"),
            ("0" * 32, "2026-08-10T14:30:00+07:00"),
        )
        for generation_id, cutoff in mapping:
            self._commit(generation_id, cutoff=cutoff)
        authoritative = generation_cache_path(self.root / "catalog.sqlite3", "0" * 32)
        os.utime(authoritative, (1, 1))
        os.utime(generation_cache_path(self.root / "catalog.sqlite3", "f" * 32), None)
        self._cleanup()
        self.assertTrue(authoritative.exists())
        self.assertEqual(read_sync_status(self.root / "sync_status.json")["generation_id"], "0" * 32)

    def test_retention_04_predecessor_order_uses_metadata_not_name_or_mtime(self):
        mapping = (
            ("d" * 32, "2026-08-10T14:00:00+07:00"),
            ("a" * 32, "2026-08-10T14:30:00+07:00"),
            ("f" * 32, "2026-08-10T14:20:00+07:00"),
            ("1" * 32, "2026-08-10T14:40:00+07:00"),
        )
        for generation_id, cutoff in mapping:
            self._commit(generation_id, cutoff=cutoff)
        for index, (generation_id, _cutoff) in enumerate(reversed(mapping), start=10):
            os.utime(
                generation_cache_path(self.root / "catalog.sqlite3", generation_id),
                (index, index),
            )
        self._cleanup()
        self.assertFalse(generation_cache_path(self.root / "catalog.sqlite3", "d" * 32).exists())
        self.assertTrue(
            all(
                generation_cache_path(self.root / "catalog.sqlite3", item).exists()
                for item in ("a" * 32, "f" * 32, "1" * 32)
            )
        )

    def test_retention_05_old_valid_orphan_is_cleaned_after_next_commit(self):
        orphan_id = "9" * 32
        orphan = self._orphan(orphan_id, "2026-08-10T13:50:00+07:00")
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C)
        self._cleanup()
        self.assertFalse(orphan.exists())
        self.assertTrue(all(self._exists(item) for item in (self.GEN_A, self.GEN_B, self.GEN_C)))

    def test_retention_06_failed_or_uncommitted_sync_never_runs_cleanup(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C, self.GEN_D)

        class SourceFailureSynchronizer(CatalogSynchronizer):
            def _run_locked(self, attempt_at: str) -> dict:
                raise TransportError("SOURCE_TIMEOUT")

        before = {item: self._exists(item) for item in self.CUTOFFS}
        with patch(
            "integrations.kiot_public_catalog.sync.cleanup_generation_retention"
        ) as cleanup_mock:
            with self.assertRaises(TransportError):
                SourceFailureSynchronizer(
                    self._config(), logger=quiet_logger("retention-source-fail"), client=object()
                ).run()
            cleanup_mock.assert_not_called()
        self.assertEqual({item: self._exists(item) for item in self.CUTOFFS}, before)

    def test_retention_07_cleanup_is_after_commit_and_before_lock_exit(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C)
        events: list[str] = []
        outer = self

        class TrackingLock:
            held = False

            def __init__(self, _path: Path) -> None:
                pass

            def __enter__(self):
                type(self).held = True
                events.append("lock_enter")
                return self

            def __exit__(self, *_args):
                events.append("lock_exit")
                type(self).held = False

        class SyntheticSynchronizer(CatalogSynchronizer):
            def _run_locked(inner_self, attempt_at: str) -> dict:
                outer._commit(outer.GEN_D)
                events.append("status_committed")
                return {
                    "status": "PASS",
                    "retention": inner_self._apply_retention_locked(),
                }

        real_cleanup = cleanup_generation_retention

        def observed_cleanup(*args, **kwargs):
            self.assertTrue(TrackingLock.held)
            self.assertEqual(read_sync_status(self.root / "sync_status.json")["generation_id"], self.GEN_D)
            events.append("cleanup")
            return real_cleanup(*args, **kwargs)

        with patch("integrations.kiot_public_catalog.sync.SyncLock", TrackingLock), patch(
            "integrations.kiot_public_catalog.sync.cleanup_generation_retention",
            side_effect=observed_cleanup,
        ):
            SyntheticSynchronizer(
                self._config(), logger=quiet_logger("retention-order"), client=object()
            ).run()
        self.assertEqual(events, ["lock_enter", "status_committed", "cleanup", "lock_exit"])

    def test_retention_08_lock_busy_does_not_cleanup_or_mutate_status(self):
        self._seed(self.GEN_A)
        before = (self.root / "sync_status.json").read_bytes()
        with SyncLock(self.root / ".sync.lock"), patch(
            "integrations.kiot_public_catalog.sync.cleanup_generation_retention"
        ) as cleanup_mock:
            with self.assertRaisesRegex(ContractError, "SYNC_LOCK_BUSY"):
                CatalogSynchronizer(
                    self._config(), logger=quiet_logger("retention-busy"), client=object()
                ).run()
            cleanup_mock.assert_not_called()
        self.assertEqual((self.root / "sync_status.json").read_bytes(), before)

    def test_retention_09_cleanup_failure_keeps_new_pointer_fresh_and_warns(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C)
        stream = io.StringIO()
        logger = logging.getLogger("retention-cleanup-failure")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler(stream))
        synchronizer = self._commit_then_cleanup_synchronizer(self.GEN_D)
        synchronizer.logger = logger
        with patch(
            "integrations.kiot_public_catalog.sync.cleanup_generation_retention",
            side_effect=OSError("synthetic cleanup failure"),
        ):
            result = synchronizer.run()
        status = read_sync_status(self.root / "sync_status.json")
        self.assertEqual(status["generation_id"], self.GEN_D)
        self.assertFalse(status["stale"])
        self.assertIsNone(status["last_error_code"])
        self.assertEqual(result["retention"]["warning_code"], "RETENTION_CLEANUP_FAILED")
        self.assertIn("retention_warning code=RETENTION_CLEANUP_FAILED", stream.getvalue())
        self.assertNotIn(str(self.root), stream.getvalue())

    def test_retention_10_next_sync_retries_and_removes_cleanup_failure_leftovers(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C)
        with patch(
            "integrations.kiot_public_catalog.sync.cleanup_generation_retention",
            side_effect=OSError("synthetic cleanup failure"),
        ):
            self._commit_then_cleanup_synchronizer(self.GEN_D).run()
        self.assertEqual(sum(self._exists(item) for item in self.CUTOFFS), 4)
        result = self._commit_then_cleanup_synchronizer(self.GEN_E).run()
        self.assertEqual(result["retention"]["valid_after"], 3)
        self.assertTrue(all(self._exists(item) for item in (self.GEN_C, self.GEN_D, self.GEN_E)))
        self.assertFalse(self._exists(self.GEN_A))
        self.assertFalse(self._exists(self.GEN_B))

    def test_retention_11_symlink_is_not_followed_or_removed(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C, self.GEN_D)
        outside = self.root.parent / f"{self.root.name}-outside-target"
        outside.write_bytes(b"outside target")
        symlink = generation_cache_path(self.root / "catalog.sqlite3", self.GEN_E)
        symlink.symlink_to(outside)
        try:
            result = self._cleanup()
            self.assertTrue(symlink.is_symlink())
            self.assertTrue(outside.exists())
            self.assertIn("RETENTION_CANDIDATE_SKIPPED", result["warning_codes"])
        finally:
            symlink.unlink(missing_ok=True)
            outside.unlink(missing_ok=True)

    def test_retention_12_absolute_nested_and_traversal_candidates_are_rejected(self):
        self.root.mkdir(parents=True, exist_ok=True)
        valid_name = generation_cache_path(self.root / "catalog.sqlite3", self.GEN_A).name
        candidates = (
            f"../{valid_name}",
            f"nested/{valid_name}",
            str((self.root / valid_name).resolve()),
            f"..\\{valid_name}",
        )
        for candidate in candidates:
            with self.subTest(candidate_type=type(candidate).__name__):
                with self.assertRaisesRegex(ContractError, "RETENTION_CANDIDATE_PATH_REJECTED"):
                    _validated_generation_candidate_path(self.root / "catalog.sqlite3", candidate)

    def test_retention_13_foreign_and_malformed_files_are_preserved(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C, self.GEN_D)
        files = {
            self.root / ".env": b"placeholder-only",
            self.root / ".sync.lock": b"",
            self.root / "catalog.log": b"runtime-like fixture",
            self.root / "backup.sqlite3": b"backup fixture",
            self.root / "catalog.sqlite3": b"legacy base fixture",
            generation_cache_path(self.root / "catalog.sqlite3", self.GEN_E): b"not sqlite",
        }
        for path, body in files.items():
            path.write_bytes(body)
        status_before = (self.root / "sync_status.json").read_bytes()
        self._cleanup()
        for path, body in files.items():
            self.assertEqual(path.read_bytes(), body)
        self.assertEqual((self.root / "sync_status.json").read_bytes(), status_before)

    def test_retention_14_missing_blank_and_non_integer_config_fail_closed(self):
        for value in (None, "", "   ", "3.0", "abc", "nan"):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True):
                if value is not None:
                    os.environ["KIOT_CATALOG_RETAIN_GENERATIONS"] = value
                with self.assertRaises(ConfigurationError):
                    load_retain_generations()

    def test_retention_15_below_minimum_and_above_safety_ceiling_are_rejected(self):
        for value in ("-1", "0", "1", str(MAX_RETAIN_GENERATIONS + 1), "1000"):
            with self.subTest(value=value), patch.dict(
                os.environ,
                {"KIOT_CATALOG_RETAIN_GENERATIONS": value},
                clear=True,
            ):
                with self.assertRaises(ConfigurationError):
                    load_retain_generations()
        for value in ("2", "3", str(MAX_RETAIN_GENERATIONS)):
            with self.subTest(valid=value), patch.dict(
                os.environ,
                {"KIOT_CATALOG_RETAIN_GENERATIONS": value},
                clear=True,
            ):
                self.assertEqual(load_retain_generations(), int(value))

    def test_retention_16_concurrent_skip_cannot_delete_or_roll_back_authority(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C, self.GEN_D)
        before = (self.root / "sync_status.json").read_bytes()
        with SyncLock(self.root / ".sync.lock"), patch(
            "integrations.kiot_public_catalog.sync.cleanup_generation_retention"
        ) as skipped_cleanup:
            with self.assertRaisesRegex(ContractError, "SYNC_LOCK_BUSY"):
                CatalogSynchronizer(
                    self._config(), logger=quiet_logger("retention-concurrent"), client=object()
                ).run()
            skipped_cleanup.assert_not_called()
            self.assertEqual((self.root / "sync_status.json").read_bytes(), before)
            self._commit(self.GEN_E)
            cleanup_generation_retention(
                self.root / "catalog.sqlite3", self.root / "sync_status.json", 3
            )
        status = read_sync_status(self.root / "sync_status.json")
        self.assertEqual(status["generation_id"], self.GEN_E)
        self.assertTrue(self._exists(self.GEN_E))

    def test_retention_17_health_public_internal_serve_d_after_cleanup(self):
        self._seed(self.GEN_A, self.GEN_B, self.GEN_C)
        self._commit(self.GEN_D, code="LATEST-D")
        self._cleanup()
        with ApiHarness(
            self.root / "catalog.sqlite3",
            self.root / "sync_status.json",
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
        ) as api:
            health = api.request("GET", "/health")[0]
            public_status, public, _headers = api.request(
                "GET", "/v1/catalog/products", WEBSITE_KEY
            )
            internal_status, internal, _headers = api.request(
                "GET", "/v1/internal/products", INTERNAL_KEY
            )
        self.assertEqual(health, 200)
        self.assertEqual(public_status, 200)
        self.assertEqual(internal_status, 200)
        self.assertEqual([row["code"] for row in public["items"]], ["LATEST-D"])
        self.assertEqual([row["code"] for row in internal["items"]], ["LATEST-D"])

    def test_retention_18_freshness_boundary_10800_and_10801_seconds(self):
        cutoff = "2026-08-11T06:00:00+07:00"
        cache_path, status_path = initialize_cache(self.root, data_as_of=cutoff)
        boundary_now = dt.datetime.fromisoformat("2026-08-11T09:00:00+07:00")
        self.assertEqual(
            CacheReader(
                cache_path,
                status_path,
                max_cache_age_seconds=10_800,
                now=boundary_now,
            ).status["data_as_of"],
            cutoff,
        )
        with self.assertRaisesRegex(CacheUnavailable, "CACHE_TOO_OLD"):
            CacheReader(
                cache_path,
                status_path,
                max_cache_age_seconds=10_800,
                now=boundary_now + dt.timedelta(seconds=1),
            )

    def test_retention_19_publication_auth_sale_branch_and_schema_do_not_regress(self):
        records = [
            record_for("ELIGIBLE"),
            record_for("MISSING", has_sale_row=False),
            record_for("INACTIVE", active=False),
        ]
        cache_path, status_path = initialize_cache(self.root, records=records)
        contract = resolve_live_contract(FakeResolverClient())
        self.assertEqual(contract.pricebook_name, "SALE")
        self.assertEqual({branch.slug for branch in contract.branches}, set(BRANCH_SLUGS))
        with ApiHarness(
            cache_path,
            status_path,
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
        ) as api:
            public_status, public, _headers = api.request(
                "GET", "/v1/catalog/products", WEBSITE_KEY
            )
            internal_status, internal, _headers = api.request(
                "GET", "/v1/internal/products", INTERNAL_KEY
            )
            forbidden = api.request("GET", "/v1/internal/products", WEBSITE_KEY)[0]
        self.assertEqual(public_status, 200)
        self.assertEqual([row["code"] for row in public["items"]], ["ELIGIBLE"])
        self.assertNotIn("inventory", public["items"][0])
        self.assertEqual(internal_status, 200)
        self.assertEqual(internal["total"], 3)
        self.assertEqual(forbidden, 403)
        self.assertEqual(set(public["items"][0]), set(CATALOG_RESPONSE_FIELDS))

    def test_retention_20_fault_windows_preserve_coherent_authority_and_recover(self):
        precommit_root = self.root / "precommit"
        original_root = self.root
        self.root = precommit_root
        try:
            self._seed(self.GEN_A, self.GEN_B, self.GEN_C)
            with self.assertRaisesRegex(RuntimeError, "INJECTED_PRECOMMIT_CRASH"):
                self._commit(
                    self.GEN_D,
                    fault_injector=lambda point: (
                        (_ for _ in ()).throw(RuntimeError("INJECTED_PRECOMMIT_CRASH"))
                        if point == "before_status_commit"
                        else None
                    ),
                )
            self.assertFalse(self._exists(self.GEN_D))
            self.assertEqual(read_sync_status(self.root / "sync_status.json")["generation_id"], self.GEN_C)
        finally:
            self.root = original_root

        after_commit_root = self.root / "after-commit"
        self.root = after_commit_root
        try:
            self._seed(self.GEN_A, self.GEN_B, self.GEN_C)
            self._commit(self.GEN_D)
            self.assertEqual(read_sync_status(self.root / "sync_status.json")["generation_id"], self.GEN_D)
            self.assertEqual(sum(self._exists(item) for item in (self.GEN_A, self.GEN_B, self.GEN_C, self.GEN_D)), 4)
            reader = CacheReader(
                self.root / "catalog.sqlite3",
                self.root / "sync_status.json",
                max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
                now=TEST_NOW,
            )
            self.assertEqual(reader.status["generation_id"], self.GEN_D)
        finally:
            self.root = original_root

        between_unlinks_root = self.root / "between-unlinks"
        self.root = between_unlinks_root
        try:
            self._seed(self.GEN_A, self.GEN_B, self.GEN_C, self.GEN_D, self.GEN_E)
            injected = {"done": False}

            def fail_after_first_unlink(point: str) -> None:
                if point == "after_unlink" and not injected["done"]:
                    injected["done"] = True
                    raise RuntimeError("INJECTED_BETWEEN_UNLINKS")

            with self.assertRaisesRegex(RuntimeError, "INJECTED_BETWEEN_UNLINKS"):
                self._cleanup(fault_injector=fail_after_first_unlink)
            self.assertTrue(self._exists(self.GEN_E))
            self.assertEqual(read_sync_status(self.root / "sync_status.json")["generation_id"], self.GEN_E)
            self.assertGreaterEqual(sum(self._exists(item) for item in self.CUTOFFS), 3)
            recovered = self._cleanup()
            self.assertEqual(recovered["valid_after"], 3)
            self.assertTrue(all(self._exists(item) for item in (self.GEN_C, self.GEN_D, self.GEN_E)))
        finally:
            self.root = original_root

    def test_retention_21_audit_supports_isolated_data_and_log_directories(self):
        isolated = self.root / "isolated"
        data_root = isolated / "data"
        log_root = isolated / "logs"
        secrets_path = isolated / "secrets.env"
        cache_path, status_path = initialize_cache(
            data_root, data_as_of=DATA_AS_OF
        )
        log_root.mkdir(parents=True)
        log_root.chmod(0o700)
        log_path = log_root / "catalog_sync.log"
        log_path.write_text("sanitized fixture\n", encoding="utf-8")
        log_path.chmod(0o600)
        lock_path = data_root / ".sync.lock"
        lock_path.write_bytes(b"")
        lock_path.chmod(0o600)
        secrets_path.write_text(
            "KV_RETAILER=fixture-retailer\n"
            "KV_CLIENT_ID=fixture-client-id\n"
            "KV_CLIENT_SECRET=" + "-".join(("fixture", "client", "secret")) + "\n",
            encoding="utf-8",
        )
        secrets_path.chmod(0o600)
        config = SyncConfig(
            secrets_path=secrets_path,
            cache_path=cache_path,
            status_path=status_path,
            lock_path=lock_path,
            log_path=log_path,
            retain_generations=3,
        )
        result = audit_artifacts(
            config,
            max_cache_age_seconds=TEST_MAX_CACHE_AGE_SECONDS,
            now=TEST_NOW,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
