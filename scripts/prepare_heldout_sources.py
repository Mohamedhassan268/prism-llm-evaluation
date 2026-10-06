"""Prepare original-source checks for design work; no held-out translations are read."""

from pathlib import Path

from prepare_calibration import freeze

from prismqa.authors import load_pairs
from prismqa.cli import artifact
from prismqa.records import identity, read_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    catalog = load_pairs(artifact(ROOT, "Preliminary/dataset_after_processing.csv"))
    sample = read_json(ROOT / "data/manifests/track-a-sample.json")
    if identity(catalog) != sample["dataset_identity"]:
        raise ValueError("Pair catalog changed")
    candidates = read_json(ROOT / "data/manifests/calibration-overlap-audit.json")
    selected = set(candidates["proposed_retained_pairs"])
    sources = []
    for item in catalog:
        if item["sample_id"] not in selected:
            continue
        sources.append(
            {
                **item,
                "id": "design-source:" + item["sample_id"],
                "raw_output": item["source_code"],
                "target_language": item["source_language"],
                "data_kind": "authors_source_control",
                "split": "design-reference-only",
                "model": "original-source",
                "condition": "reference-source",
            }
        )
    freeze(ROOT / "data/cache/heldout-design-sources.json", sources)
    profile = {
        **read_json(ROOT / "data/manifests/calibration-baseline-profile.json"),
        "version": "heldout-source-design-check-v1",
        "purpose": "Original-source validation only; no held-out target grading",
        "selection_status": "Reference checks for 97 proposed retained pairs; "
        "final eligibility/design approval pending",
    }
    freeze(ROOT / "data/manifests/heldout-source-check-profile.json", profile)
    print(f"Prepared {len(sources)} original sources; no held-out translations ingested")


if __name__ == "__main__":
    main()
