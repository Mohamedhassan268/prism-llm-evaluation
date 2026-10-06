"""Canonical identities and atomic research records."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def identity(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".prismqa-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def inside(root: Path, path: str | Path) -> Path:
    """Reject traversal and symlink escapes before accessing project-owned records."""
    base = root.resolve()
    candidate = (base / path).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(f"Path leaves the project: {path}")
    return candidate


def validate_records(records: Any) -> list[dict]:
    if not isinstance(records, list) or not records:
        raise ValueError("Dataset must contain at least one record")
    identifiers: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each dataset record must be an object")
        for field in ("id", "source_code", "source_language", "target_language"):
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise ValueError(f"Record requires nonempty {field}")
        if not isinstance(record.get("raw_output"), str):
            raise ValueError("Raw output must be a string; empty generations remain eligible")
        if record["id"] in identifiers:
            raise ValueError(f"Duplicate record ID: {record['id']}")
        identifiers.add(record["id"])
        tests = record.get("original_tests")
        if not isinstance(tests, list) or not tests:
            raise ValueError("Each record requires original_tests")
        for test in tests:
            if not isinstance(test, dict) or not all(
                isinstance(test.get(field), str) for field in ("input", "expected")
            ):
                raise ValueError("Test input and expected output must be strings")
        if record.get("data_kind") not in (
            "controlled_fixture",
            "authors_saved_outputs",
            "authors_source_control",
        ):
            raise ValueError("Record must declare its data_kind")
    return records
