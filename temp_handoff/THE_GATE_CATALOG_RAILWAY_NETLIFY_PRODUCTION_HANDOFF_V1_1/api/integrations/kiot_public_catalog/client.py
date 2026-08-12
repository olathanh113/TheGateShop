from __future__ import annotations

import logging
import re
import time
from collections.abc import Iterator, Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

import requests

from .contracts import API_ORIGIN, TOKEN_SCOPE, TOKEN_URL
from .errors import ContractError, TransportError
from .secrets import load_kiotviet_credentials


_PRICEBOOK_DETAIL_RE = re.compile(r"/pricebooks/\d+\Z")
_BUSINESS_PATHS = frozenset({"/branches", "/pricebooks", "/products"})


class KiotVietClient:
    """Transport-enforced client: one auth POST class and GET-only business calls."""

    def __init__(
        self,
        *,
        secrets_path: Any,
        logger: logging.Logger,
        timeout_seconds: float = 60.0,
        attempts: int = 4,
        min_interval_seconds: float = 0.12,
        session: requests.Session | None = None,
        sleeper: Any = time.sleep,
    ) -> None:
        credentials = load_kiotviet_credentials(secrets_path)
        self._retailer = credentials["KV_RETAILER"]
        self._client_id = credentials["KV_CLIENT_ID"]
        self._client_secret = credentials["KV_CLIENT_SECRET"]
        credentials = None
        self._token: str | None = None
        self._logger = logger
        self._timeout = (10.0, float(timeout_seconds))
        self._attempts = max(1, int(attempts))
        self._min_interval = max(0.0, float(min_interval_seconds))
        self._sleep = sleeper
        self._last_request_at = 0.0
        self._session = session or requests.Session()
        self._session.trust_env = False
        self._session.headers.update({"User-Agent": "TheGate-KiotCatalog/1.0"})
        self.call_ledger: list[dict[str, Any]] = []

    @staticmethod
    def _validate_token_url() -> None:
        parsed = urlparse(TOKEN_URL)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "id.kiotviet.vn"
            or parsed.path != "/connect/token"
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise TransportError("TOKEN_URL_POLICY_VIOLATION")

    @staticmethod
    def _validate_business_path(path: str) -> None:
        if path not in _BUSINESS_PATHS and not _PRICEBOOK_DETAIL_RE.fullmatch(path):
            raise TransportError("BUSINESS_PATH_POLICY_VIOLATION")

    @staticmethod
    def _redirect_observed(response: requests.Response) -> bool:
        return 300 <= response.status_code < 400 or "Location" in response.headers

    def _record_call(self, method: str, path: str, status: int) -> None:
        self.call_ledger.append({"method": method, "path": path, "status": status})
        self._logger.info("kv_call method=%s path=%s status=%s", method, path, status)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self._min_interval - elapsed
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = time.monotonic()

    def _authenticate(self) -> str:
        if self._token:
            return self._token
        self._validate_token_url()
        response: requests.Response | None = None
        for attempt in range(1, self._attempts + 1):
            try:
                response = self._session.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "client_credentials",
                        "scopes": TOKEN_SCOPE,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                if attempt == self._attempts:
                    raise TransportError("TOKEN_NETWORK_OR_TLS_ERROR") from exc
                self._sleep(min(30.0, float(2**attempt)))
                continue
            self._record_call("POST", "/connect/token", response.status_code)
            if self._redirect_observed(response):
                raise TransportError("TOKEN_REDIRECT_REJECTED")
            if response.status_code == 200:
                try:
                    token = response.json().get("access_token")
                except Exception as exc:
                    raise TransportError("TOKEN_RESPONSE_NOT_JSON") from exc
                if not isinstance(token, str) or not token:
                    raise TransportError("TOKEN_MISSING_IN_RESPONSE")
                self._token = token
                return token
            if response.status_code not in (429, 500, 502, 503, 504):
                raise TransportError(f"TOKEN_HTTP_{response.status_code}")
            if attempt < self._attempts:
                self._sleep(min(30.0, float(2**attempt)))
        raise TransportError("TOKEN_RETRY_EXHAUSTED")

    def get(
        self,
        path: str,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self._validate_business_path(path)
        url = API_ORIGIN + path
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "public.kiotapi.com"
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise TransportError("BUSINESS_URL_POLICY_VIOLATION")
        refreshed = False
        for attempt in range(1, self._attempts + 1):
            self._throttle()
            token = self._authenticate()
            try:
                response = self._session.get(
                    url,
                    params=params,
                    headers={
                        "Retailer": self._retailer,
                        "Authorization": "Bearer " + token,
                    },
                    timeout=self._timeout,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                if attempt == self._attempts:
                    raise TransportError("BUSINESS_NETWORK_OR_TLS_ERROR") from exc
                self._sleep(min(30.0, float(2**attempt)))
                continue
            self._record_call("GET", path, response.status_code)
            if self._redirect_observed(response):
                raise TransportError("BUSINESS_REDIRECT_REJECTED")
            if response.status_code == 200:
                try:
                    payload = response.json()
                except Exception as exc:
                    raise TransportError("BUSINESS_RESPONSE_NOT_JSON") from exc
                if not isinstance(payload, dict):
                    raise TransportError("BUSINESS_RESPONSE_NOT_OBJECT")
                return payload
            if response.status_code == 401 and not refreshed:
                self._token = None
                refreshed = True
                continue
            if response.status_code not in (429, 500, 502, 503, 504):
                raise TransportError(f"BUSINESS_HTTP_{response.status_code}")
            if attempt < self._attempts:
                self._sleep(min(30.0, float(2**attempt)))
        raise TransportError("BUSINESS_RETRY_EXHAUSTED")

    def paginate(
        self,
        path: str,
        params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        *,
        page_size: int = 100,
        max_pages: int = 2000,
    ) -> Iterator[tuple[list[dict[str, Any]], int, int]]:
        """Yield pages while requiring a stable total and unique source IDs."""
        page_size = min(100, max(1, int(page_size)))
        base_items = list(params.items()) if isinstance(params, Mapping) else list(params or ())
        current = 0
        first_total: int | None = None
        seen: set[str] = set()
        for page_number in range(1, max_pages + 1):
            call_params = base_items + [
                ("pageSize", page_size),
                ("currentItem", current),
            ]
            payload = self.get(path, call_params)
            batch = payload.get("data") or []
            total = payload.get("total")
            if not isinstance(batch, list) or not isinstance(total, int) or total < 0:
                raise ContractError("PAGINATION_SCHEMA_INVALID")
            if first_total is None:
                first_total = total
            elif total != first_total:
                raise ContractError("PAGINATION_TOTAL_DRIFT")
            for row in batch:
                if not isinstance(row, dict):
                    raise ContractError("PAGINATION_ROW_NOT_OBJECT")
                marker = row.get("id", row.get("productId"))
                if marker is None:
                    raise ContractError("PAGINATION_SOURCE_ID_MISSING")
                marker_text = str(marker)
                if marker_text in seen:
                    raise ContractError("PAGINATION_DUPLICATE_SOURCE_ID")
                seen.add(marker_text)
            yield batch, total, page_number
            current += len(batch)
            if current >= total:
                if current != total:
                    raise ContractError("PAGINATION_TOTAL_MISMATCH")
                return
            if not batch:
                raise ContractError("PAGINATION_PREMATURE_EMPTY_PAGE")
        raise ContractError("PAGINATION_MAX_PAGES_REACHED")

    def clear_token(self) -> None:
        self._token = None

