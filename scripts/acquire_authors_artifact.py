"""Acquire and verify pinned artifacts without executing or extracting them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

REPOSITORY = "RISElabQueens/forge24-code-translation"
COMMIT = "036135a1ba6d4cd7f0562058bea0912381a0f3e9"
ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "authors" / COMMIT
MANIFEST = ROOT / "data" / "manifests" / "authors_artifacts.json"
BUDGET = 2 * 1024**3
FREE_FLOOR = 5 * 1024**3
EXPANDED_LIMIT = 1024**3
FILES = (
    "LICENSE",
    "README.md",
    "Preliminary/dataset_after_processing.csv",
    "Preliminary/process_dataset.ipynb",
    "RQ3/rq3_files.zip",
    "RQ4/rq4_extend_codenet_dataset.ipynb",
    "RQ4/rq4_metrics_analysis.ipynb",
    "Prompt Templates/Control/CodeLlama.txt",
    "Prompt Templates/Control/Magicoder.txt",
    "Prompt Templates/Control/Mixtral.txt",
    "Prompt Templates/Control/Wizard.txt",
    "Prompt Templates/Reference/Reference.txt",
    "Prompt Templates/Vanilla/CodeLlama.txt",
    "Prompt Templates/Vanilla/Magicoder.txt",
    "Prompt Templates/Vanilla/Mixtral.txt",
    "Prompt Templates/Vanilla/Wizard.txt",
)


def request(url: str):
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("Only HTTPS artifact sources are supported")
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "PRISM-QA-artifact-audit"}),
        timeout=60,
    )


def hashes(path: Path) -> tuple[str, str]:
    sha256 = hashlib.sha256()
    blob = hashlib.sha1(usedforsecurity=False)
    blob.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            sha256.update(block)
            blob.update(block)
    return sha256.hexdigest(), blob.hexdigest()


def cache_bytes() -> int:
    return sum(p.stat().st_size for p in (ROOT / "data" / "cache").rglob("*") if p.is_file())


def acquire(relative: str, metadata: dict) -> dict:
    destination = CACHE / relative
    source = f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/" + urllib.parse.quote(
        relative
    )
    size = metadata["size"]
    if destination.exists():
        digest, blob = hashes(destination)
        if destination.stat().st_size != size or blob != metadata["sha"]:
            raise ValueError(f"Existing original differs from pinned Git blob: {relative}")
    else:
        if cache_bytes() + size > BUDGET or shutil.disk_usage(ROOT).free - size < FREE_FLOOR:
            raise ValueError("Acquisition would violate artifact budget or free-space floor")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".part")
        # Never overwrite a partial file from an earlier interrupted acquisition.
        with request(source) as response, temporary.open("xb") as output:
            written = 0
            while block := response.read(1024 * 1024):
                written += len(block)
                if written > size:
                    raise ValueError("Response exceeds pinned file size")
                output.write(block)
        digest, blob = hashes(temporary)
        if written != size or blob != metadata["sha"]:
            raise ValueError(f"Pinned Git blob verification failed: {relative}")
        temporary.rename(destination)
    os.chmod(destination, stat.S_IREAD)
    return {
        "repository_path": relative,
        "path": destination.relative_to(ROOT).as_posix(),
        "source_url": source,
        "git_commit": COMMIT,
        "git_blob_sha1": blob,
        "sha256": digest,
        "bytes": size,
        "license": "MIT (repository); upstream dataset provenance requires separate review",
    }


def inspect_zip(path: Path) -> dict:
    members = []
    total = 0
    with zipfile.ZipFile(path) as archive:
        names: set[str] = set()
        for item in archive.infolist():
            name = item.filename
            normalized = PurePosixPath(name)
            mode = item.external_attr >> 16
            if (
                "\\" in name
                or normalized.is_absolute()
                or ".." in normalized.parts
                or ":" in name
                or stat.S_ISLNK(mode)
            ):
                raise ValueError(f"Unsafe ZIP member: {name}")
            folded = name.casefold()
            if folded in names:
                raise ValueError(f"Duplicate ZIP member: {name}")
            names.add(folded)
            if item.flag_bits & 1:
                raise ValueError(f"Encrypted ZIP member: {name}")
            total += item.file_size
            if total > EXPANDED_LIMIT or item.file_size > 512 * 1024**2:
                raise ValueError("ZIP expanded-size budget exceeded")
            if item.file_size > 1024**2 and item.file_size / max(item.compress_size, 1) > 2000:
                raise ValueError("Suspicious ZIP compression ratio")
            members.append(
                {
                    "name": name,
                    "bytes": item.file_size,
                    "compressed_bytes": item.compress_size,
                    "crc32": f"{item.CRC:08x}",
                }
            )
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "expanded_bytes": total,
        "members": members,
        "extraction": "not extracted; safe streaming inspection only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Inspect pinned tree without writing"
    )
    args = parser.parse_args()
    tree_url = f"https://api.github.com/repos/{REPOSITORY}/git/trees/{COMMIT}?recursive=1"
    with request(tree_url) as stream:
        tree = json.load(stream)
    if tree.get("truncated"):
        raise ValueError("GitHub returned a truncated tree")
    entries = {entry["path"]: entry for entry in tree["tree"] if entry["type"] == "blob"}
    selected_bytes = sum(entries[name]["size"] for name in FILES)
    if args.dry_run:
        print(
            json.dumps(
                {"commit": COMMIT, "selected_bytes": selected_bytes, "files": FILES}, indent=2
            )
        )
        return
    records = [acquire(name, entries[name]) for name in FILES]
    manifest = {
        "schema_version": 1,
        "retrieved_date": "2026-09-29",
        "repository": REPOSITORY,
        "commit": COMMIT,
        "tree_source_url": tree_url,
        "repository_files": [
            {"path": name, "bytes": value["size"], "git_blob_sha1": value["sha"]}
            for name, value in entries.items()
        ],
        "artifacts": records,
        "zip_inspection": inspect_zip(CACHE / "RQ3/rq3_files.zip"),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manifest": str(MANIFEST),
                "files": len(records),
                "bytes": selected_bytes,
                "zip_expanded_bytes": manifest["zip_inspection"]["expanded_bytes"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
