"""Read pinned author CSVs as data, without running notebooks or extracting ZIPs."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from .records import text_hash

LANGUAGES = {
    "c": "C",
    "c++": "C++",
    "cpp": "C++",
    "go": "Go",
    "golang": "Go",
    "java": "Java",
    "python": "Python",
    "python3": "Python",
}


def language(value: str) -> str:
    try:
        return LANGUAGES[value.lower().strip()]
    except KeyError as exc:
        raise ValueError(f"Unsupported author language: {value}") from exc


def load_pairs(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("Empty author dataset")
    return [
        {
            "id": "pair:" + row["sample_id"],
            "sample_id": row["sample_id"],
            "source_code": row["input_code"],
            "source_language": language(row["input_lang"]),
            "target_language": language(row["desired_output_lang"]),
            "original_tests": [
                {"input": row["test_case_input_data"], "expected": row["test_case_expected_output"]}
            ],
            "data_kind": "authors_pair_catalog",
            "grouping": "exact_source_hash",
        }
        for row in rows
    ]


def load_saved(
    path: Path, pair_ids: list[str], *, split: str = "calibration", model: str | None = None
) -> list[dict]:
    requested = set(pair_ids)
    if not requested:
        raise ValueError("No selected pairs")
    records = []
    seen = set()
    with zipfile.ZipFile(path) as archive:
        for member in sorted(archive.namelist()):
            lower = member.lower()
            if not lower.endswith(".csv") or "inference_output" not in lower:
                continue
            condition = next(
                (item for item in ("CRE", "VDE", "VRE") if item.lower() in lower), None
            )
            if condition is None:
                raise ValueError(f"Unrecognized author condition: {member}")
            with (
                archive.open(member) as raw,
                io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream,
            ):
                for row_number, row in enumerate(csv.DictReader(stream), 2):
                    if row["sample_id"] not in requested:
                        continue
                    if model and row["model_path"] != model:
                        continue
                    identifier = condition + ":" + row["translation_output_id"]
                    if identifier in seen:
                        raise ValueError(f"Duplicate saved-output identity {identifier}")
                    seen.add(identifier)
                    records.append(
                        {
                            "id": identifier,
                            "sample_id": row["sample_id"],
                            "source_code": row["input_code"],
                            "source_language": language(row["source_language"]),
                            "target_language": language(row["target_language"]),
                            "raw_output": row["new_tokens_from_inference_output"],
                            "prompt": row["prompt_template"],
                            "model": row["model_path"],
                            "condition": condition,
                            "split": split,
                            "extraction_profile": "direct-v1"
                            if condition == "VDE"
                            else "authors-regex-v1",
                            "original_tests": [
                                {
                                    "input": row["test_case_input_data"],
                                    "expected": row["test_case_expected_output"],
                                }
                            ],
                            "data_kind": "authors_saved_outputs",
                            "saved_generation_id": (
                                "control:" if condition == "CRE" else "vanilla:"
                            )
                            + row["translation_output_id"],
                            "source_hash": text_hash(row["input_code"]),
                            "provenance": {
                                "archive": str(path.name),
                                "member": member,
                                "row": row_number,
                            },
                        }
                    )
    if not records:
        raise ValueError("No saved outputs matched selected pairs/model")
    return records
