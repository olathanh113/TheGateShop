from __future__ import annotations

import json

from integrations.kiot_public_catalog.errors import CatalogError
from integrations.kiot_public_catalog.railway_runtime import (
    load_railway_runtime_settings,
    prepare_railway_environment,
    validate_railway_preflight,
)


def main() -> int:
    try:
        prepare_railway_environment()
        summary = validate_railway_preflight(load_railway_runtime_settings())
        print(json.dumps(summary, sort_keys=True))
        return 0
    except CatalogError as exc:
        print(json.dumps({"status": "FAILED", "error_code": exc.code}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
