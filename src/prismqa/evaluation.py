"""Stage-separated grading, reviewed oracles and identity-checked resumable runs."""

from __future__ import annotations

import random
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from .extraction import extract
from .records import identity, inside, read_json, text_hash, validate_records, write_json
from .runner import ContainerRunner
from .sampling import program_group


def grade(case: dict, result: dict, comparator: str) -> str:
    if result.get("status") != "ok":
        return result.get("status", "not_run")
    if comparator == "strict-exact-v1":
        actual = result.get("stdout_sha256") or text_hash(result.get("stdout", ""))
        return "pass" if actual == text_hash(case["expected"]) else "wrong_output"
    if comparator == "strip-v1":
        if result.get("stdout_truncated"):
            return "comparison_unavailable"
        return (
            "pass"
            if result.get("stdout", "").strip() == case["expected"].strip()
            else "wrong_output"
        )
    raise ValueError("Unknown comparator")


def additional_cases(record: dict, profile: dict) -> list[dict]:
    entry = profile.get("domains", {}).get(program_group(record))
    if entry is None:
        return []
    if entry.get("status") != "independently_checked" or not entry.get("domain_description"):
        raise ValueError("Additional tests require an independently checked, described domain")
    tests = entry.get("tests")
    if not isinstance(tests, list) or not tests or len(tests) > 100:
        raise ValueError("A domain must contain 1..100 frozen additional tests")
    for case in tests:
        if not all(isinstance(case.get(key), str) for key in ("input", "expected")):
            raise ValueError("Additional input/expected fields must be strings")
    return tests


def evaluate_one(root: Path, runner, record: dict, profile: dict, run_identity: str) -> dict:
    extraction = extract(
        record["raw_output"],
        record["target_language"],
        profile=profile.get("extraction", record.get("extraction_profile", "direct-v1")),
        prompt=record.get("prompt", ""),
    )
    comparator = profile.get("comparator", "strict-exact-v1")
    originals = record["original_tests"]
    extras = additional_cases(record, profile)
    if len(originals) + len(extras) > 121:
        raise ValueError("Record exceeds scheduled case cap")
    result = {
        "id": record["id"],
        "run_identity": run_identity,
        "group_id": program_group(record),
        "model": record.get("model", "control"),
        "target_language": record["target_language"],
        "condition": record.get("condition", "control"),
        "data_kind": record["data_kind"],
        "extraction": extraction,
        "comparator": comparator,
        "comparator_status": "reconstructed",
        "compilation": {"status": "not_run_extraction_failure"},
        "tests": [],
        "original_pass": False,
        "additional_status": "not_requested",
        "additional_validated": False,
    }
    if extraction["status"] != "ok":
        return result
    cases = originals + extras
    execution = runner.run_program(
        extraction["code"], record["target_language"], cases, root / "runs/_jobs" / uuid.uuid4().hex
    )
    result["compilation"] = execution["compilation"]
    outcomes = execution.get("results", [])
    result["tests"] = [
        {
            "input_hash": text_hash(case["input"]),
            "expected_hash": text_hash(case["expected"]),
            "stage": "original" if index < len(originals) else "additional",
            "outcome": grade(case, outcomes[index], comparator)
            if index < len(outcomes)
            else "not_run",
            "execution": outcomes[index] if index < len(outcomes) else {},
        }
        for index, case in enumerate(cases)
    ]
    result["original_pass"] = all(
        test["outcome"] == "pass" for test in result["tests"][: len(originals)]
    )
    if extras:
        reference_runner = getattr(runner, "run_reference", runner.run_program)
        reference = reference_runner(
            record["source_code"],
            record["source_language"],
            cases,
            root / "runs/_jobs" / uuid.uuid4().hex,
        )
        reference_outcomes = reference.get("results", [])
        oracle_valid = len(reference_outcomes) == len(cases) and all(
            grade(case, reference_outcomes[index], comparator) == "pass"
            for index, case in enumerate(cases)
        )
        result["oracle_check"] = reference
        result["additional_validated"] = oracle_valid
        additional_outcomes = [test["outcome"] for test in result["tests"][len(originals) :]]
        if not oracle_valid:
            reference_ran = len(reference_outcomes) == len(cases) and all(
                item.get("status") == "ok" for item in reference_outcomes
            )
            result["additional_status"] = (
                "oracle_mismatch" if reference_ran else "oracle_inconclusive"
            )
        elif "wrong_output" in additional_outcomes:
            result["additional_status"] = "wrong_output"
        elif all(outcome == "pass" for outcome in additional_outcomes):
            result["additional_status"] = "pass"
        else:
            result["additional_status"] = "inconclusive"
    return result


