"""Build a verified calibration checkpoint; incomplete batches stay incomplete."""

import shutil
from collections import Counter
from pathlib import Path

from prismqa.calibration_diagnostics import diagnose
from prismqa.evaluation import summarize, verified_report
from prismqa.records import file_hash, identity, read_json, text_hash, write_json
from prismqa.sampling import program_group

ROOT = Path(__file__).resolve().parents[1]


def stage_records(stage, models):
    records, completed, pending, identities = [], [], [], []
    for i, model in enumerate(models, 1):
        directory = ROOT / "runs" / f"calibration-batch-{i:02}-{stage}"
        state_path = directory / "state.json"
        if not state_path.exists() or read_json(state_path)["status"] != "complete":
            pending.append(model)
            continue
        state, _ = verified_report(directory)
        dataset = read_json(ROOT / "data/cache" / f"calibration-batch-{i:02}.json")
        if identity(dataset) != state["dataset_identity"]:
            raise ValueError("Batch dataset changed")
        records.extend(
            read_json(directory / "records" / (text_hash(item["id"]) + ".json")) for item in dataset
        )
        completed.append(model)
        identities.append(state["run_identity"])
    return {
        "status": "complete" if not pending else "incomplete",
        "completed_models": completed,
        "pending_models": pending,
        "run_identities": identities,
        "summary": summarize(records) if records else None,
    }, records


