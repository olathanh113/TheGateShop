#!/usr/bin/env python3
"""Safely merge the one approved catalog proxy into an existing _redirects file."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit


CATALOG_SOURCE = "/api/catalog"
CATALOG_TARGET_PATH = "/v1/website/catalog"
_HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def _approved_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or not _HOST_RE.fullmatch(parsed.hostname)
    ):
        raise ValueError("RAILWAY_ORIGIN_INVALID")
    if parsed.port is not None:
        raise ValueError("RAILWAY_ORIGIN_PORT_REJECTED")
    return f"https://{parsed.hostname}"


def merge_redirects(existing: bytes, railway_origin: str) -> bytes:
    origin = _approved_origin(railway_origin)
    try:
        text = existing.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("REDIRECTS_NOT_UTF8") from exc
    newline = "\r\n" if "\r\n" in text else "\n"
    preserved: list[str] = []
    for line in text.splitlines():
        tokens = line.strip().split()
        if tokens and tokens[0] == CATALOG_SOURCE:
            continue
        preserved.append(line)
    rule = f"{CATALOG_SOURCE}  {origin}{CATALOG_TARGET_PATH}  200!"
    insert_at = len(preserved)
    for index, line in enumerate(preserved):
        tokens = line.strip().split()
        if tokens and tokens[0] == "/*":
            insert_at = index
            break
    preserved.insert(insert_at, rule)
    return (newline.join(preserved) + newline).encode("utf-8")


def _atomic_write(path: Path, body: bytes) -> None:
    temp = path.with_name(f".{path.name}.catalog-v1-1.tmp.{os.getpid()}")
    descriptor = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        if hasattr(os, "O_DIRECTORY"):
            try:
                directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                pass
    finally:
        if temp.exists() and not temp.is_symlink():
            temp.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge exact The Gate catalog Netlify rule")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--railway-origin", required=True)
    args = parser.parse_args(argv)
    candidate = args.file.expanduser()
    if not candidate.is_absolute() or candidate.is_symlink():
        print("status=FAILED code=REDIRECTS_TARGET_UNSAFE", file=sys.stderr)
        return 2
    target = candidate.resolve()
    if target.name != "_redirects" or not target.is_file() or target.is_symlink():
        print("status=FAILED code=REDIRECTS_TARGET_UNSAFE", file=sys.stderr)
        return 2
    try:
        before = target.read_bytes()
        after = merge_redirects(before, args.railway_origin)
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.with_name(f"_redirects.backup.{timestamp}")
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(before)
            handle.flush()
            os.fsync(handle.fileno())
        _atomic_write(target, after)
    except (OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, ValueError) else "REDIRECTS_MERGE_IO_FAILED"
        print(f"status=FAILED code={code}", file=sys.stderr)
        return 2
    print(f"status=PASS backup={backup.name} rule=EXACT_CATALOG_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