def summarize(results: list[dict]) -> dict:
    if not results:
        raise ValueError("Cannot summarize zero evaluated records")
    original_passes = sum(result["original_pass"] for result in results)
    eligible = [
        result
        for result in results
        if result["original_pass"]
        and result["additional_validated"]
        and result["additional_status"] in ("pass", "wrong_output")
    ]
    false_passes = sum(result["additional_status"] == "wrong_output" for result in eligible)
    summary = {
        "selected_outputs": len(results),
        "extraction_successes": sum(result["extraction"]["status"] == "ok" for result in results),
        "compilation_successes": sum(result["compilation"]["status"] == "ok" for result in results),
        "original_test_passes": original_passes,
        "validated_extra_original_passes": len(eligible),
        "confirmed_false_passes": false_passes,
        "false_pass_rate": false_passes / len(eligible) if eligible else None,
        "additional_statuses": dict(Counter(result["additional_status"] for result in results)),
        "data_kinds": dict(Counter(result["data_kind"] for result in results)),
        "original_pass_rate_all_selected": original_passes / len(results),
        "target_execution_seconds": sum(
            test.get("execution", {}).get("seconds", 0)
            for result in results
            for test in result["tests"]
        ),
        "additional_target_seconds": sum(
            test.get("execution", {}).get("seconds", 0)
            for result in results
            for test in result["tests"]
            if test["stage"] == "additional"
        ),
        "diagnostic_statuses": dict(
            Counter(test["outcome"] for result in results for test in result["tests"])
        ),
    }
    groups = defaultdict(list)
    for result in eligible:
        groups[result["group_id"]].append(result["additional_status"] == "wrong_output")
    summary["independent_program_groups"] = len(groups)
    summary["breakdowns"] = {}
    for field in ("target_language", "model", "condition"):
        strata = defaultdict(list)
        for result in results:
            strata[result[field]].append(result)
        summary["breakdowns"][field] = {
            value: {
                "selected": len(items),
                "original_passes": sum(item["original_pass"] for item in items),
                "additional_statuses": dict(Counter(item["additional_status"] for item in items)),
            }
            for value, items in sorted(strata.items())
        }
    summary["cluster_bootstrap_95"] = None
    if len(groups) >= 2:
        rng = random.Random(20260929)
        clusters = list(groups.values())
        rates = []
        for _ in range(1000):
            drawn = [flag for cluster in rng.choices(clusters, k=len(clusters)) for flag in cluster]
            rates.append(sum(drawn) / len(drawn))
        rates.sort()
        summary["cluster_bootstrap_95"] = [rates[24], rates[974]]
    return summary


def evaluate(
    root: Path,
    records: list[dict],
    profile: dict,
    directory: Path,
    *,
    resume: bool = False,
    runner=None,
) -> dict:
    validate_records(records)
    if profile.get("comparator", "strict-exact-v1") not in ("strict-exact-v1", "strip-v1"):
        raise ValueError("Unknown comparator")
    for record in records:
        additional_cases(record, profile)
        if record["data_kind"] == "authors_saved_outputs" and record.get("split") != "calibration":
            review = profile.get("human_review", {})
            if review.get("protocol") != "approved" or review.get("frozen_design") != "approved":
                raise ValueError(
                    "Authentic held-out grading requires recorded user review of protocol/design"
                )
    executor = runner or ContainerRunner(root)
    run_identity = identity({"records": records, "profile": profile, "toolchain": executor.lock})
    destination = inside(root, directory)
    state_path = destination / "state.json"
    expected_ids = [record["id"] for record in records]
    if state_path.exists():
        state = read_json(state_path)
        if not resume or state["run_identity"] != run_identity:
            raise ValueError(
                "Existing run requires --resume and identical dataset/profile/toolchain"
            )
    else:
        state = {
            "schema_version": 1,
            "run_identity": run_identity,
            "status": "in_progress",
            "expected_ids": expected_ids,
            "dataset_identity": identity(records),
            "profile_identity": identity(profile),
            "toolchain": executor.lock,
            "profile": profile,
        }
        write_json(state_path, state)
    results = []
    for record in records:
        output = destination / "records" / (text_hash(record["id"]) + ".json")
        if output.exists():
            result = read_json(output)
            stored_identity = result.pop("result_identity")
            if result["run_identity"] != run_identity or identity(result) != stored_identity:
                raise ValueError("Cached result identity mismatch")
            if result["id"] != record["id"]:
                raise ValueError("Cached result record mismatch")
        else:
            result = evaluate_one(root, executor, record, profile, run_identity)
            write_json(output, {**result, "result_identity": identity(result)})
        results.append(result)
    summary = summarize(results)
    write_json(destination / "summary.json", summary)
    write_json(
        state_path,
        {
            **state,
            "status": "complete",
            "completed_outputs": len(results),
            "summary_identity": identity(summary),
        },
    )
    return summary


def verified_report(directory: Path) -> tuple[dict, dict]:
    state = read_json(directory / "state.json")
    if state["status"] != "complete" or not state.get("expected_ids"):
        raise ValueError("Cannot report an empty/incomplete evaluation as complete")
    results = []
    for identifier in state["expected_ids"]:
        result = read_json(directory / "records" / (text_hash(identifier) + ".json"))
        result_identity = result.pop("result_identity")
        if result["id"] != identifier or result["run_identity"] != state["run_identity"]:
            raise ValueError("Result provenance mismatch")
        if identity(result) != result_identity:
            raise ValueError("Result changed after evaluation")
        results.append(result)
    summary = summarize(results)
    if (
        summary != read_json(directory / "summary.json")
        or identity(summary) != state["summary_identity"]
    ):
        raise ValueError("Report summary does not match raw outcomes")
    return state, summary
