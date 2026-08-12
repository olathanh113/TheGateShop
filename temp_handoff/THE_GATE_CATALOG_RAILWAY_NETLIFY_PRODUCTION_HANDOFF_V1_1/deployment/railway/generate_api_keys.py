from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create two distinct API keys in a private file")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output).expanduser()
    if not target.is_absolute() or target.exists() or target.is_symlink():
        raise SystemExit("OUTPUT_MUST_BE_NEW_ABSOLUTE_FILE")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.parent.chmod(0o700)
    website = secrets.token_urlsafe(48)
    internal = secrets.token_urlsafe(48)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(f"KIOT_CATALOG_WEBSITE_API_KEY={website}\n")
        handle.write(f"KIOT_CATALOG_INTERNAL_API_KEY={internal}\n")
        handle.flush()
        os.fsync(handle.fileno())
    print("keys_written=YES mode=0600 values_printed=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
