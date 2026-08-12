from __future__ import annotations

from pathlib import Path

from .config import verify_secret_file
from .errors import ConfigurationError


REQUIRED_KEYS = ("KV_RETAILER", "KV_CLIENT_ID", "KV_CLIENT_SECRET")
PLACEHOLDER_MARKS = (
    "PUT_",
    "_HERE",
    "YOUR_",
    "CHANGE_ME",
    "REPLACE_ME",
    "PLACEHOLDER",
)


def load_kiotviet_credentials(path: Path) -> dict[str, str]:
    """Load the existing external store without logging or copying its values."""
    verify_secret_file(path)
    parsed: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ConfigurationError("SECRET_STORE_MALFORMED_LINE")
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    missing = [key for key in REQUIRED_KEYS if not parsed.get(key)]
    if missing:
        raise ConfigurationError("REQUIRED_KIOTVIET_CREDENTIAL_MISSING")
    if any(
        marker in parsed[key].upper()
        for key in REQUIRED_KEYS
        for marker in PLACEHOLDER_MARKS
    ):
        raise ConfigurationError("KIOTVIET_CREDENTIAL_IS_PLACEHOLDER")
    return {key: parsed[key] for key in REQUIRED_KEYS}