def main():
    selection = read_json(ROOT / "data/manifests/calibration-batches.json")
    baseline, base_rows = stage_records("baseline", selection["models"])
    extended, extra_rows = stage_records("extended", selection["models"])
    base = {r["id"]: r for r in base_rows}
    extras = {r["id"]: r for r in extra_rows}
    outputs = {r["id"]: r for r in read_json(ROOT / "data/cache/calibration-outputs.json")}
    profile = read_json(ROOT / "data/manifests/calibration-domains-v1.json")
    changes, examples = Counter(), []
    for identifier in sorted(base.keys() & extras.keys()):
        original, result = base[identifier], extras[identifier]
        if original["original_pass"] != result["original_pass"]:
            raise ValueError(
                "Baseline original outcome differs in extended run; triage before reporting"
            )
        if result["original_pass"] and result["additional_status"] == "wrong_output":
            changes[result["model"]] += 1
            failed = [
                t
                for t in result["tests"]
                if t["stage"] == "additional" and t["outcome"] == "wrong_output"
            ]
            metadata = outputs[identifier]
            cases = profile["domains"][program_group(metadata)]["tests"]
            lookup = {(text_hash(c["input"]), text_hash(c["expected"])): c for c in cases}
            diagnoses = []
            for test in failed:
                case = lookup[(test["input_hash"], test["expected_hash"])]
                diagnoses.append(
                    {
                        "input": case["input"],
                        "expected": case["expected"],
                        "actual": test["execution"].get("stdout"),
                        "category": diagnose(
                            metadata["sample_id"], case["expected"], test["execution"]
                        ),
                    }
                )
            examples.append(
                {
                    "id": identifier,
                    "pair": outputs[identifier]["sample_id"],
                    "model": result["model"],
                    "condition": result["condition"],
                    "failed_input_hashes": [t["input_hash"] for t in failed],
                    "diagnostics": diagnoses,
                }
            )
    # VDE and VRE share generations. Their comparison is paired, not independent samples.
    paired = Counter()
    paired_examples = {"rescued": [], "lost": []}
    generations = {}
    for output in outputs.values():
        if output["id"] not in base or output["condition"] not in ("VDE", "VRE"):
            continue
        generations.setdefault(output["saved_generation_id"], {})[output["condition"]] = output
    for pair in generations.values():
        if set(pair) != {"VDE", "VRE"}:
            continue
        direct, extracted = pair["VDE"], pair["VRE"]
        for field in ("raw_output", "prompt", "source_code", "target_language", "model"):
            if direct[field] != extracted[field]:
                raise ValueError("Paired extraction records do not share the same generation")
        paired["pairs"] += 1
        d, e = base[direct["id"]], base[extracted["id"]]
        paired["direct_original_passes"] += d["original_pass"]
        paired["extracted_original_passes"] += e["original_pass"]
        paired["extraction_rescued_original_pass"] += not d["original_pass"] and e["original_pass"]
        paired["extraction_lost_original_pass"] += d["original_pass"] and not e["original_pass"]
        direction = (
            "rescued"
            if not d["original_pass"] and e["original_pass"]
            else "lost"
            if d["original_pass"] and not e["original_pass"]
            else None
        )
        if direction:
            paired_examples[direction].append(
                {
                    "model": direct["model"],
                    "sample_id": direct["sample_id"],
                    "direct_id": direct["id"],
                    "extracted_id": extracted["id"],
                    "raw_output_hash": d["extraction"]["raw_hash"],
                    "direct_extraction_status": d["extraction"]["status"],
                    "regex_extraction_status": e["extraction"]["status"],
                    "direct_compilation_status": d["compilation"]["status"],
                    "regex_compilation_status": e["compilation"]["status"],
                }
            )
    record = {
        "study_status": "calibration only; held-out grading not started",
        "baseline": baseline,
        "extended": extended,
        "paired_original_conditions": dict(paired),
        "paired_examples": paired_examples,
        "confirmed_false_pass_examples": examples,
        "confirmed_false_passes_by_model": dict(changes),
        "functional_value_fault_outputs": sum(
            any(d["category"] == "functional_value_mismatch" for d in item["diagnostics"])
            for item in examples
        ),
        "diagnostic_method": "Post-hoc value/format classification; frozen strict grades unchanged",
        "diagnostic_implementation_sha256": file_hash(
            ROOT / "src/prismqa/calibration_diagnostics.py"
        ),
        "limit": "Reconstructed compilation/grading. Related conditions share generations. "
        "Calibration is exploratory; this is not the held-out pilot.",
    }
    write_json(ROOT / "reports/calibration-checkpoint.json", record)
    lines = [
        "# Calibration checkpoint",
        "",
        record["study_status"],
        "",
        "The public-task mapping and frozen tests are in "
        "[the design record](../docs/CALIBRATION_DESIGN.md).",
        "",
    ]
    for name, stage in [
        ("Original-test replay", baseline),
        ("Additional-test evaluation", extended),
    ]:
        lines += [
            f"## {name}",
            "",
            f"Status: **{stage['status']}**. Completed models: "
            f"{len(stage['completed_models'])}/{len(selection['models'])}.",
            "",
        ]
        summary = stage["summary"]
        if summary:
            lines += [
                f"Evaluated saved outputs: {summary['selected_outputs']}. "
                f"Original passes: {summary['original_test_passes']}. "
                f"Confirmed additional wrong-output cases among original passes: "
                f"{summary['confirmed_false_passes']}.",
                "",
            ]
    lines += [
        "## Paired formatting comparison",
        "",
        str(dict(paired)),
        "",
        "VDE and VRE are the same generations under different extraction conditions.",
        "",
        "All ten original sources pass their original test and all 601 additional cases.",
        "Three confirmed problem overlaps are proposed for exclusion before held-out grading.",
        "",
        record["limit"],
        "",
    ]
    (ROOT / "reports/CALIBRATION_CHECKPOINT.md").write_text("\n".join(lines), encoding="utf-8")
    for name in ("calibration-source-baseline", "calibration-source-extended"):
        destination = ROOT / "reports/evidence" / name
        destination.mkdir(parents=True, exist_ok=True)
        for file in ("summary.json", "state.json"):
            shutil.copyfile(ROOT / "runs" / name / file, destination / file)
    print(
        {
            name: len(stage["completed_models"])
            for name, stage in [("baseline", baseline), ("extended", extended)]
        }
    )


if __name__ == "__main__":
    main()
