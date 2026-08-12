from __future__ import annotations

import datetime as dt
import hmac
import json
import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .cache import CacheReader
from .config import ApiConfig, validate_bind
from .contracts import CATALOG_RESPONSE_FIELDS, INTERNAL_RESPONSE_FIELDS
from .errors import CacheUnavailable
from .website_catalog import WebsiteCatalogStore


class RateLimiter:
    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, bucket: str) -> bool:
        now = time.monotonic()
        threshold = now - 60.0
        with self._lock:
            events = self._events[bucket]
            while events and events[0] <= threshold:
                events.popleft()
            if len(events) >= self.per_minute:
                return False
            events.append(now)
            return True


def filter_record(record: dict[str, Any], *, internal: bool) -> dict[str, Any]:
    fields = INTERNAL_RESPONSE_FIELDS if internal else CATALOG_RESPONSE_FIELDS
    return {field: record[field] for field in fields}


class CatalogApplication:
    def __init__(
        self,
        config: ApiConfig,
        logger: logging.Logger,
        *,
        now_provider: Callable[[], dt.datetime] | None = None,
        website_store: WebsiteCatalogStore | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.now_provider = now_provider
        self.rate_limiter = RateLimiter(config.rate_limit_per_minute)
        self.website_rate_limiter = RateLimiter(config.website_rate_limit_per_minute)
        self.website_store = website_store or WebsiteCatalogStore(
            config.website_catalog_path,
            config.website_catalog_status_path,
            max_age_seconds=config.website_catalog_max_age_seconds,
            source_max_age_seconds=config.max_cache_age_seconds,
            max_products=config.website_catalog_max_products,
            max_response_bytes=config.website_catalog_max_response_bytes,
            now_provider=now_provider or (lambda: dt.datetime.now(dt.timezone.utc)),
        )

    def authenticate(self, supplied: str, *, internal: bool) -> tuple[bool, str]:
        if not supplied:
            return False, "missing"
        website_match = hmac.compare_digest(supplied, self.config.website_api_key)
        internal_match = hmac.compare_digest(supplied, self.config.internal_api_key)
        if internal:
            return (internal_match, "internal" if internal_match else "forbidden")
        if website_match:
            return True, "website"
        if internal_match:
            return True, "internal"
        return False, "forbidden"

    def reader(self) -> CacheReader:
        return CacheReader(
            self.config.cache_path,
            self.config.status_path,
            max_cache_age_seconds=self.config.max_cache_age_seconds,
            now=self.now_provider() if self.now_provider is not None else None,
        )


def make_handler(application: CatalogApplication) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "TheGateCatalog"
        sys_version = ""

        def log_message(self, _format: str, *_args: Any) -> None:
            return

        def _send(
            self,
            status: int,
            payload: dict[str, Any],
            *,
            cache_control: str = "no-store",
        ) -> None:
            body = json.dumps(
                payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache_control)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _send_website(self, body: bytes, etag: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=60, stale-if-error=300")
            self.send_header("ETag", etag)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _send_not_modified(self, etag: str) -> None:
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.send_header("Cache-Control", "public, max-age=60, stale-if-error=300")
            self.send_header("ETag", etag)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.end_headers()

        def _request_log(self, status: int, role: str, path: str) -> None:
            logged_path = path
            for prefix in ("/v1/catalog/products", "/v1/internal/products"):
                if path.startswith(prefix + "/"):
                    logged_path = prefix + "/{code}"
                    break
            application.logger.info(
                "api_request method=%s path=%s status=%s role=%s",
                self.command,
                logged_path,
                status,
                role,
            )

        def _reject_non_get(self) -> None:
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "GET")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            body = b'{"error":"method_not_allowed"}'
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            self._request_log(HTTPStatus.METHOD_NOT_ALLOWED, "none", urlsplit(self.path).path)

        do_POST = _reject_non_get
        do_PUT = _reject_non_get
        do_PATCH = _reject_non_get
        do_DELETE = _reject_non_get
        do_OPTIONS = _reject_non_get
        do_HEAD = _reject_non_get

        def _authorize(self, *, internal: bool, path: str) -> str | None:
            bucket = f"{self.client_address[0]}:protected"
            if not application.rate_limiter.allow(bucket):
                self._send(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
                self._request_log(HTTPStatus.TOO_MANY_REQUESTS, "limited", path)
                return None
            supplied = self.headers.get("X-API-Key", "")
            allowed, role = application.authenticate(supplied, internal=internal)
            if not allowed:
                status = (
                    HTTPStatus.UNAUTHORIZED
                    if role == "missing"
                    else HTTPStatus.FORBIDDEN
                )
                self._send(status, {"error": "authentication_required" if role == "missing" else "forbidden"})
                self._request_log(status, role, path)
                return None
            return role

        def _pagination(self, query: str) -> tuple[int, int] | None:
            parsed = parse_qs(query, keep_blank_values=True)
            if set(parsed) - {"page", "page_size"}:
                self._send(HTTPStatus.BAD_REQUEST, {"error": "unsupported_query_parameter"})
                return None
            try:
                page = int(parsed.get("page", ["1"])[0])
                page_size = int(parsed.get("page_size", ["50"])[0])
            except (TypeError, ValueError):
                self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid_pagination"})
                return None
            if page < 1 or page_size < 1 or page_size > application.config.max_page_size:
                self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid_pagination"})
                return None
            return page, page_size

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/livez":
                if parsed.query:
                    self._send(HTTPStatus.BAD_REQUEST, {"error": "query_not_allowed"})
                    self._request_log(HTTPStatus.BAD_REQUEST, "liveness", path)
                    return
                self._send(HTTPStatus.OK, {"status": "alive"})
                self._request_log(HTTPStatus.OK, "liveness", path)
                return

            if path == "/v1/website/catalog":
                if parsed.query:
                    self._send(HTTPStatus.BAD_REQUEST, {"error": "query_not_allowed"})
                    self._request_log(HTTPStatus.BAD_REQUEST, "website", path)
                    return
                bucket = f"{self.client_address[0]}:website"
                if not application.website_rate_limiter.allow(bucket):
                    self._send(HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
                    self._request_log(HTTPStatus.TOO_MANY_REQUESTS, "website", path)
                    return
                try:
                    _payload, body, etag = application.website_store.read()
                except CacheUnavailable:
                    self._send(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        {"error": "website_catalog_unavailable"},
                    )
                    self._request_log(HTTPStatus.SERVICE_UNAVAILABLE, "website", path)
                    return
                if self.headers.get("If-None-Match") == etag:
                    self._send_not_modified(etag)
                    self._request_log(HTTPStatus.NOT_MODIFIED, "website", path)
                    return
                self._send_website(body, etag)
                self._request_log(HTTPStatus.OK, "website", path)
                return

            if path == "/health":
                bucket = f"{self.client_address[0]}:health"
                if not application.rate_limiter.allow(bucket):
                    self._send(HTTPStatus.TOO_MANY_REQUESTS, {"status": "degraded"})
                    self._request_log(HTTPStatus.TOO_MANY_REQUESTS, "health", path)
                    return
                try:
                    reader = application.reader()
                    status = "degraded" if reader.status["stale"] else "ok"
                    self._send(HTTPStatus.OK, {"status": status})
                    self._request_log(HTTPStatus.OK, "health", path)
                except CacheUnavailable:
                    self._send(HTTPStatus.SERVICE_UNAVAILABLE, {"status": "unavailable"})
                    self._request_log(HTTPStatus.SERVICE_UNAVAILABLE, "health", path)
                return

            catalog_prefix = "/v1/catalog/products"
            internal_prefix = "/v1/internal/products"
            is_internal = path == internal_prefix or path.startswith(internal_prefix + "/")
            is_catalog = path == catalog_prefix or path.startswith(catalog_prefix + "/")
            if not is_internal and not is_catalog:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                self._request_log(HTTPStatus.NOT_FOUND, "none", path)
                return
            role = self._authorize(internal=is_internal, path=path)
            if role is None:
                return
            try:
                reader = application.reader()
            except CacheUnavailable:
                self._send(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "cache_unavailable"})
                self._request_log(HTTPStatus.SERVICE_UNAVAILABLE, role, path)
                return

            prefix = internal_prefix if is_internal else catalog_prefix
            if path == prefix:
                pagination = self._pagination(parsed.query)
                if pagination is None:
                    self._request_log(HTTPStatus.BAD_REQUEST, role, path)
                    return
                page, page_size = pagination
                records, total = reader.list_records(
                    offset=(page - 1) * page_size,
                    limit=page_size,
                    public_only=not is_internal,
                )
                payload = {
                    "items": [
                        filter_record(record, internal=is_internal) for record in records
                    ],
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                    "data_as_of": reader.status["data_as_of"],
                    "stale": reader.status["stale"],
                }
                self._send(HTTPStatus.OK, payload)
                self._request_log(HTTPStatus.OK, role, path)
                return

            if parsed.query:
                self._send(HTTPStatus.BAD_REQUEST, {"error": "query_not_allowed"})
                self._request_log(HTTPStatus.BAD_REQUEST, role, path)
                return
            code = unquote(path[len(prefix) + 1 :])
            if not code or "/" in code or len(code) > 200:
                self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid_product_code"})
                self._request_log(HTTPStatus.BAD_REQUEST, role, path)
                return
            record = reader.get_record(code, public_only=not is_internal)
            if record is None:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                self._request_log(HTTPStatus.NOT_FOUND, role, path)
                return
            self._send(HTTPStatus.OK, filter_record(record, internal=is_internal))
            self._request_log(HTTPStatus.OK, role, path)

    return Handler


def create_server(
    config: ApiConfig,
    logger: logging.Logger,
    *,
    port_override: int | None = None,
    now_provider: Callable[[], dt.datetime] | None = None,
    website_store: WebsiteCatalogStore | None = None,
) -> ThreadingHTTPServer:
    validate_bind(config.host, config.deployment_mode)
    port = config.port if port_override is None else port_override
    application = CatalogApplication(
        config,
        logger,
        now_provider=now_provider,
        website_store=website_store,
    )
    return ThreadingHTTPServer((config.host, port), make_handler(application))


def serve(config: ApiConfig, logger: logging.Logger) -> None:
    server = create_server(config, logger)
    logger.info("api_started host=%s port=%s", config.host, config.port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        logger.info("api_stopped")
