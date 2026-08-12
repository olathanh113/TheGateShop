from __future__ import annotations


class CatalogError(RuntimeError):
    """Fail-closed error carrying only a non-sensitive code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ConfigurationError(CatalogError):
    pass


class TransportError(CatalogError):
    pass


class ContractError(CatalogError):
    pass


class CacheUnavailable(CatalogError):
    pass

