"""Separately diagnose a missing C math-library link; never replace frozen grades."""

import uuid
from pathlib import Path

from prismqa import runner
from prismqa.records import read_json, text_hash, write_json

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = next(
        row
        for row in read_json(ROOT / "data/cache/heldout-design-sources.json")
        if row["id"] == "design-source:59019"
    )
    baseline = read_json(
        ROOT / "runs/heldout-source-design-check/records" / (text_hash(source["id"]) + ".json")
    )
    if baseline["original_pass"] or "undefined reference to `sqrt'" not in baseline[
        "compilation"
    ]["stderr"]:
        raise ValueError("Unexpected frozen baseline; inspect before running diagnostic")
    destination = ROOT / "reports/source-libm-diagnostic.json"
    if destination.exists():
        raise ValueError("Diagnostic already recorded; preserve its original execution")
    original_commands = runner.language_commands

    def libm_commands(language, code):
        name, compiler, executable = original_commands(language, code)
        if language != "C":
            raise ValueError("This diagnostic supports the selected C source only")
        return name, [*compiler, "-lm"], executable

    # Keep this compiler override separate from frozen run profiles.
    runner.language_commands = libm_commands
    try:
        result = runner.ContainerRunner(ROOT).run_program(
            source["source_code"],
            "C",
            source["original_tests"],
            ROOT / "runs/source-libm-diagnostic" / uuid.uuid4().hex,
        )
    finally:
        runner.language_commands = original_commands
    write_json(
        destination,
        {
            "scope": "post-hoc compiler-configuration diagnostic; frozen grades unchanged",
            "source_id": source["id"],
            "source_code_sha256": text_hash(source["source_code"]),
            "frozen_baseline_compilation": baseline["compilation"],
            "diagnostic_compiler": libm_commands("C", source["source_code"])[1],
            "expected_outputs": [t["expected"] for t in source["original_tests"]],
            "result": result,
            "heldout_target_outputs_inspected": False,
        },
    )
    print({"diagnostic": str(destination), "frozen_grades_changed": False})


if __name__ == "__main__":
    main()
