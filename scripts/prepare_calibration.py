"""Freeze calibration inputs/selection before grading saved target translations."""

from pathlib import Path

from prismqa.authors import load_pairs
from prismqa.cli import artifact
from prismqa.records import identity, read_json, write_json
from prismqa.sampling import program_group

ROOT = Path(__file__).resolve().parents[1]


def freeze(path, value):
    if path.exists() and read_json(path) != value:
        raise ValueError(f"Frozen contents differ: {path}; use a new version")
    write_json(path, value)


def main():
    manifest = read_json(ROOT / "data/manifests/track-a-sample.json")
    claimed = manifest.pop("manifest_identity")
    if identity(manifest) != claimed:
        raise ValueError("Sample manifest changed")
    pairs = load_pairs(artifact(ROOT, "Preliminary/dataset_after_processing.csv"))
    if identity(pairs) != manifest["dataset_identity"]:
        raise ValueError("Pair catalog changed")
    selected = [item for item in pairs if item["sample_id"] in manifest["pair_ids"]["calibration"]]
    sources = [
        {
            **item,
            "id": "source:" + item["sample_id"],
            "raw_output": item["source_code"],
            "target_language": item["source_language"],
            "data_kind": "authors_source_control",
            "model": "original-source",
            "condition": "reference-source",
            "split": "calibration",
        }
        for item in selected
    ]
    outputs = read_json(ROOT / "data/cache/calibration-outputs.json")
    models = sorted({item["model"] for item in outputs})
    batch = [item for item in outputs if item["model"] == models[0]]
    profile = {
        "version": "calibration-baseline-strict-v1",
        "comparator": "strict-exact-v1",
        "grading_status": "reconstructed",
        "human_review": {"protocol": "approved", "samples": "approved", "frozen_design": "pending"},
        "review_basis": "User: next is what start it; 2026-09-29",
        "domains": {},
    }
    freeze(ROOT / "data/manifests/calibration-baseline-profile.json", profile)
    freeze(ROOT / "data/cache/calibration-sources.json", sources)
    freeze(ROOT / "data/cache/calibration-batch-01.json", batch)
    freeze(
        ROOT / "data/manifests/calibration-batches.json",
        {
            "selection_rule": "All 11 models sorted by model identifier; "
            "first batch is first model. "
            "Selection precedes calibration outcomes; no model ranking inferred.",
            "models": models,
            "first_model": models[0],
            "first_batch_ids": [r["id"] for r in batch],
            "first_batch_identity": identity(batch),
            "total_saved_calibration_outputs": len(outputs),
            "source_groups": [program_group(r) for r in sources],
            "first_batch_records": len(batch),
            "sample_identity": claimed,
        },
    )
    print(f"Frozen {len(sources)} sources and {len(batch)} saved outputs for {models[0]}")


if __name__ == "__main__":
    main()
