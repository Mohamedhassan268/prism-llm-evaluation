"""Pin a contemporary collection snapshot; never execute its prompts."""

import csv
import io
import json
import random
import urllib.request
from pathlib import Path

from prismqa.records import file_hash, identity, write_json

ROOT = Path(__file__).resolve().parents[1]
REPO = "f/prompts.chat"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "PRISM-QA-research-pilot"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(20 * 1024**2 + 1)
    if len(data) > 20 * 1024**2:
        raise ValueError("Artifact exceeds 20 MiB download cap")
    return data


def main():
    csv.field_size_limit(20 * 1024**2)
    target = ROOT / "data/manifests/track-b-sample.json"
    if target.exists():
        raise ValueError("Selection already frozen; do not silently repin")
    info = json.loads(fetch(f"https://api.github.com/repos/{REPO}"))
    commit = json.loads(
        fetch(f"https://api.github.com/repos/{REPO}/commits/" + info["default_branch"])
    )["sha"]
    cache = ROOT / "data/cache/prompts-chat" / commit
    cache.mkdir(parents=True, exist_ok=True)
    assets = []
    for name in ("prompts.csv", "LICENSE", "LICENSE-CC0", "README.md"):
        url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{name}"
        path = cache / name
        path.write_bytes(fetch(url))
        assets.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "url": url,
                "sha256": file_hash(path),
                "bytes": path.stat().st_size,
            }
        )
    rows = list(
        csv.DictReader(io.StringIO((cache / "prompts.csv").read_text(encoding="utf-8-sig")))
    )
    if not rows or "prompt" not in rows[0]:
        raise ValueError("CSV no longer provides the expected prompt column")
    candidates = [i for i, row in enumerate(rows) if row.get("prompt", "").strip()]
    random.Random(20260929).shuffle(candidates)
    chosen = sorted(candidates[:500])
    records = [
        {
            "id": f"prompts-chat:{i + 2}",
            "text": rows[i]["prompt"],
            "title": rows[i].get("act", ""),
            "repository": REPO,
            "commit": commit,
            "path": "prompts.csv",
            "csv_row": i + 2,
            "corpus_kind": "contemporary_reconstruction",
        }
        for i in chosen
    ]
    manifest = {
        "schema_version": 1,
        "retrieved_date": "2026-09-29",
        "seed": 20260929,
        "repository": REPO,
        "commit": commit,
        "created_at": info["created_at"],
        "stars_at_retrieval": info["stargazers_count"],
        "category": "collection",
        "license": "CC0-1.0 (prompt data); MIT (source code), as stated in cached licenses",
        "artifacts": assets,
        "eligible_nonempty_rows": len(candidates),
        "excluded_empty_rows": len(rows) - len(candidates),
        "selected_rows": [i + 2 for i in chosen],
        "records_identity": identity(records),
        "limitations": [
            "New single-repository sample; not the authors corpus.",
            "Application/courseware categories are not represented.",
            "Language eligibility requires review before English metrics.",
        ],
    }
    write_json(ROOT / "data/cache/track-b-prompts.json", records)
    write_json(target, manifest)
    print(
        json.dumps(
            {"commit": commit, "selected": len(records), "eligible": len(candidates)}, indent=2
        )
    )


if __name__ == "__main__":
    main()
