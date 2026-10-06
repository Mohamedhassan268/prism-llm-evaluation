"""Run every frozen calibration model in sequential, resumable 30-output batches."""

import argparse
from pathlib import Path

from prepare_calibration import freeze

from prismqa.evaluation import evaluate, verified_report
from prismqa.records import identity, read_json, write_json
from prismqa.reference_cache import ReferenceCacheRunner

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["baseline", "extended"], required=True)
    parser.add_argument("--first", type=int, default=1)
    parser.add_argument("--last", type=int, default=11)
    args = parser.parse_args()
    selection = read_json(ROOT / "data/manifests/calibration-batches.json")
    records = read_json(ROOT / "data/cache/calibration-outputs.json")
    if len(records) != selection["total_saved_calibration_outputs"]:
        raise ValueError("Calibration inventory changed")
    if args.stage == "extended":
        _, reference = verified_report(ROOT / "runs/calibration-source-extended")
        if reference["original_test_passes"] != 10 or reference["additional_statuses"] != {
            "pass": 10
        }:
            raise ValueError("Source controls do not validate all frozen domains")
    profile = read_json(
        ROOT
        / "data/manifests"
        / (
            "calibration-baseline-profile.json"
            if args.stage == "baseline"
            else "calibration-domains-v1.json"
        )
    )
    runner = (
        ReferenceCacheRunner(ROOT, "runs/calibration-source-extended")
        if args.stage == "extended"
        else None
    )
    for index, model in enumerate(selection["models"], 1):
        if not args.first <= index <= args.last:
            continue
        batch = [item for item in records if item["model"] == model]
        freeze(ROOT / "data/cache" / f"calibration-batch-{index:02}.json", batch)
        directory = ROOT / "runs" / f"calibration-batch-{index:02}-{args.stage}"
        print(f"Start {args.stage} model {index}/{len(selection['models'])}: {model}", flush=True)
        result = evaluate(
            ROOT,
            batch,
            profile,
            directory,
            resume=(directory / "state.json").exists(),
            runner=runner,
        )
        verified_report(directory)
        write_json(
            ROOT / "reports" / f"calibration-batch-{index:02}-{args.stage}.json",
            {
                "dataset_identity": identity(batch),
                "profile_identity": identity(profile),
                "model": model,
                "stage": args.stage,
                "summary": result,
            },
        )
        print(
            f"Complete model {index}: original passes {result['original_test_passes']}/"
            f"{len(batch)}, extra statuses {result['additional_statuses']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
